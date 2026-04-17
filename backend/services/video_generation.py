from __future__ import annotations

import time
from pathlib import Path

import httpx
from google import genai
from google.genai.types import GenerateVideosConfig, Image

from config import ALIBABA_DASHSCOPE_API_KEY, GCS_MEDIA_BUCKET, VERTEX_LOCATION, VERTEX_PROJECT_ID
from contracts.generation import VideoGenerateRequest, VideoTaskResponse


def _vertex_client() -> genai.Client:
    if not VERTEX_PROJECT_ID:
        raise RuntimeError("VERTEX_PROJECT_ID is required for Vertex video generation")
    return genai.Client(vertexai=True, project=VERTEX_PROJECT_ID, location=VERTEX_LOCATION)


def _default_output_prefix(output_prefix: str | None) -> str:
    if output_prefix:
        return output_prefix.rstrip("/")
    if not GCS_MEDIA_BUCKET:
        raise RuntimeError("GCS_MEDIA_BUCKET is required for video generation outputs")
    return f"gs://{GCS_MEDIA_BUCKET}/generated/{int(time.time())}"


def generate_with_vertex(body: VideoGenerateRequest) -> VideoTaskResponse:
    client = _vertex_client()
    model = body.model or "veo-3.1-generate-001"
    output_gcs_uri = _default_output_prefix(body.output_prefix)
    operation = client.models.generate_videos(
        model=model,
        prompt=body.prompt,
        image=Image(gcs_uri=body.image_gcs_uri, mime_type=body.mime_type or "image/png") if body.image_gcs_uri else None,
        config=GenerateVideosConfig(
            aspect_ratio=body.aspect_ratio,
            output_gcs_uri=output_gcs_uri,
        ),
    )
    return VideoTaskResponse(
        provider="vertex",
        model=model,
        task_id=getattr(operation, "name", "vertex-operation"),
        status="submitted",
        output_uri=output_gcs_uri,
        raw={"done": getattr(operation, "done", False)},
    )


def generate_with_dashscope(body: VideoGenerateRequest) -> VideoTaskResponse:
    if not ALIBABA_DASHSCOPE_API_KEY:
        raise RuntimeError("ALIBABA_DASHSCOPE_API_KEY is required for DashScope video generation")
    model = body.model or "wan2.7-i2v-turbo"
    payload = {
        "model": model,
        "input": {
            "prompt": body.prompt,
            "img_url": body.image_gcs_uri,
        },
        "parameters": {
            "resolution": "720P",
            "prompt_extend": True,
        },
    }
    if body.input_video_gcs_uri:
        payload["input"]["video_url"] = body.input_video_gcs_uri
    if body.mask_gcs_uri:
        payload["input"]["mask_url"] = body.mask_gcs_uri

    response = httpx.post(
        "https://dashscope-intl.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis",
        headers={
            "Authorization": f"Bearer {ALIBABA_DASHSCOPE_API_KEY}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        },
        json=payload,
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()
    task_id = data.get("output", {}).get("task_id") or data.get("task_id") or "dashscope-task"
    return VideoTaskResponse(
        provider="dashscope",
        model=model,
        task_id=task_id,
        status=data.get("output", {}).get("task_status", "submitted"),
        raw=data,
    )


def get_dashscope_task(task_id: str) -> VideoTaskResponse:
    if not ALIBABA_DASHSCOPE_API_KEY:
        raise RuntimeError("ALIBABA_DASHSCOPE_API_KEY is required for DashScope video generation")
    response = httpx.get(
        f"https://dashscope-intl.aliyuncs.com/api/v1/tasks/{task_id}",
        headers={"Authorization": f"Bearer {ALIBABA_DASHSCOPE_API_KEY}"},
        timeout=30,
    )
    response.raise_for_status()
    data = response.json()
    output = data.get("output", {})
    video_url = None
    results = output.get("results") or []
    if results:
        video_url = results[0].get("video_url")
    return VideoTaskResponse(
        provider="dashscope",
        model=data.get("model", "wan2.7-i2v-turbo"),
        task_id=task_id,
        status=output.get("task_status", "unknown"),
        output_uri=video_url,
        raw=data,
    )
