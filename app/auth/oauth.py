from typing import Tuple
import httpx
from authlib.integrations.starlette_client import OAuth
from authlib.jose import JsonWebKey, KeySet, jwt

from app.core.settings import settings
from app.database.user_alchemy_repo import UserRepository


class OAuthWrapper:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo
        self._jwks: KeySet | None = None
        self.oauth = OAuth()
        self.oauth.register(
            name="zitadel",
            server_metadata_url=f"{settings.ZITADEL_ISSUER}/.well-known/openid-configuration",
            client_id=settings.ZITADEL_CLIENT_ID,
            client_secret=settings.ZITADEL_CLIENT_SECRET,
            client_kwargs={
                "scope": "openid email profile offline_access",
            },
        )

    async def get_jwks(self) -> KeySet:
        if self._jwks is not None:
            return self._jwks

        async with httpx.AsyncClient() as client:
            disc = await client.get(f"{settings.ZITADEL_ISSUER}/.well-known/openid-configuration")
            disc.raise_for_status()
            discovery = disc.json()

            jwks_resp = await client.get(discovery["jwks_uri"])
            jwks_resp.raise_for_status()

            self._jwks = JsonWebKey.import_key_set(jwks_resp.json())
        return self._jwks

    async def attempt_refresh(self, user_id: str) -> Tuple[dict, str]:
        try:
            user_row = self.repo.repo_get_user_internal(user_id)
        except Exception as e:
            print("DB lookup for refresh_token failed:", e)
            return None

        if not user_row or not user_row.refresh_token:
            return None

        try:
            metadata = await self.oauth.zitadel.load_server_metadata()
            token_endpoint_url = metadata.get("token_endpoint")
            print(f"das ist der refresh endpoint: {token_endpoint_url}")
            print(f"das auch richtig {user_row.refresh_token}")
            # Include client_secret for confidential clients (authorization code flow)
            data = {
                "client_id": f"{settings.ZITADEL_CLIENT_ID}",
                "client_secret": settings.ZITADEL_CLIENT_SECRET,
                "grant_type": "refresh_token",
                "refresh_token": user_row.refresh_token,
            }
            print(f"das bekommt zitadel: {data}")
            async with httpx.AsyncClient() as client:
                disc = await client.post(token_endpoint_url, data=data)
                if disc.status_code != 200:
                    print(f"=== REFRESH ERROR: Status {disc.status_code}")
                    print(f"=== REFRESH ERROR: Response body: {disc.text}")
                disc.raise_for_status()
                result = disc.json()

        except Exception as e:
            print("Token refresh failed:", e)
            return None

        # Erwartet: new_token hat wieder id_token, access_token, evtl. neuen refresh_token
        new_id_token = result.get("id_token")
        new_refresh_token = result.get("refresh_token")

        if not new_id_token:
            return None

        # 4. Neues id_token validieren und premium status aktualisieren
        try:
            new_claims = jwt.decode(new_id_token, await self.get_jwks())
            new_claims.validate()

            # Extract Zitadel roles and update premium status
            zitadel_roles = new_claims.get("urn:zitadel:iam:org:project:roles", {})
            roles = list(zitadel_roles.keys()) if isinstance(zitadel_roles, dict) else []
            is_premium = "premium" in roles

            try:
                self.repo.repo_set_is_premium(user_id, is_premium)
                print(f"=== REFRESH: Updated premium status to {is_premium} for user {user_id}")
            except Exception as e:
                print(f"Failed to update is_premium: {e}")

        except Exception as e:
            print("Refreshed token invalid:", e)
            return None

        # 5. Refresh-Token ggf. rotieren (store new refresh token if Zitadel rotates it)
        if new_refresh_token:
            try:
                # user_id is the function parameter from attempt_refresh
                self.repo.repo_set_refresh_token(user_id, new_refresh_token)
                print(f"=== REFRESH: Updated refresh token for user {user_id}")
            except Exception as e:
                print(f"Failed to update refresh token in DB: {e}")

        # 6. return an dispatch()
        print(f"=== REFRESH: Successfully refreshed token for user {user_id}")
        return (new_claims, new_id_token)
