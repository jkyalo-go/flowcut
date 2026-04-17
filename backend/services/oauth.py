import httpx
from itsdangerous import URLSafeTimedSerializer

_SIGNER = None

def _get_signer(secret_key: str) -> URLSafeTimedSerializer:
    global _SIGNER
    if _SIGNER is None:
        _SIGNER = URLSafeTimedSerializer(secret_key)
    return _SIGNER


def generate_state_token(secret_key: str, workspace_id: str | None = None) -> str:
    s = _get_signer(secret_key)
    return s.dumps({"ws": workspace_id or ""})


def verify_state_token(secret_key: str, token: str, max_age: int = 600) -> dict:
    s = _get_signer(secret_key)
    return s.loads(token, max_age=max_age)


async def exchange_google_code(code: str, redirect_uri: str, client_id: str, client_secret: str) -> dict:
    """Exchange an auth code for Google user info. Returns dict with sub, email, name, picture."""
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "code": code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        token_resp.raise_for_status()
        tokens = token_resp.json()

        userinfo_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo_resp.raise_for_status()
        return userinfo_resp.json()
