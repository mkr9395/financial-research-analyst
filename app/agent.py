"""Agent factory. Later sessions extend build_agent() (tools, subagents, memory, ...)."""
from deepagents import create_deep_agent
from langchain.agents.middleware import TodoListMiddleware
from langgraph.graph.state import CompiledStateGraph

from app.backend import build_backend
from app.config import Settings, load_settings
from app.prompts import manager_prompt
from app.subagents import SKILLS_SOURCE, build_subagents
from app.tools import build_web_search_tool



def build_agent(settings: Settings | None = None) -> CompiledStateGraph:
    """Create the Deep Agent with the configured model, backend and recursion limit."""
    settings = settings or load_settings()
    search_tool = build_web_search_tool(settings)
    agent = create_deep_agent(
        model=settings.model,
        system_prompt=manager_prompt(),
        middleware=[TodoListMiddleware()],
        backend=build_backend(settings),
        tools=[],
        subagents=build_subagents(search_tool),
        skills=[SKILLS_SOURCE],
    )
    return agent.with_config({"recursion_limit": settings.recursion_limit})
