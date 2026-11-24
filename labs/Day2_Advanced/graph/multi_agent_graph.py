"""Modern LangGraph multi-agent orchestration with Command, Send, and HITL."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agents.coder import CoderAgent
from agents.planner import PlannerAgent
from agents.researcher import ResearcherAgent
from agents.reviewer import ReviewerAgent
from state import AgentRole, MultiAgentState, TaskStatus
from utils.constants import (
    GRAPH_RECURSION_LIMIT,
    SYNTHESIZER_SYSTEM_PROMPT,
)
from utils.llm import get_llm
from utils.routing import next_route_after_plan, next_route_after_review, pending_tasks


class MultiAgentGraph:
    def __init__(
        self,
        enable_checkpoints: bool = True,
        enable_human_review: bool = True,
    ):
        self.planner = PlannerAgent()
        self.researcher = ResearcherAgent()
        self.coder = CoderAgent()
        self.reviewer = ReviewerAgent()
        self.enable_human_review = enable_human_review
        self.graph = self._build_graph(enable_checkpoints)

    def _build_graph(self, enable_checkpoints: bool):
        workflow = StateGraph(MultiAgentState)

        workflow.add_node("planner", self.planning_node)
        workflow.add_node("dispatch", self.dispatch_node)
        workflow.add_node("researcher", self.research_node)
        workflow.add_node("coder", self.coding_node)
        workflow.add_node("reviewer", self.review_node)
        workflow.add_node("synthesizer", self.synthesize_node)

        workflow.add_edge(START, "planner")
        workflow.add_edge("planner", "dispatch")
        workflow.add_edge("researcher", "reviewer")
        workflow.add_edge("coder", "reviewer")
        workflow.add_edge("synthesizer", END)

        return workflow.compile(
            checkpointer=MemorySaver() if enable_checkpoints else None
        )

    def planning_node(self, state: MultiAgentState) -> dict:
        print("\n[Planner] Creating execution plan...")
        query = state.get("original_query") or ""
        if not query:
            for message in reversed(state.get("messages", [])):
                if isinstance(message, HumanMessage):
                    query = message.content
                    break

        plan_result = self.planner.create_plan(query)
        return {
            "original_query": query,
            "plan": plan_result,
            "tasks": plan_result["tasks"],
            "messages": [
                AIMessage(
                    content=(
                        f"Plan created with {len(plan_result['tasks'])} tasks:\n"
                        f"{plan_result['reasoning']}"
                    )
                )
            ],
            "agent_history": [
                {
                    "agent": "planner",
                    "action": "created_plan",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
            "iteration_count": 0,
            "requires_human_input": False,
            "human_feedback": None,
        }

    def dispatch_node(
        self, state: MultiAgentState
    ) -> Command[Literal["researcher", "coder", "synthesizer"]]:
        """Route with Command so state updates and control-flow stay atomic."""
        route = next_route_after_plan(state)
        print(f"\n[Dispatch] Routing to: {route}")
        return Command(goto=route)

    def research_node(self, state: MultiAgentState) -> dict:
        print("\n[Researcher] Conducting research...")
        tasks = list(state.get("tasks", []))
        current_task_id = state.get("current_task_id")

        if current_task_id:
            task = next((item for item in tasks if item["id"] == current_task_id), None)
        else:
            pending = pending_tasks(tasks, AgentRole.RESEARCHER)
            task = pending[0] if pending else None

        if not task:
            return {"messages": [AIMessage(content="No research tasks pending.")]}

        task_update = {**task, "status": TaskStatus.IN_PROGRESS}
        result = self.researcher.research(task_update, self._build_context(state))
        completed = {
            **task_update,
            "status": result["status"],
            "result": result.get("findings"),
            "completed_at": result.get("timestamp"),
        }
        return {
            "current_task_id": task["id"],
            "tasks": [completed],
            "research_findings": [result],
            "messages": [
                AIMessage(content=f"Research completed for: {task['description']}")
            ],
            "agent_history": [
                {
                    "agent": "researcher",
                    "action": "researched",
                    "task_id": task["id"],
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }

    def coding_node(self, state: MultiAgentState) -> dict:
        print("\n[Coder] Generating code...")
        tasks = list(state.get("tasks", []))
        pending = pending_tasks(tasks, AgentRole.CODER)
        if not pending:
            return {"messages": [AIMessage(content="No coding tasks pending.")]}

        task = pending[0]
        task_update = {**task, "status": TaskStatus.IN_PROGRESS}
        result = self.coder.generate_code(task_update, self._build_context(state))
        completed = {
            **task_update,
            "status": result["status"],
            "result": result.get("code"),
            "completed_at": result.get("timestamp"),
        }
        return {
            "current_task_id": task["id"],
            "tasks": [completed],
            "code_artifacts": [result],
            "messages": [
                AIMessage(content=f"Code generated for: {task['description']}")
            ],
            "agent_history": [
                {
                    "agent": "coder",
                    "action": "coded",
                    "task_id": task["id"],
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }

    def review_node(
        self, state: MultiAgentState
    ) -> Command[Literal["researcher", "coder", "synthesizer"]]:
        print("\n[Reviewer] Reviewing work...")
        current_task_id = state.get("current_task_id")
        tasks = state.get("tasks", [])
        task = next((item for item in tasks if item.get("id") == current_task_id), None)
        if not task:
            return Command(goto="synthesizer")

        work_product: dict = {}
        if task.get("assigned_to") == AgentRole.CODER:
            work_product = next(
                (
                    artifact
                    for artifact in reversed(state.get("code_artifacts", []))
                    if artifact.get("task_id") == current_task_id
                ),
                {},
            )
        else:
            work_product = next(
                (
                    finding
                    for finding in reversed(state.get("research_findings", []))
                    if finding.get("task_id") == current_task_id
                ),
                {},
            )

        review_result = self.reviewer.review(
            task, work_product, self._build_context(state)
        )
        iteration = int(state.get("iteration_count") or 0) + 1
        human_feedback = state.get("human_feedback")

        # Human-in-the-loop when automated review rejects work
        if (
            self.enable_human_review
            and not review_result.get("approved")
            and iteration <= 2
        ):
            print("\n[HITL] Waiting for human decision on rejected work...")
            decision = interrupt(
                {
                    "type": "review_gate",
                    "task_id": current_task_id,
                    "task": task.get("description"),
                    "score": review_result.get("score"),
                    "feedback": review_result.get("feedback"),
                    "prompt": (
                        "Automated reviewer requested changes. "
                        "Reply with 'approve', 'revise', or free-text guidance."
                    ),
                }
            )
            human_feedback = str(decision)
            lowered = human_feedback.lower().strip()
            if lowered in {"approve", "approved", "yes", "y"}:
                review_result["approved"] = True
                review_result["decision"] = "approve"
                review_result["feedback"] = (
                    f"{review_result.get('feedback', '')}\n\n"
                    f"Human override: APPROVED ({human_feedback})"
                )
            else:
                review_result["approved"] = False
                review_result["feedback"] = (
                    f"{review_result.get('feedback', '')}\n\n"
                    f"Human guidance: {human_feedback}"
                )

        task_status = (
            TaskStatus.COMPLETED
            if review_result.get("approved")
            else TaskStatus.NEEDS_REVIEW
        )
        task_update = {
            **task,
            "status": task_status,
        }
        update = {
            "tasks": [task_update],
            "review_feedback": [review_result],
            "iteration_count": iteration,
            "requires_human_input": not review_result.get("approved"),
            "human_feedback": human_feedback,
            "messages": [
                AIMessage(
                    content=(
                        "Review: "
                        + (
                            "Approved"
                            if review_result.get("approved")
                            else "Needs Revision"
                        )
                        + f"\n{review_result.get('feedback', '')}"
                    )
                )
            ],
            "agent_history": [
                {
                    "agent": "reviewer",
                    "action": "reviewed",
                    "task_id": current_task_id,
                    "approved": review_result.get("approved"),
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }

        route = next_route_after_review({**state, **update})
        print(f"\n[Reviewer] Next route: {route}")
        return Command(update=update, goto=route)

    def synthesize_node(self, state: MultiAgentState) -> dict:
        print("\n[Synthesizer] Creating final output...")
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYNTHESIZER_SYSTEM_PROMPT),
                (
                    "human",
                    "Original Query: {query}\n\n"
                    "Research Findings:\n{research}\n\n"
                    "Code Artifacts:\n{code}\n\n"
                    "Review Feedback:\n{reviews}\n\n"
                    "Create a comprehensive final answer.",
                ),
            ]
        )
        research_str = "\n\n".join(
            item.get("findings", "") for item in state.get("research_findings", [])
        )
        code_str = "\n\n".join(
            (
                f"Language: {item.get('language', 'python')}\n"
                f"```\n{item.get('code', '')}\n```\n"
                f"Explanation: {item.get('explanation', '')}\n"
                f"Usage: {item.get('usage', '')}"
            )
            for item in state.get("code_artifacts", [])
        )
        reviews_str = "\n\n".join(
            (
                f"Decision={item.get('decision')} score={item.get('score')}\n"
                f"{item.get('feedback', '')}"
            )
            for item in state.get("review_feedback", [])
        )

        try:
            response = (prompt | get_llm(temperature=0.3)).invoke(
                {
                    "query": state.get("original_query", ""),
                    "research": research_str or "None",
                    "code": code_str or "None",
                    "reviews": reviews_str or "None",
                }
            )
            final_output = response.content
        except Exception as exc:
            final_output = (
                f"# Final Output (fallback)\n\n"
                f"Query: {state.get('original_query', '')}\n\n"
                f"## Research\n{research_str or 'None'}\n\n"
                f"## Code\n{code_str or 'None'}\n\n"
                f"## Reviews\n{reviews_str or 'None'}\n\n"
                f"_Synthesizer LLM unavailable: {exc}_"
            )

        return {
            "final_output": final_output,
            "messages": [AIMessage(content=final_output)],
            "agent_history": [
                {
                    "agent": "synthesizer",
                    "action": "finalized",
                    "timestamp": datetime.now().isoformat(),
                }
            ],
        }

    def _build_context(self, state: MultiAgentState) -> dict:
        return {
            "research": "\n".join(
                item.get("findings", "") for item in state.get("research_findings", [])
            ),
            "code": "\n".join(
                item.get("code", "") for item in state.get("code_artifacts", [])
            ),
            "reviews": "\n".join(
                item.get("feedback", "") for item in state.get("review_feedback", [])
            ),
            "tasks": [
                task["description"]
                for task in state.get("tasks", [])
                if task.get("status") == TaskStatus.COMPLETED
            ],
        }

    def _initial_state(self, query: str) -> MultiAgentState:
        return {
            "messages": [HumanMessage(content=query)],
            "original_query": query,
            "plan": None,
            "tasks": [],
            "current_task_id": None,
            "research_findings": [],
            "code_artifacts": [],
            "review_feedback": [],
            "final_output": "",
            "iteration_count": 0,
            "agent_history": [],
            "errors": [],
            "requires_human_input": False,
            "human_feedback": None,
        }

    def run(self, query: str, config: dict | None = None) -> dict:
        """Execute until completion or HITL interrupt."""
        if config is None:
            config = {"configurable": {"thread_id": "1"}}
        config = {
            **config,
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }
        return self.graph.invoke(self._initial_state(query), config)

    def stream(self, query: str, config: dict | None = None):
        """Stream node updates for demo visibility."""
        if config is None:
            config = {"configurable": {"thread_id": "1"}}
        config = {
            **config,
            "recursion_limit": GRAPH_RECURSION_LIMIT,
        }
        return self.graph.stream(
            self._initial_state(query),
            config,
            stream_mode="updates",
        )

    def resume(self, decision: str, config: dict) -> dict:
        """Resume after a human interrupt."""
        return self.graph.invoke(
            Command(resume=decision),
            {**config, "recursion_limit": GRAPH_RECURSION_LIMIT},
        )

    def get_state(self, config: dict):
        return self.graph.get_state(config)
