"""The single filesystem backend, confined to workspace/."""
from deepagents.backends import FilesystemBackend

from app.config import Settings


def build_backend(settings: Settings) -> FilesystemBackend:
    """Single backend confined to workspace/ (virtual_mode rejects paths outside it)."""
    return FilesystemBackend(root_dir=settings.workspace_dir, virtual_mode=True)
