"""API keys for provider credentials must be encrypted at rest.

Writes go to api_key_enc (AES-GCM); the legacy api_key column stays NULL.
Reads transparently decrypt via common.secrets.unseal.
"""
import json


def test_credential_api_key_is_encrypted_at_rest(client, workspace_a, db):
    _, token = workspace_a
    resp = client.post(
        "/api/ai/credentials",
        headers={"X-Flowcut-Token": token},
        json={
            "provider": "anthropic",
            "api_key": "sk-ant-SECRET-12345",
            "label": "test",
            "allowed_models": [],
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    # Response DTO never includes the key
    assert "api_key" not in body
    # DB row: plaintext column is NULL, ciphertext column is populated
    from domain.ai import AIProviderCredential
    row = db.query(AIProviderCredential).filter(AIProviderCredential.id == body["id"]).one()
    assert row.api_key is None
    assert row.api_key_enc is not None
    assert b"sk-ant-SECRET-12345" not in bytes(row.api_key_enc)
    # Round-trip through unseal
    from common.secrets import unseal
    assert unseal(row.api_key_enc) == "sk-ant-SECRET-12345"


def test_credential_list_never_returns_api_key(client, workspace_a, db):
    _, token = workspace_a
    client.post(
        "/api/ai/credentials",
        headers={"X-Flowcut-Token": token},
        json={"provider": "openai", "api_key": "sk-OPENAI-SECRET", "label": "a", "allowed_models": []},
    )
    resp = client.get("/api/ai/credentials", headers={"X-Flowcut-Token": token})
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) >= 1
    for row in rows:
        assert "api_key" not in row
        assert "api_key_enc" not in row
    # And the raw response body has no trace of the secret
    assert "sk-OPENAI-SECRET" not in json.dumps(rows)
