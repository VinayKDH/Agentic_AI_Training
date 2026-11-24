"""Enterprise LangGraph multi-agent orchestration with Command, HITL, and gates."""

from __future__ import annotations

from datetime import datetime, timezone
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
from state import AgentRole, MultiAgentState, TaskStatus, upsert_tasks
from utils.constants import (
    ENTERPRISE_POLICY_CHECKLIST,
    GRAPH_RECURSION_LIMIT,
    SYNTHESIZER_SYSTEM_PROMPT,
)
from utils.guardrails import validate_user_query
from utils.llm import active_model_label, get_llm
from utils.observability import RunContext, format_run_report
from utils.policies import apply_policy_to_review, evaluate_work_product
from utils.resilience import with_retry
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
        self._run_ctx: RunContext | None = None
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

    def _ctx(self, state: MultiAgentState) -> RunContext:
        if self._run_ctx is None:
            self._run_ctx = RunContext(run_id=state.get("run_id"))
        return self._run_ctx

    def planning_node(self, state: MultiAgentState) -> dict:
        ctx = self._ctx(state)
        print("\n[Planner] Creating enterprise execution plan...")
        query = state.get("original_query") or ""
        if not query:
            for message in reversed(state.get("messages", [])):
                if isinstance(message, HumanMessage):
                    query = message.content
                    break

        guard = validate_user_query(query)
        if not guard.ok:
            ctx.increment("guardrail_blocks")
            ctx.log(
                "planner",
                "guardrail_block",
                status="blocked",
                reasons=guard.reasons,
            )
            return {
                "original_query": query,
                "final_output": (
                    "Request blocked by enterprise input guardrails:\n- "
                    + "\n- ".join(guard.reasons)
                ),
                "guardrail_status": {
                    "ok": False,
                    "reasons": guard.reasons,
                    "findings": guard.findings,
                },
                "policy_violations": guard.reasons,
                "tasks": [],
                "plan": {"tasks": [], "reasoning": "Blocked by guardrails"},
                "messages": [
                    AIMessage(
                        content="Input rejected by enterprise guardrails: "
                        + "; ".join(guard.reasons)
                    )
                ],
                "agent_history": [
                    {
                        "agent": "planner",
                        "action": "guardrail_block",
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                        "details": guard.reasons,
                    }
                ],
                "iteration_count": 0,
                "requires_human_input": False,
                "human_feedback": None,
            }

        with ctx.timed("planner"):
            plan_result = self.planner.create_plan(query)
            ctx.increment("llm_calls")

        ctx.log(
            "planner",
            "created_plan",
            task_count=len(plan_result["tasks"]),
            model=active_model_label(),
        )
        return {
            "original_query": query,
            "plan": plan_result,
            "tasks": plan_result["tasks"],
            "guardrail_status": {"ok": True, "reasons": [], "findings": guard.findings},
            "messages": [
                AIMessage(
                    content=(
                        f"Enterprise plan created with {len(plan_result['tasks'])} tasks:\n"
                        f"{plan_result['reasoning']}\n"
                        f"Delivery notes: {plan_result.get('delivery_notes', '')}"
                    )
                )
            ],
            "agent_history": [
                {
                    "agent": "planner",
                    "action": "created_plan",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "task_count": len(plan_result["tasks"]),
                }
            ],
            "iteration_count": 0,
            "requires_human_input": False,
            "human_feedback": None,
        }

    def dispatch_node(
        self, state: MultiAgentState
    ) -> Command[Literal["researcher", "coder", "synthesizer"]]:
        if state.get("final_output") and not state.get("tasks"):
            return Command(goto="synthesizer")
        route = next_route_after_plan(state)
        print(f"\n[Dispatch] Routing to: {route}")
        self._ctx(state).log("dispatch", "route", route=route)
        return Command(goto=route)

    def research_node(self, state: MultiAgentState) -> dict:
        ctx = self._ctx(state)
        print("\n[Researcher] Conducting enterprise research...")
        tasks = list(state.get("tasks", []))
        current_task_id = state.get("current_task_id")

        if current_task_id:
            task = next((item for item in tasks if item["id"] == current_task_id), None)
            role = getattr(task.get("assigned_to"), "value", task.get("assigned_to")) if task else None
            status = getattr(task.get("status"), "value", task.get("status")) if task else None
            if role != AgentRole.RESEARCHER.value:
                task = None
            elif status not in {
                TaskStatus.PENDING.value,
                TaskStatus.NEEDS_REVIEW.value,
                TaskStatus.IN_PROGRESS.value,
            }:
                task = None
        else:
            task = None

        if not task:
            pending = pending_tasks(tasks, AgentRole.RESEARCHER)
            task = pending[0] if pending else None

        if not task:
            return {"messages": [AIMessage(content="No research tasks pending.")]}

        task_update = {**task, "status": TaskStatus.IN_PROGRESS}
        with ctx.timed("researcher"):
            result = self.researcher.research(task_update, self._build_context(state))
            ctx.increment("llm_calls")

        completed = {
            **task_update,
            "status": result["status"],
            "result": result.get("findings"),
            "completed_at": result.get("timestamp"),
        }
        ctx.log(
            "researcher",
            "researched",
            task_id=task["id"],
            task_status=str(result.get("status")),
            sources=len(result.get("sources") or []),
        )
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
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }

    def coding_node(self, state: MultiAgentState) -> dict:
        ctx = self._ctx(state)
        print("\n[Coder] Generating enterprise-grade code...")
        tasks = list(state.get("tasks", []))
        pending = pending_tasks(tasks, AgentRole.CODER)
        if not pending:
            return {"messages": [AIMessage(content="No coding tasks pending.")]}

        task = pending[0]
        task_update = {**task, "status": TaskStatus.IN_PROGRESS}
        with ctx.timed("coder"):
            result = self.coder.generate_code(task_update, self._build_context(state))
            ctx.increment("llm_calls")

        completed = {
            **task_update,
            "status": result["status"],
            "result": result.get("code"),
            "completed_at": result.get("timestamp"),
        }
        ctx.log(
            "coder",
            "coded",
            task_id=task["id"],
            task_status=str(result.get("status")),
            language=result.get("language"),
        )
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
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }

    def review_node(
        self, state: MultiAgentState
    ) -> Command[Literal["researcher", "coder", "synthesizer"]]:
        ctx = self._ctx(state)
        print("\n[Reviewer] Enterprise quality + compliance review...")
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

        role = getattr(task.get("assigned_to"), "value", task.get("assigned_to"))
        policy = evaluate_work_product(str(role), work_product)
        policy_notes = ""
        if policy.violations or policy.warnings:
            policy_notes = "\n".join(
                [f"VIOLATION: {v}" for v in policy.violations]
                + [f"WARNING: {w}" for w in policy.warnings]
            )

        with ctx.timed("reviewer"):
            review_result = self.reviewer.review(
                task,
                work_product,
                self._build_context(state),
                policy_notes=policy_notes,
            )
            ctx.increment("llm_calls")

        review_result = apply_policy_to_review(review_result, policy)
        if policy.violations:
            ctx.increment("policy_violations", len(policy.violations))

        iteration = int(state.get("iteration_count") or 0) + 1
        human_feedback = state.get("human_feedback")

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
                    "policy_violations": policy.violations,
                    "prompt": (
                        "Enterprise reviewer requested changes. "
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
        task_update = {**task, "status": task_status}
        update = {
            "tasks": [task_update],
            "review_feedback": [review_result],
            "iteration_count": iteration,
            "requires_human_input": not review_result.get("approved"),
            "human_feedback": human_feedback,
            "policy_violations": list(policy.violations),
            "messages": [
                AIMessage(
                    content=(
                        "Enterprise review: "
                        + (
                            "Approved"
                            if review_result.get("approved")
                            else "Needs Revision"
                        )
                        + f" (score={review_result.get('score')})"
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
                    "score": review_result.get("score"),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            ],
        }

        # Merge task updates before routing so sibling pending tasks remain visible
        merged_tasks = upsert_tasks(state.get("tasks", []), update.get("tasks", []))
        route_state = {**state, **update, "tasks": merged_tasks}
        route = next_route_after_review(route_state)
        print(f"\n[Reviewer] Next route: {route}")
        ctx.log(
            "reviewer",
            "reviewed",
            task_id=current_task_id,
            approved=review_result.get("approved"),
            score=review_result.get("score"),
            next_route=route,
        )
        return Command(update=update, goto=route)

    def synthesize_node(self, state: MultiAgentState) -> dict:
        ctx = self._ctx(state)
        print("\n[Synthesizer] Creating enterprise final output...")

        # Early exit when input was blocked
        if state.get("final_output") and not state.get("tasks"):
            report = ctx.finalize()
            return {
                "run_metadata": report,
                "metrics": report["metrics"],
                "compliance": {
                    "verdict": "blocked",
                    "checklist": list(ENTERPRISE_POLICY_CHECKLIST),
                },
            }

        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", SYNTHESIZER_SYSTEM_PROMPT),
                (
                    "human",
                    "Original Query: {query}\n\n"
                    "Research Findings:\n{research}\n\n"
                    "Code Artifacts:\n{code}\n\n"
                    "Review Feedback:\n{reviews}\n\n"
                    "Policy violations:\n{violations}\n\n"
                    "Create a comprehensive enterprise final answer.",
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
                f"Usage: {item.get('usage', '')}\n"
                f"Security: {item.get('security_notes', '')}"
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
        violations = state.get("policy_violations") or []

        with ctx.timed("synthesizer"):
            try:
                response = with_retry(
                    lambda: (prompt | get_llm(temperature=0.2)).invoke(
                        {
                            "query": state.get("original_query", ""),
                            "research": research_str or "None",
                            "code": code_str or "None",
                            "reviews": reviews_str or "None",
                            "violations": "\n".join(violations) or "None",
                        }
                    ),
                    operation="synthesizer",
                )
                ctx.increment("llm_calls")
                final_output = response.content
            except Exception as exc:  # noqa: BLE001
                final_output = (
                    f"# Final Output (fallback)\n\n"
                    f"Query: {state.get('original_query', '')}\n\n"
                    f"## Research\n{research_str or 'None'}\n\n"
                    f"## Code\n{code_str or 'None'}\n\n"
                    f"## Reviews\n{reviews_str or 'None'}\n\n"
                    f"_Synthesizer LLM unavailable: {exc}_"
                )

        approved_reviews = [
            item for item in state.get("review_feedback", []) if item.get("approved")
        ]
        compliance_verdict = "pass"
        if violations:
            compliance_verdict = "fail"
        elif not approved_reviews and (
            state.get("research_findings") or state.get("code_artifacts")
        ):
            compliance_verdict = "conditional"

        report = ctx.finalize()
        compliance = {
            "verdict": compliance_verdict,
            "checklist": list(ENTERPRISE_POLICY_CHECKLIST),
            "approved_reviews": len(approved_reviews),
            "total_reviews": len(state.get("review_feedback", [])),
        }
        ctx.log("synthesizer", "finalized", verdict=compliance_verdict)

        return {
            "final_output": final_output,
            "messages": [AIMessage(content=final_output)],
            "run_metadata": report,
            "metrics": report["metrics"],
            "compliance": compliance,
            "agent_history": [
                {
                    "agent": "synthesizer",
                    "action": "finalized",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "compliance": compliance_verdict,
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
            "policy_checklist": list(ENTERPRISE_POLICY_CHECKLIST),
        }

    def _initial_state(self, query: str) -> MultiAgentState:
        self._run_ctx = RunContext()
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
            "policy_violations": [],
            "requires_human_input": False,
            "human_feedback": None,
            "run_id": self._run_ctx.run_id,
            "run_metadata": {"run_id": self._run_ctx.run_id},
            "metrics": {},
            "compliance": {},
            "guardrail_status": {},
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

    @staticmethod
    def format_report(state: dict) -> str:
        return format_run_report(state)
