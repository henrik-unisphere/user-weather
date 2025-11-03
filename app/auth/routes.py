from typing import Optional
from authlib.integrations.starlette_client import OAuthError
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates
from typing_extensions import Annotated

from app.auth.oauth import OAuthWrapper
from app.auth.settings import settings
from app.dependencies import get_oauth_wrapper, get_user_repo
from app.schemas.user_model import User
from app.user_alchemy_repo import UserRepository


templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, user_repo: Annotated[UserRepository, Depends(get_user_repo)]) -> HTMLResponse:
    user_data = getattr(request.state, "user", None)
    if not user_data:
        user = {}
    else:
        user = user_repo.repo_get_user(user_data["sub"])
        user = user.model_dump() if user is not None else {}

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
        return await oauth_wrapper.oauth.keycloak.authorize_redirect(request, redirect_uri)

    try:
        token = await oauth_wrapper.oauth.keycloak.authorize_access_token(request)
        print(token)
    except OAuthError as error:
        return HTMLResponse(f"<h1>{error.error}</h1>", status_code=400)

    userinfo = token.get("userinfo") or {}
    refresh_token = token.get("refresh_token")

    response = RedirectResponse(url="/")
    if userinfo:
        response.set_cookie("token", token["id_token"], httponly=True)

    try:
        kc_sub = userinfo.get("sub")  # stabiler OIDC-Identifikator (wichtig!)
        if kc_sub:
            email = (userinfo.get("email") or "").strip().lower()
            first_name = userinfo.get("given_name") or ""
            last_name = userinfo.get("family_name") or ""

            existing = repo.repo_get_user_internal(kc_sub)

            if existing:
                if refresh_token:
                    repo.repo_set_refresh_token(kc_sub, refresh_token)
            else:
                new_user = User(user_id=kc_sub, email=email, first_name=first_name, last_name=last_name)
                try:
                    repo.repo_create_user(new_user, refresh_token=refresh_token)
                except ValueError:
                    pass
    except Exception as e:
        print("Failed to create/sync user:", e)

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

    metadata = await oauth.oauth.keycloak.load_server_metadata()
    end = metadata.get("end_session_endpoint")
    home = settings.APP_BASE_URL
    id_token = request.cookies.get("token")
    response = RedirectResponse(f"{end}?id_token_hint={id_token}&post_logout_redirect_uri={home}/")
    response.delete_cookie("token")
    return response
