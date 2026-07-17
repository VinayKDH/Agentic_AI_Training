from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage
from typing import Dict, Any, List, Optional, TypedDict, Annotated
from operator import add
import time
import uuid
from datetime import datetime

from app.config import settings
from app.constants import (
    AGENT_PROMPT_TEMPLATE,
    LLM_PROVIDER_OPENAI,
    LLM_PROVIDER_VERTEX,
)


class AgentState(TypedDict, total=False):
    messages: Annotated[List[BaseMessage], add]
    query: str
    response: str


def _build_llm():
    provider = settings.LLM_PROVIDER.lower().strip()

    if provider == LLM_PROVIDER_VERTEX:
        from langchain_google_vertexai import ChatVertexAI

        return ChatVertexAI(
            model_name=settings.VERTEX_MODEL,
            project=settings.GCP_PROJECT,
            location=settings.VERTEX_LOCATION,
            temperature=settings.OPENAI_TEMPERATURE,
            max_output_tokens=settings.OPENAI_MAX_TOKENS,
        )

    if provider == LLM_PROVIDER_OPENAI:
        from langchain_openai import ChatOpenAI

        if not settings.OPENAI_API_KEY:
            raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER=openai")

        return ChatOpenAI(
            model=settings.OPENAI_MODEL,
            temperature=settings.OPENAI_TEMPERATURE,
            api_key=settings.OPENAI_API_KEY,
        )

    raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")


class AgentService:
    def __init__(self):
        self.llm = _build_llm()
        self.memory = MemorySaver()
        self.graph = self._build_graph()
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self._agent_node)
        workflow.set_entry_point("agent")
        workflow.add_edge("agent", END)
        return workflow.compile(checkpointer=self.memory)

    def _agent_node(self, state: AgentState) -> AgentState:
        messages = state.get("messages", [])
        user_message = None
        for msg in reversed(messages):
            if isinstance(msg, HumanMessage):
                user_message = msg.content
                break

        if not user_message:
            user_message = state.get("query", "")

        prompt = AGENT_PROMPT_TEMPLATE.format(user_message=user_message)
        response = self.llm.invoke(prompt)
        return {
            "messages": [AIMessage(content=response.content)],
            "response": response.content,
        }

    async def process_query(
        self,
        query: str,
        session_id: Optional[str] = None,
        max_iterations: int = 10,
    ) -> Dict[str, Any]:
        start_time = time.time()

        if not session_id:
            session_id = str(uuid.uuid4())

        if session_id not in self.sessions:
            self.sessions[session_id] = {
                "created_at": datetime.now().isoformat(),
                "message_count": 0,
            }

        config = {"configurable": {"thread_id": session_id}}
        initial_state: AgentState = {
            "messages": [HumanMessage(content=query)],
            "query": query,
        }

        try:
            result = self.graph.invoke(initial_state, config)
            execution_time = time.time() - start_time

            self.sessions[session_id]["message_count"] += 1
            self.sessions[session_id]["last_activity"] = datetime.now().isoformat()

            return {
                "response": result.get("response", ""),
                "session_id": session_id,
                "execution_time": execution_time,
                "metadata": {
                    "message_count": self.sessions[session_id]["message_count"],
                    "iterations": 1,
                    "llm_provider": settings.LLM_PROVIDER,
                    "model": (
                        settings.VERTEX_MODEL
                        if settings.LLM_PROVIDER == LLM_PROVIDER_VERTEX
                        else settings.OPENAI_MODEL
                    ),
                },
            }
        except Exception as e:
            raise Exception(f"Agent execution failed: {str(e)}") from e


agent_service = AgentService()
