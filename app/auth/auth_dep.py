from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer


def get_current_user(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_role_premium(request: Request) -> None:
    user = get_current_user(request)  # stellt sicher, dass 401 vorher greift
    if "premium" not in (user.get("roles") or []):
        raise HTTPException(status_code=403, detail="premium role required")


def require_admin(request: Request) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    roles = set(user.get("roles") or [])
    if "admin" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin role required")
    return user


security = HTTPBearer(auto_error=False)


def require_authenticated_user(
    request: Request,
    _: HTTPAuthorizationCredentials | None = Depends(security),
) -> dict:
    user = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user
