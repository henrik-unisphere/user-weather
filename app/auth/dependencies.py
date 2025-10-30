from typing import Annotated
from fastapi import Depends
from app.auth.settings import settings
from app.auth.oauth import OAuthWrapper
from app.user_alchemy_repo import UserRepository

_user_repo = UserRepository(settings.DATABASE_URL)
_oauth_wrapper = None


def get_user_repo():
    return _user_repo


def get_oauth_wrapper(db_repo: Annotated[UserRepository, Depends(get_user_repo)]):
    global _oauth_wrapper
    if _oauth_wrapper is not None:
        print("return oauth wrapper")
        return _oauth_wrapper
    _oauth_wrapper = OAuthWrapper(db_repo)
    print("create oauth wrapper")
    return _oauth_wrapper
