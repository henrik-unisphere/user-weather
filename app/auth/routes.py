from typing import Optional
from urllib.parse import urlencode
from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates
from typing_extensions import Annotated

from app.auth.oauth import OAuthWrapper
from app.core.settings import settings
from app.core.dependencies import get_oauth_wrapper, get_user_repo
from app.schemas.user_model import User
from app.database.user_alchemy_repo import UserRepository


templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, user_repo: Annotated[UserRepository, Depends(get_user_repo)]) -> HTMLResponse:
    user_data = getattr(request.state, "user", None)
    print(f"=== HOME: user_data from middleware: {user_data}")
    if not user_data:
        user = {}
    else:
        try:
            user_db = user_repo.repo_get_user(user_data["sub"])
            print(f"=== HOME: user from DB: {user_db}")
            if user_db is not None:
                user = user_db.model_dump()
            else:
                # User authenticated but not in DB - use data from token
                user = {
                    "user_id": user_data["sub"],
                    "email": user_data.get("email", ""),
                    "first_name": "",
                    "last_name": "",
                    "name": user_data.get("name", ""),
                }
        except Exception as e:
            print(f"=== HOME: Error fetching user: {e}")
            # Fallback to token data
            user = {
                "user_id": user_data["sub"],
                "email": user_data.get("email", ""),
                "first_name": "",
                "last_name": "",
                "name": user_data.get("name", ""),
            }

    print(f"=== HOME: Final user object: {user}")
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "user": user},
    )


@router.get("/auth")
async def auth(
    request: Request,
    repo: UserRepository = Depends(get_user_repo),
    oauth_wrapper: OAuthWrapper = Depends(get_oauth_wrapper),
) -> RedirectResponse:
    if "code" not in request.query_params:
        redirect_uri = f"{settings.APP_BASE_URL}/auth"
        return await oauth_wrapper.oauth.zitadel.authorize_redirect(request, redirect_uri)

    try:
        token = await oauth_wrapper.oauth.zitadel.authorize_access_token(request)
    except OAuthError as error:
        return HTMLResponse(f"<h1>{error.error}</h1>", status_code=400)

    print(token)

    # Fetch userinfo from Zitadel's userinfo endpoint
    try:
        userinfo = await oauth_wrapper.oauth.zitadel.userinfo(token=token)
        print(f"=== AUTH: Userinfo from Zitadel: {userinfo}")
    except Exception as e:
        print(f"Failed to fetch userinfo: {e}")
        userinfo = token.get("userinfo") or {}

    refresh_token = token.get("refresh_token")
    id_token = token.get("id_token")

    response = RedirectResponse(url="/")
    if id_token:
        response.set_cookie("id_token", id_token, httponly=True)

    # Store or update user in database
    try:
        user_sub = userinfo.get("sub")
        if user_sub:
            email = (userinfo.get("email") or "").strip().lower()
            first_name = userinfo.get("given_name") or ""
            last_name = userinfo.get("family_name") or ""

            # Extract roles from Zitadel userinfo
            zitadel_roles = userinfo.get("urn:zitadel:iam:org:project:roles", {})
            roles = list(zitadel_roles.keys()) if isinstance(zitadel_roles, dict) else []
            is_premium = "premium" in roles

            # Check if user already exists
            existing = repo.repo_get_user_internal(user_sub)

            if existing:
                # User exists - update refresh token and premium status
                print(f"=== AUTH: User {user_sub} already exists, updating refresh token and premium status")
                if refresh_token:
                    repo.repo_set_refresh_token(user_sub, refresh_token)
                repo.repo_set_is_premium(user_sub, is_premium)
                print(f"=== AUTH: User {user_sub} premium status: {is_premium}")
            else:
                # New user - create in database
                print(f"=== AUTH: Creating new user {user_sub}")
                new_user = User(
                    user_id=user_sub,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                    is_premium=is_premium,
                )
                try:
                    repo.repo_create_user(new_user, refresh_token=refresh_token, is_premium=is_premium)
                    print(f"=== AUTH: User {user_sub} created successfully with premium: {is_premium}")
                except ValueError as e:
                    print(f"=== AUTH: User creation failed: {e}")
    except Exception as e:
        print(f"=== AUTH: Failed to create/sync user: {e}")

    return response


@router.get("/logout")
async def logout(
    request: Request, oauth: OAuthWrapper = Depends(get_oauth_wrapper), repo: UserRepository = Depends(get_user_repo)
) -> RedirectResponse:
    sub: Optional[str] = None
    if getattr(request.state, "user", None):
        sub = request.state.user.get("sub")
    if sub:
        try:
            repo.repo_set_refresh_token(sub, None)
        except Exception:
            pass

    metadata = await oauth.oauth.zitadel.load_server_metadata()
    end = metadata.get("end_session_endpoint")
    home = settings.APP_BASE_URL
    params = {
        "post_logout_redirect_uri": f"{home}/",
        "client_id": settings.ZITADEL_CLIENT_ID,
    }
    resp = RedirectResponse(f"{end}?{urlencode(params)}")
    resp.delete_cookie("id_token")
    return resp
