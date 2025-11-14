#!/usr/bin/env python3
"""Test script to verify Zitadel authentication configuration."""

import sys
from app.core.settings import settings

print("=" * 60)
print("ZITADEL CONFIGURATION TEST")
print("=" * 60)

# Check settings
print(f"\n1. ZITADEL_ISSUER: {settings.ZITADEL_ISSUER}")
print(f"2. ZITADEL_PROJECT_ID: {settings.ZITADEL_PROJECT_ID}")
print(f"3. ZITADEL_ADMIN_CLIENT_ID: {settings.ZITADEL_ADMIN_CLIENT_ID}")
print(f"4. ZITADEL_ADMIN_CLIENT_SECRET: {'*' * 20} (length: {len(settings.ZITADEL_ADMIN_CLIENT_SECRET)})")

print("\n" + "=" * 60)
print("CHECKING CONFIGURATION")
print("=" * 60)

# Validate settings
issues = []

if not settings.ZITADEL_ISSUER:
    issues.append("❌ ZITADEL_ISSUER is empty")
else:
    print(f"✓ ZITADEL_ISSUER is set")

if not settings.ZITADEL_PROJECT_ID:
    issues.append("❌ ZITADEL_PROJECT_ID is empty")
else:
    print(f"✓ ZITADEL_PROJECT_ID is set")

if not settings.ZITADEL_ADMIN_CLIENT_ID:
    issues.append("❌ ZITADEL_ADMIN_CLIENT_ID is empty")
else:
    print(f"✓ ZITADEL_ADMIN_CLIENT_ID is set")
    if "@" not in settings.ZITADEL_ADMIN_CLIENT_ID:
        print("  ⚠️  WARNING: Client ID doesn't contain '@' - Zitadel client IDs usually have format: XXXXXX@projectname")

if not settings.ZITADEL_ADMIN_CLIENT_SECRET:
    issues.append("❌ ZITADEL_ADMIN_CLIENT_SECRET is empty")
else:
    print(f"✓ ZITADEL_ADMIN_CLIENT_SECRET is set")

print("\n" + "=" * 60)
print("TESTING AUTHENTICATION")
print("=" * 60)

try:
    import zitadel_client as zitadel
    from zitadel_client.exceptions import ApiError

    # Parse issuer
    issuer = settings.ZITADEL_ISSUER.rstrip("/")
    if not issuer.startswith("http://") and not issuer.startswith("https://"):
        issuer = f"https://{issuer}"

    print(f"\nConnecting to: {issuer}")
    print(f"Using Client ID: {settings.ZITADEL_ADMIN_CLIENT_ID}")

    # Try to create client
    client = zitadel.Zitadel.with_client_credentials(
        issuer,
        settings.ZITADEL_ADMIN_CLIENT_ID,
        settings.ZITADEL_ADMIN_CLIENT_SECRET,
    )

    print("✓ Zitadel client created successfully")

    # Try to call a simple API
    print("\nTrying to call Zitadel API...")
    try:
        # Try to list authorizations (this will trigger authentication)
        from zitadel_client.models import BetaAuthorizationServiceListAuthorizationsRequest

        request = BetaAuthorizationServiceListAuthorizationsRequest(
            project_id=settings.ZITADEL_PROJECT_ID,
        )
        response = client.beta_authorizations.list_authorizations(request)
        print("✓ Successfully authenticated with Zitadel!")
        print(f"✓ API call successful")

    except ApiError as e:
        print(f"❌ API Error: {str(e)}")
        if "client not found" in str(e).lower():
            print("\n⚠️  The client ID does not exist in Zitadel")
            print("   Please check:")
            print("   1. Go to your Zitadel Console")
            print("   2. Navigate to your project")
            print("   3. Check Applications or Service Users")
            print("   4. Copy the EXACT Client ID (should look like: 123456789012345678@projectname)")
        elif "unauthorized" in str(e).lower() or "invalid_client" in str(e).lower():
            print("\n⚠️  Authentication failed - client credentials are invalid")
            print("   Please check:")
            print("   1. ZITADEL_ADMIN_CLIENT_ID is correct")
            print("   2. ZITADEL_ADMIN_CLIENT_SECRET is correct")
            print("   3. The machine client has 'Client Secret Basic' authentication enabled")
        elif "permission" in str(e).lower() or "forbidden" in str(e).lower():
            print("\n⚠️  Authentication succeeded but insufficient permissions")
            print("   The machine client needs these roles:")
            print("   - Project Owner (to manage user grants)")
            print("   - Or Org Owner (to manage everything)")
        else:
            print(f"\n⚠️  Unexpected error: {e}")

    except Exception as e:
        print(f"❌ Unexpected error: {str(e)}")
        import traceback
        traceback.print_exc()

except ImportError:
    print("❌ zitadel_client package not installed")
    print("   Run: uv pip install zitadel-client")
except Exception as e:
    print(f"❌ Error: {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
if issues:
    print("ISSUES FOUND:")
    for issue in issues:
        print(f"  {issue}")
    sys.exit(1)
else:
    print("Configuration check complete!")
    print("=" * 60)
