"""Shared utility for loading API keys from .env or environment."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def load_api_key(key_name: str, repo_root: Optional[Path] = None) -> str:
    """Load an API key from .env file (if repo_root given) or environment variable."""
    if repo_root:
        env_path = repo_root / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if line.startswith(f"{key_name}="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    key = os.environ.get(key_name, "")
    if not key:
        raise RuntimeError(f"{key_name} not found in .env or environment")
    return key
