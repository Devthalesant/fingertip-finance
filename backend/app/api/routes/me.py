from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import CurrentUserDep

router = APIRouter(tags=["me"])


class Me(BaseModel):
    email: str
    display_name: str | None
    is_admin: bool


@router.get("/me")
def read_me(user: CurrentUserDep) -> Me:
    return Me(email=user.email, display_name=user.display_name, is_admin=user.is_admin)
