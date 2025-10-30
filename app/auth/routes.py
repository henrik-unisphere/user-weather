from typing_extensions import Annotated
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.templating import Jinja2Templates
from authlib.integrations.starlette_client import OAuthError
from app.auth.dependencies import get_oauth_wrapper, get_user_repo
from app.auth.oauth import OAuthWrapper
from app.auth.settings import settings
from app.schemas.user_model import User
from app.user_alchemy_repo import UserRepository

templates = Jinja2Templates(directory="app/templates")
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
async def home(request: Request, user_repo: Annotated[UserRepository, Depends(get_user_repo)]) -> HTMLResponse:
    user_data = getattr(request.state, "user", None)

    user = user_repo.repo_get_user(user_data["sub"]) if user_data is not None else None

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

    userinfo = token.get("userinfo")
    refresh_token = token.get("refresh_token")
    response = RedirectResponse(url="/")
    if userinfo:
        response.set_cookie("token", token["id_token"], httponly=True)

    try:
        kc_sub = userinfo.get("sub")  # stabiler OIDC-Identifikator (wichtig!)
        email = userinfo.get("email") or ""
        first_name = userinfo.get("given_name") or ""
        last_name = userinfo.get("family_name") or ""

        if kc_sub:
            existing = repo.repo_get_user(kc_sub)
            if not existing:
                new_user = User(
                    user_id=kc_sub,
                    email=email,
                    first_name=first_name,
                    last_name=last_name,
                )
                try:
                    repo.repo_create_user(new_user)
                except ValueError:
                    pass
    except Exception as e:
        print("Failed to create/sync user:", e)

    return response


@router.get("/logout")
async def logout(request: Request) -> RedirectResponse:
    oauth = request.app.state.oauth
    metadata = await oauth.keycloak.load_server_metadata()
    end = metadata.get("end_session_endpoint")
    home = settings.APP_BASE_URL
    id_token = request.cookies.get("token")
    response = RedirectResponse(f"{end}?id_token_hint={id_token}&post_logout_redirect_uri={home}/")
    response.delete_cookie("token")
    return response
