from fastapi import HTTPException, Request, status


def get_current_user(request: Request):  # noqa: ANN201
    user = getattr(request.state, "user", None)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user
