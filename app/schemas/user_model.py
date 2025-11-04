from pydantic import BaseModel, field_validator, EmailStr
from typing import Optional
from typing import Literal


class User(BaseModel):
    first_name: str
    last_name: str
    email: EmailStr
    user_id: str
    is_premium: bool = False


class UserResponse(BaseModel):
    message: str
    user: User


class UserUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None

    @field_validator("first_name", "last_name")
    @classmethod
    def strip_and_non_empty(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        v = v.strip()
        if not v:
            raise ValueError("must not be blank")
        return v


class UserNames(BaseModel):
    first_name: str
    last_name: str


class RoleChangeRequest(BaseModel):
    user_id: str
    role: Literal["premium", "admin"]
    action: Literal["add", "remove"]

    @field_validator("user_id")
    @classmethod
    def non_blank(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("user_id must not be blank")
        return v
