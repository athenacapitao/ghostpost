"""Playbook system — flat markdown templates for common email workflows."""

import logging
import os
import re

from src.db.models import Thread
from src.db.session import async_session

logger = logging.getLogger("ghostpost.engine.playbooks")

PLAYBOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "playbooks")


def _ensure_dir() -> None:
    os.makedirs(PLAYBOOKS_DIR, exist_ok=True)


def list_playbooks() -> list[dict]:
    """List all available playbooks."""
    _ensure_dir()
    playbooks = []
    for fname in sorted(os.listdir(PLAYBOOKS_DIR)):
        if fname.endswith(".md"):
            name = fname[:-3]
            path = os.path.join(PLAYBOOKS_DIR, fname)
            with open(path) as f:
                content = f.read()
            # Extract first line as title (strip # prefix)
            title = content.split("\n")[0].lstrip("# ").strip() if content else name
            playbooks.append({"name": name, "title": title, "path": path})
    return playbooks


def _is_safe_name(name: str) -> bool:
    """Validate playbook name — alphanumeric, hyphens, underscores only."""
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', name))


def get_playbook(name: str) -> dict | None:
    """Get a playbook by name. Returns {name, title, content} or None."""
    if not _is_safe_name(name):
        return None
    path = os.path.join(PLAYBOOKS_DIR, f"{name}.md")
    if not os.path.isfile(path):
        return None
    with open(path) as f:
        content = f.read()
    title = content.split("\n")[0].lstrip("# ").strip() if content else name
    return {"name": name, "title": title, "content": content}


async def apply_playbook(thread_id: int, name: str) -> bool:
    """Apply a playbook to a thread — sets thread.playbook field."""
    playbook = get_playbook(name)
    if not playbook:
        return False

    async with async_session() as session:
        thread = await session.get(Thread, thread_id)
        if not thread:
            return False
        thread.playbook = name
        await session.commit()

    logger.info(f"Applied playbook '{name}' to thread {thread_id}")
    return True


def create_playbook(name: str, content: str) -> dict | None:
    """Create a new playbook. Returns the playbook dict or None if name is invalid/exists."""
    _ensure_dir()
    if not re.match(r'^[a-zA-Z0-9_-]+$', name):
        return None
    path = os.path.join(PLAYBOOKS_DIR, f"{name}.md")
    if os.path.isfile(path):
        return None
    with open(path, "w") as f:
        f.write(content)
    title = content.split("\n")[0].lstrip("# ").strip() if content else name
    logger.info(f"Created playbook '{name}'")
    return {"name": name, "title": title, "content": content}


def update_playbook(name: str, content: str) -> dict | None:
    """Update an existing playbook's content. Returns updated dict or None if not found."""
    if not _is_safe_name(name):
        return None
    path = os.path.join(PLAYBOOKS_DIR, f"{name}.md")
    if not os.path.isfile(path):
        return None
    with open(path, "w") as f:
        f.write(content)
    title = content.split("\n")[0].lstrip("# ").strip() if content else name
    logger.info(f"Updated playbook '{name}'")
    return {"name": name, "title": title, "content": content}


def delete_playbook(name: str) -> bool:
    """Delete a playbook by name. Returns True if deleted, False if not found."""
    if not _is_safe_name(name):
        return False
    path = os.path.join(PLAYBOOKS_DIR, f"{name}.md")
    if not os.path.isfile(path):
        return False
    os.remove(path)
    logger.info(f"Deleted playbook '{name}'")
    return True
