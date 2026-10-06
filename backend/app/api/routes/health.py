from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["health"])


class Health(BaseModel):
    status: str


@router.get("/health")
def health() -> Health:
    """Está vivo? Sem login e sem banco: só diz que o processo responde."""
    return Health(status="ok")
