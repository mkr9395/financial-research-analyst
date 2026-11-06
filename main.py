"""Minimal runner: python main.py "your request". The full CLI comes in Session 10."""
import sys

from app.agent import build_agent
from app.config import ConfigError, load_settings


def run(request: str) -> str:
    """Invoke the agent with the request and return the final answer text."""
    settings = load_settings()
    agent = build_agent(settings)
    result = agent.invoke({"messages": [{"role": "user", "content": request}]})
    return result["messages"][-1].text


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit('Usage: python main.py "your request"')
    try:
        print(run(" ".join(sys.argv[1:])))
    except ConfigError as error:
        sys.exit(f"Configuration error: {error}")
