from pathlib import Path
import pytest
from app.user_repository import UserRepository
from app.schemas.user_model import User


@pytest.fixture
def empty_repo(tmp_path: Path) -> UserRepository:
    """Leeres Repo mit frischer users.json im Temp-Ordner."""
    return UserRepository(tmp_path / "users.json")


@pytest.fixture
def filled_repo(tmp_path: Path) -> UserRepository:
    """Repo mit 2 vorab angelegten Usern."""
    repo = UserRepository(tmp_path / "users.json")
    repo.repo_create_user(User(first_name="Ada", last_name="Lovelace", email="ada@ex.com"))
    repo.repo_create_user(User(first_name="Alan", last_name="Turing", email="alan@ex.com"))
    return repo
