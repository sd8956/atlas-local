from pathlib import Path

WORKSPACES_DIR = Path(".workspaces")
WORKSPACE_DIRS = [
    "inputs",
    "evidence/raw/aws",
    "evidence/raw/repository",
    "evidence/normalized",
    "repo",
    "graph",
    "opportunities",
    "ai",
    "reports",
    "remediation",
    "patches",
    "audit",
    "approvals",
    "delivery",
]


def workspace_root(name: str) -> Path:
    safe = name.strip().replace("/", "-").replace("..", "-")
    if not safe:
        raise ValueError("workspace name cannot be empty")
    return WORKSPACES_DIR / safe
