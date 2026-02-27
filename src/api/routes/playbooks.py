"""Playbook endpoints — list, get, and apply markdown workflow templates."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from src.api.dependencies import get_current_user
from src.engine.playbooks import (
    apply_playbook,
    create_playbook,
    delete_playbook,
    get_playbook,
    list_playbooks,
    update_playbook,
)

router = APIRouter(prefix="/api/playbooks", tags=["playbooks"])


@router.get("")
async def list_all_playbooks(_user: str = Depends(get_current_user)) -> list[dict]:
    """List all available playbooks."""
    return list_playbooks()


@router.get("/{name}", response_class=PlainTextResponse)
async def get_playbook_content(
    name: str, _user: str = Depends(get_current_user)
) -> str:
    """Get the full markdown content of a playbook by name."""
    playbook = get_playbook(name)
    if not playbook:
        raise HTTPException(status_code=404, detail=f"Playbook '{name}' not found")
    return playbook["content"]


@router.post("/apply/{thread_id}/{name}")
async def apply_playbook_to_thread(
    thread_id: int, name: str, _user: str = Depends(get_current_user)
) -> dict:
    """Apply a playbook to a thread by setting thread.playbook."""
    success = await apply_playbook(thread_id, name)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Thread {thread_id} not found or playbook '{name}' does not exist",
        )
    return {"message": f"Playbook '{name}' applied to thread {thread_id}"}


class PlaybookContent(BaseModel):
    content: str


@router.post("")
async def create_new_playbook(
    name: str, body: PlaybookContent, _user: str = Depends(get_current_user)
) -> dict:
    """Create a new playbook with the given name and markdown content."""
    result = create_playbook(name, body.content)
    if not result:
        raise HTTPException(status_code=400, detail=f"Invalid name or playbook '{name}' already exists")
    return result


@router.put("/{name}")
async def update_existing_playbook(
    name: str, body: PlaybookContent, _user: str = Depends(get_current_user)
) -> dict:
    """Update an existing playbook's content."""
    result = update_playbook(name, body.content)
    if not result:
        raise HTTPException(status_code=404, detail=f"Playbook '{name}' not found")
    return result


@router.delete("/{name}")
async def delete_existing_playbook(
    name: str, _user: str = Depends(get_current_user)
) -> dict:
    """Delete a playbook by name."""
    success = delete_playbook(name)
    if not success:
        raise HTTPException(status_code=404, detail=f"Playbook '{name}' not found")
    return {"message": f"Playbook '{name}' deleted"}
