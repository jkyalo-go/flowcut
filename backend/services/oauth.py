import base64
import hashlib
import secrets

import httpx
from itsdangerous import URLSafeTimedSerializer


def generate_state_token(secret_key: str, workspace_id: str | None = None) -> str:
    s = URLSafeTimedSerializer(secret_key)
    return s.dumps({"ws": workspace_id or ""})


def verify_state_token(secret_key: str, token: str, max_age: int = 600) -> dict:
    s = URLSafeTimedSerializer(secret_key)
    return s.loads(token, max_age=max_age)


def generate_pkce_pair() -> tuple[str, str]:
    """Return (code_verifier, code_challenge) for PKCE S256."""
    verifier = secrets.token_urlsafe(64)[:128]
    digest = hashlib.sha256(verifier.encode("ascii")).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return verifier, challenge


async def exchange_google_code(
    code: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
    code_verifier: str | None = None,
) -> dict:
    """Exchange an auth code for Google user info. Sends PKCE verifier when provided."""
    data = {
        "code": code,
        "client_id": client_id,
        "client_secret": client_secret,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    if code_verifier:
        data["code_verifier"] = code_verifier
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data=data,
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        return userinfo_resp.json()
