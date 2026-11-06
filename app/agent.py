"""Agent factory. Later sessions extend build_agent() (tools, subagents, memory, ...)."""
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
from langchain.agents.middleware import TodoListMiddleware
from langgraph.graph.state import CompiledStateGraph

from app.config import Settings, load_settings
from app.prompts import manager_prompt
from app.tools import build_web_search_tool


def build_backend(settings: Settings) -> FilesystemBackend:
    """Single backend confined to workspace/ (virtual_mode rejects paths outside it)."""
    return FilesystemBackend(root_dir=settings.workspace_dir, virtual_mode=True)


def build_agent(settings: Settings | None = None) -> CompiledStateGraph:
    """Create the Deep Agent with the configured model, backend and recursion limit."""
    settings = settings or load_settings()
    agent = create_deep_agent(
        model=settings.model,
        system_prompt=manager_prompt(),
        middleware=[TodoListMiddleware()],
        backend=build_backend(settings),
        tools=[build_web_search_tool(settings)],
    )
    return agent.with_config({"recursion_limit": settings.recursion_limit})
