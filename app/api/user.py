from fastapi import APIRouter, HTTPException, Path as PathParam, status, Depends
from pydantic import EmailStr
from user_repository import UserRepository
from schemas.user_model import User, UserResponse, UserUpdate, UserNames
from typing import List
from pathlib import Path as FilePath

APP_DIR = FilePath(__file__).resolve().parent.parent  # .../app
DATA_PATH = APP_DIR / "data" / "users.json"
dev_repo = UserRepository(DATA_PATH)


def get_repo() -> UserRepository:
    return dev_repo


router = APIRouter(prefix="/users", tags=["user"])


@router.post(
    "",
    response_model=UserResponse,
    summary="Create a new User",
    description="Add a new user to the fake database",
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {
            "content": {
                "application/json": {
                    "example": {
                        "message": "User successfully created",
                        "user": {
                            "first_name": "John",
                            "last_name": "Doe",
                            "email": "john.doe@example.com",
                        },
                    }
                }
            }
        },
        409: {"description": "User with this email already exists"},
        400: {
            "description": "Bad Request",
            "content": {"application/json": {"example": {"detail": "first_name must not be blank"}}},
        },
        422: {"description": "Validation Error (auto by FastAPI)"},
        500: {"description": "Internal Server Error"},
    },
)
def create_user(user: User, repo: UserRepository = Depends(get_repo)) -> UserResponse:
    try:
        u = repo.repo_create_user(user)
    except ValueError:  # conflict
        raise HTTPException(status_code=409, detail="User with this email already exists")
    return UserResponse(message="User successfully created", user=u)


@router.get(
    "",
    response_model=List[User],
    summary="List all users",
    description="Gibt alle aktuell im Speicher vorhandenen User zurück.",
)
def list_users(repo: UserRepository = Depends(get_repo)) -> list[User]:
    return repo.repo_list_users()


@router.get(
    "/{email}",
    response_model=User,
    summary="Returns User",
    description="Rückgabe von gefordertem User",
)
def get_user(
    email: EmailStr = PathParam(..., description="email des Users"),
    repo: UserRepository = Depends(get_repo),
) -> User:
    u = repo.repo_get_user(email)  # <-- email übergeben
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return u


@router.patch("/{email}", response_model=UserResponse)
def update_user(
    email: EmailStr = PathParam(..., description="E-Mail des Users"),
    data: UserUpdate = ...,
    repo: UserRepository = Depends(get_repo),
) -> UserResponse:
    try:
        u = repo.repo_patch_user(email, data)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Provide at least one of first_name or last_name")
    return UserResponse(message="User successfully updated", user=u)


@router.delete(
    "/{email}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete user by email",
    responses={
        200: {"description": "Deleted"},
        404: {"description": "User not found"},
        422: {"description": "Validation error"},
    },
)
def delete_user(
    email: EmailStr = PathParam(..., description="E-Mail des Users"), repo: UserRepository = Depends(get_repo)
) -> UserResponse:
    try:
        u = repo.repo_delete_user(email)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(message="User successfully deleted", user=u)


@router.put("/{email}", response_model=UserResponse, summary="Replace user's names")
def override_user(
    email: EmailStr = PathParam(..., description="E-Mail des Users"),
    data: UserNames = ...,
    repo: UserRepository = Depends(get_repo),
) -> UserResponse:
    try:
        u = repo.repo_replace_user(email, data)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="first_name and last_name must not be blank")
    return UserResponse(message="User successfully replaced", user=u)
