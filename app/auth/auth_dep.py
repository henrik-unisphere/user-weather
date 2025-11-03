from fastapi import HTTPException, Request, status


def get_current_user(request: Request):  # noqa: ANN201
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_role_premium(request: Request) -> None:
    user = get_current_user(request)  # stellt sicher, dass 401 vorher greift
    roles = set(user.get("roles") or [])
    if "premium" not in roles:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="premium role required")
