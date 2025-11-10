from fastapi import Depends

from app.auth.oauth import OAuthWrapper
from app.core.settings import settings
from app.database.user_alchemy_repo import UserRepository

_user_repo = UserRepository(settings.DATABASE_URL)
_oauth_wrapper = None


def get_user_repo() -> UserRepository:
    return _user_repo


def get_oauth_wrapper(db_repo: UserRepository = Depends(get_user_repo)) -> OAuthWrapper:
    global _oauth_wrapper
    if _oauth_wrapper is not None:
        print("return oauth wrapper")
        return _oauth_wrapper
    _oauth_wrapper = OAuthWrapper(db_repo)
    print("create oauth wrapper")
    return _oauth_wrapper
