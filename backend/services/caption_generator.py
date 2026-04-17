import json
import os
import logging

logger = logging.getLogger(__name__)

PLATFORM_CONSTRAINTS = {
    "tiktok":           {"max_chars": 2200, "hashtag_count": 5,  "hook_chars": 150, "style": "energetic, short sentences, emoji OK"},
    "youtube_shorts":   {"max_chars": 5000, "hashtag_count": 8,  "hook_chars": 100, "style": "SEO-friendly, descriptive"},
    "youtube":          {"max_chars": 5000, "hashtag_count": 8,  "hook_chars": 200, "style": "SEO-friendly, detailed"},
    "instagram_reels":  {"max_chars": 2200, "hashtag_count": 15, "hook_chars": 125, "style": "visual, lifestyle tone, hashtag-heavy"},
    "linkedin":         {"max_chars": 3000, "hashtag_count": 4,  "hook_chars": 140, "style": "professional, insightful"},
    "x":                {"max_chars": 280,  "hashtag_count": 2,  "hook_chars": 280, "style": "punchy, max 2 hashtags"},
}

_FALLBACK = {"title": "New clip", "description": "", "hashtags": []}


def generate_platform_captions(
    transcript: str,
    moment_type: str,
    platforms: list[str],
    style_voice: str = "",
) -> dict[str, dict]:
    """Returns {platform: {title, description, hashtags}} for each platform."""
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        return {p: dict(_FALLBACK) for p in platforms}

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        constraints = {p: PLATFORM_CONSTRAINTS[p] for p in platforms if p in PLATFORM_CONSTRAINTS}
        prompt = (
            f"Generate platform-specific captions for a short-form video clip.\n"
            f"Transcript excerpt: {transcript[:500]}\n"
            f"Moment type: {moment_type}\n"
            f"Creator voice: {style_voice or 'casual, engaging'}\n"
            f"Platform constraints: {json.dumps(constraints)}\n\n"
            f"Return JSON: {{\"platform\": {{\"title\": str, \"description\": str, \"hashtags\": [str]}}}} for each platform in {json.dumps(platforms)}."
        )
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config={"response_mime_type": "application/json"},
        )
        result = json.loads(response.text)
        # Ensure all requested platforms are present
        for p in platforms:
            if p not in result:
                result[p] = dict(_FALLBACK)
        return result
    except Exception as e:
        logger.error("Caption generation failed: %s", e)
        return {p: dict(_FALLBACK) for p in platforms}
