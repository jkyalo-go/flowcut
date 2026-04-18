from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlparse
from uuid import uuid4

from config import (
    GCS_MEDIA_BUCKET,
    GCS_SIGNED_URL_TTL_SECONDS,
    STORAGE_BACKEND,
    STORAGE_DIR,
    UPLOAD_TMP_DIR,
)

try:
    from google.cloud import storage as gcs_storage
except Exception:  # pragma: no cover - optional dependency at runtime
    gcs_storage = None


def workspace_storage_dir(workspace_id: str) -> Path:
    path = STORAGE_DIR / f"workspace_{workspace_id}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def temp_upload_path(session_id: str, filename: str) -> Path:
    safe_name = filename.replace("/", "_").replace("\\", "_")
    path = UPLOAD_TMP_DIR / f"{session_id}_{safe_name}"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def create_upload_path(workspace_id: str, filename: str) -> str:
    safe_name = filename.replace("/", "_").replace("\\", "_")
    object_name = f"ws_{workspace_id}/raw/{uuid4().hex}/{safe_name}"
    if STORAGE_BACKEND == "gcs" and GCS_MEDIA_BUCKET:
        return f"gs://{GCS_MEDIA_BUCKET}/{object_name}"
    return str(workspace_storage_dir(workspace_id) / "raw" / uuid4().hex / safe_name)


def is_gcs_uri(path: str) -> bool:
    return path.startswith("gs://")


def parse_gcs_uri(path: str) -> tuple[str, str]:
    parsed = urlparse(path)
    bucket = parsed.netloc
    key = parsed.path.lstrip("/")
    if not bucket or not key:
        raise ValueError(f"Invalid GCS URI: {path}")
    return bucket, key


def _gcs_client():
    if gcs_storage is None:
        raise RuntimeError("google-cloud-storage is not installed")
    return gcs_storage.Client()


def finalize_uploaded_file(source_path: Path, target_path: str) -> str:
    if is_gcs_uri(target_path):
        bucket_name, key = parse_gcs_uri(target_path)
        client = _gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(key)
        blob.upload_from_filename(str(source_path))
        return target_path

    destination = Path(target_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source_path), str(destination))
    return str(destination)


def resolve_storage_path(path: str) -> Path:
    p = Path(path)
    if p.is_absolute():
        return p
    return STORAGE_DIR / path


def download_to_temp(path: str) -> Path:
    if not is_gcs_uri(path):
        return resolve_storage_path(path)

    bucket_name, key = parse_gcs_uri(path)
    suffix = Path(key).suffix or ".bin"
    handle = tempfile.NamedTemporaryFile(prefix="flowcut-gcs-", suffix=suffix, delete=False)
    handle.close()
    client = _gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(key)
    blob.download_to_filename(handle.name)
    return Path(handle.name)


def signed_url_for(path: str) -> str | None:
    if not is_gcs_uri(path):
        return None
    bucket_name, key = parse_gcs_uri(path)
    client = _gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(key)
    return blob.generate_signed_url(version="v4", expiration=GCS_SIGNED_URL_TTL_SECONDS)


def write_text_artifact(workspace_id: str, relative_name: str, content: str) -> str:
    target_path = create_upload_path(workspace_id, relative_name)
    handle = tempfile.NamedTemporaryFile(prefix="flowcut-artifact-", suffix=Path(relative_name).suffix or ".txt", delete=False)
    handle.write(content.encode("utf-8"))
    handle.flush()
    handle.close()
    return finalize_uploaded_file(Path(handle.name), target_path)
