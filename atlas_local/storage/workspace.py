from pathlib import Path

from atlas_local.models import Workspace
from atlas_local.storage.jsonio import read_json, write_json
from atlas_local.storage.paths import WORKSPACE_DIRS, workspace_root


class WorkspaceHandle:
    def __init__(self, name: str):
        self.name = name
        self.root = workspace_root(name)

    def path(self, *parts: str) -> Path:
        return self.root.joinpath(*parts)


def create_workspace(name: str) -> WorkspaceHandle:
    root = workspace_root(name)
    root.mkdir(parents=True, exist_ok=True)
    for directory in WORKSPACE_DIRS:
        (root / directory).mkdir(parents=True, exist_ok=True)
    metadata_path = root / "workspace.json"
    if not metadata_path.exists():
        write_json(metadata_path, Workspace(name=name))
    return WorkspaceHandle(name)


def get_workspace(name: str) -> WorkspaceHandle:
    root = workspace_root(name)
    if not (root / "workspace.json").exists():
        raise FileNotFoundError(f"Workspace not found: {name}. Run atlas init-workspace {name}")
    return WorkspaceHandle(name)


def load_workspace(name: str) -> Workspace:
    handle = get_workspace(name)
    return Workspace.model_validate(read_json(handle.path("workspace.json")))
