from pydantic import FilePath
from app.user_repository import UserRepository

APP_DIR = FilePath(__file__).resolve().parent  # .../app
DATA_PATH = APP_DIR / "test_data" / "test_users.json"


def test_empty_user_repo() -> None:
    repo = UserRepository(DATA_PATH)
    assert repo.repo_list_users() == []
