from unittest.mock import patch, MagicMock


def test_send_email_calls_sendgrid(monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.test")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "noreply@flowcut.ai")
    mock_client = MagicMock()
    mock_client.send.return_value = MagicMock(status_code=202)
    with patch("sendgrid.SendGridAPIClient", return_value=mock_client):
        from services.email_service import send_email
        result = send_email(
            to_email="creator@gmail.com",
            subject="Your clip is ready",
            html_body="<p>Review it now.</p>",
        )
    assert result is True
    mock_client.send.assert_called_once()


def test_send_email_returns_false_on_api_error(monkeypatch):
    monkeypatch.setenv("SENDGRID_API_KEY", "SG.test")
    monkeypatch.setenv("SENDGRID_FROM_EMAIL", "noreply@flowcut.ai")
    mock_client = MagicMock()
    mock_client.send.side_effect = Exception("API error")
    with patch("sendgrid.SendGridAPIClient", return_value=mock_client):
        from services.email_service import send_email
        result = send_email("x@x.com", "sub", "<p>body</p>")
    assert result is False


def test_send_push_returns_false_without_credentials(monkeypatch):
    monkeypatch.delenv("FIREBASE_CREDENTIALS_JSON", raising=False)
    # Reset singleton so _init_firebase runs fresh
    import services.push_service as ps
    ps._initialized = False
    from services.push_service import send_push
    result = send_push("fcm_token_abc", "Test", "Body")
    assert result is False
