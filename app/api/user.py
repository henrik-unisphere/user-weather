from fastapi import APIRouter, HTTPException, Path as PathParam, status, Depends
from typing import List
from app.schemas.user_model import User, UserResponse, UserUpdate, UserNames
from app.auth.settings import settings
from app.user_alchemy_repo import UserRepository

db_repo = UserRepository(settings.DATABASE_URL)


def get_repo() -> UserRepository:
    return db_repo


router = APIRouter(prefix="/users", tags=["user"])


@router.post(
    "",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new User",
)
def create_user(user: User, repo: UserRepository = Depends(get_repo)) -> UserResponse:
    try:
        u = repo.repo_create_user(user)
    except ValueError:
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
    "/{user_id}",
    response_model=User,
    summary="Returns User by ID",
    description="Rückgabe von gefordertem User (user_id = Keycloak sub)",
)
def get_user(
    user_id: str = PathParam(..., description="User-ID (Keycloak sub)"),
    repo: UserRepository = Depends(get_repo),
) -> User:
    u = repo.repo_get_user(user_id)
    if not u:
        raise HTTPException(status_code=404, detail="User not found")
    return u


@router.patch(
    "/{user_id}",
    response_model=UserResponse,
    summary="Partially update user's names",
)
def update_user(
    user_id: str = PathParam(..., description="User-ID (Keycloak sub)"),
    data: UserUpdate = ...,
    repo: UserRepository = Depends(get_repo),
) -> UserResponse:
    try:
        u = repo.repo_patch_user(user_id, data)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="Provide at least one of first_name or last_name")
    return UserResponse(message="User successfully updated", user=u)


@router.delete(
    "/{user_id}",
    response_model=UserResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete user by ID",
)
def delete_user(
    user_id: str = PathParam(..., description="User-ID (Keycloak sub)"),
    repo: UserRepository = Depends(get_repo),
) -> UserResponse:
    try:
        u = repo.repo_delete_user(user_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found")
    return UserResponse(message="User successfully deleted", user=u)


@router.put(
    "/{user_id}",
    response_model=UserResponse,
    summary="Replace user's names",
)
def override_user(
    user_id: str = PathParam(..., description="User-ID (Keycloak sub)"),
    data: UserNames = ...,
    repo: UserRepository = Depends(get_repo),
) -> UserResponse:
    try:
        u = repo.repo_replace_user(user_id, data)
    except KeyError:
        raise HTTPException(status_code=404, detail="User not found")
    except ValueError:
        raise HTTPException(status_code=400, detail="first_name and last_name must not be blank")
    return UserResponse(message="User successfully replaced", user=u)
