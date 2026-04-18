from unittest.mock import MagicMock, patch


def test_send_email_sends_via_smtp(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "user@example.com")
    monkeypatch.setenv("SMTP_PASSWORD", "secret")
    monkeypatch.setenv("SMTP_FROM_EMAIL", "noreply@flowcut.ai")
    mock_smtp = MagicMock()
    with patch("smtplib.SMTP", return_value=mock_smtp.__enter__.return_value):
        mock_smtp.__enter__.return_value.sendmail = MagicMock()
        import importlib

        import services.email_service as em
        importlib.reload(em)
        with patch("smtplib.SMTP") as smtp_cls:
            smtp_instance = MagicMock()
            smtp_cls.return_value.__enter__ = MagicMock(return_value=smtp_instance)
            smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
            result = em.send_email(
                to_email="creator@gmail.com",
                subject="Your clip is ready",
                html_body="<p>Review it now.</p>",
            )
    assert result is True
    smtp_instance.sendmail.assert_called_once()


def test_send_email_returns_false_on_smtp_error(monkeypatch):
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")
    import importlib

    import services.email_service as em
    importlib.reload(em)
    with patch("smtplib.SMTP", side_effect=Exception("Connection refused")):
        result = em.send_email("x@x.com", "sub", "<p>body</p>")
    assert result is False


def test_send_email_returns_false_without_smtp_host(monkeypatch):
    monkeypatch.delenv("SMTP_HOST", raising=False)
    import importlib

    import services.email_service as em
    importlib.reload(em)
    result = em.send_email("x@x.com", "sub", "<p>body</p>")
    assert result is False


def test_send_push_returns_false_without_credentials(monkeypatch):
    monkeypatch.delenv("FIREBASE_CREDENTIALS_JSON", raising=False)
    import services.push_service as ps
    ps._initialized = False
    from services.push_service import send_push
    result = send_push("fcm_token_abc", "Test", "Body")
    assert result is False
