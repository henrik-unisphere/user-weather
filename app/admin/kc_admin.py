import httpx
from urllib.parse import urlparse
from fastapi import HTTPException
from app.core.settings import settings

# Build URLs from env
KC_REALM = settings.KEYCLOAK_REALM
KC_BASE = settings.KEYCLOAK_BASE.rstrip("/")

TOKEN_URL = f"{KC_BASE}/realms/{KC_REALM}/protocol/openid-connect/token"
ADMIN_API = f"{KC_BASE}/admin/realms/{KC_REALM}"


# ------------------------------------------------------------
# Admin Token (Client Credentials)
# ------------------------------------------------------------
async def get_admin_access_token() -> str:
    data = {
        "grant_type": "client_credentials",
        "client_id": settings.KEYCLOAK_ADMIN_CLIENT_ID,
        "client_secret": settings.KEYCLOAK_ADMIN_CLIENT_SECRET,
    }
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(TOKEN_URL, data=data)
        if r.status_code != 200:
            raise HTTPException(502, f"failed to obtain admin token: {r.text}")
        return r.json().get("access_token") or ""


# ------------------------------------------------------------
# Role helpers
# ------------------------------------------------------------
async def fetch_role_repr(role_name: str, admin_token: str) -> dict:
    headers = {"Authorization": f"Bearer {admin_token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{ADMIN_API}/roles/{role_name}", headers=headers)
        if r.status_code == 404:
            raise HTTPException(404, f"role not found: {role_name}")
        if r.status_code != 200:
            raise HTTPException(502, f"failed to fetch role: {r.text}")
        return r.json()


async def add_realm_role_to_user(user_id: str, role: dict, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    payload = [{"id": role["id"], "name": role["name"]}]
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.post(
            f"{ADMIN_API}/users/{user_id}/role-mappings/realm",
            headers=headers,
            json=payload,
        )
        if r.status_code not in (204, 201):
            raise HTTPException(502, f"failed to assign role: {r.text}")


async def remove_realm_role_from_user(user_id: str, role: dict, admin_token: str):
    headers = {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}
    payload = [{"id": role["id"], "name": role["name"]}]
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.request(
            "DELETE",
            f"{ADMIN_API}/users/{user_id}/role-mappings/realm",
            headers=headers,
            json=payload,
        )
        if r.status_code not in (204, 200):
            raise HTTPException(502, f"failed to remove role: {r.text}")


# ------------------------------------------------------------
# Client helpers
# ------------------------------------------------------------
async def _find_client_uuid(client_id: str, token: str) -> str | None:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{ADMIN_API}/clients", headers=headers, params={"clientId": client_id})
        if r.status_code != 200:
            raise HTTPException(502, f"failed to query client: {r.text}")
        data = r.json()
        return data[0]["id"] if data else None


async def _get_client_secret(client_uuid: str, token: str) -> str:
    headers = {"Authorization": f"Bearer {token}"}
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(f"{ADMIN_API}/clients/{client_uuid}/client-secret", headers=headers)
        if r.status_code != 200:
            raise HTTPException(502, f"failed to fetch client secret: {r.text}")
        return r.json().get("value", "")


async def create_client(payload: dict, token: str) -> dict:
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.post(f"{ADMIN_API}/clients", headers=headers, json=payload)

        if r.status_code == 409:
            # Already exists -> fetch secret
            client_uuid = await _find_client_uuid(payload["clientId"], token)
            if not client_uuid:
                raise HTTPException(500, "client conflict but not found")
            secret = await _get_client_secret(client_uuid, token)
            return {"client_id": payload["clientId"], "client_secret": secret}

        if r.status_code not in (201, 204):
            raise HTTPException(502, f"failed to create client: {r.text}")

        # Parse `Location` for client UUID
        location = r.headers.get("Location", "")
        uuid = location.rstrip("/").split("/")[-1] if location else None
        if not uuid:
            uuid = await _find_client_uuid(payload["clientId"], token)

        secret = await _get_client_secret(uuid, token)
        return {"client_id": payload["clientId"], "client_secret": secret}
