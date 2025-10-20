from app.user_repository import UserRepository
from app.schemas.user_model import User, UserUpdate, UserNames
import pytest


def test_empty_user_repo(empty_repo: UserRepository) -> None:
    assert empty_repo.repo_list_users() == []


def test_list_users_filled(filled_repo: UserRepository) -> None:
    users = filled_repo.repo_list_users()
    assert len(users) == 2
    emails = {u.email for u in users}
    assert {"ada@ex.com", "alan@ex.com"} <= emails


def test_create_conflict(filled_repo: UserRepository) -> None:
    with pytest.raises(ValueError):
        filled_repo.repo_create_user(User(first_name="Ada2", last_name="L", email="ADA@EX.COM"))


def test_patch_user(filled_repo: UserRepository) -> None:
    upd = UserUpdate(first_name="  Augusta  ")
    u = filled_repo.repo_patch_user("ada@ex.com", upd)
    assert u.first_name == "Augusta"
    assert u.last_name == "Lovelace"


def test_replace_and_delete(empty_repo: UserRepository) -> None:
    empty_repo.repo_create_user(User(first_name="A", last_name="B", email="x@y.com"))
    replaced = empty_repo.repo_replace_user("x@y.com", UserNames(first_name="Y", last_name="Z"))
    assert (replaced.first_name, replaced.last_name) == ("Y", "Z")
    deleted = empty_repo.repo_delete_user("x@y.com")
    assert deleted.email == "x@y.com"
    assert empty_repo.repo_get_user("x@y.com") is None
