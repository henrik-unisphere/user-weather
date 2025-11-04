from fastapi import APIRouter, Depends
from app.admin.kc_admin import get_admin_access_token, create_client
from app.auth.auth_dep import require_admin

router = APIRouter(prefix="/admin/clients", tags=["admin"])


@router.post("/create")
async def create_machine_client(
    client_id: str,
    admin=Depends(require_admin),
):
    token = await get_admin_access_token()

    # Client-Definition für M2M (Client Credentials)
    payload = {
        "clientId": client_id,
        "name": client_id,
        "protocol": "openid-connect",
        "publicClient": False,
        "serviceAccountsEnabled": True,
        "standardFlowEnabled": False,  # keine Browser Logins
        "directAccessGrantsEnabled": False,
        "clientAuthenticatorType": "client-secret",
    }

    result = await create_client(payload, token)
    return {
        "message": "client created successfully",
        "client_id": result["client_id"],
        "client_secret": result["client_secret"],
    }
