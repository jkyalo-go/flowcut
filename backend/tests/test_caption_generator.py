def test_generate_platform_captions_fallback_without_api_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    import importlib
    import services.caption_generator as cg
    importlib.reload(cg)
    result = cg.generate_platform_captions(
        transcript="Hello world this is a test clip",
        moment_type="highlight",
        platforms=["tiktok", "youtube"],
    )
    assert "tiktok" in result
    assert "youtube" in result
    assert result["tiktok"]["title"] == "New clip"


def test_generate_platform_captions_with_gemini_mock(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "fake-key")
    from unittest.mock import MagicMock, patch
    import importlib
    import services.caption_generator as cg
    importlib.reload(cg)

    mock_response = MagicMock()
    mock_response.text = '{"tiktok": {"title": "Epic clip", "description": "Watch this", "hashtags": ["#viral"]}}'

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("google.genai.Client", return_value=mock_client):
        result = cg.generate_platform_captions(
            transcript="Test transcript",
            moment_type="highlight",
            platforms=["tiktok"],
        )
    assert result["tiktok"]["title"] == "Epic clip"
