"""A symlink under STORAGE_DIR must not be usable to escape to /etc/passwd."""
import os
import tempfile
from pathlib import Path


def test_symlink_escape_is_rejected(tmp_path, monkeypatch):
    # Build an allowed-root that contains a symlink to /etc
    fake_storage = tmp_path / "storage"
    fake_storage.mkdir()
    evil_link = fake_storage / "escape"
    target_dir = Path(tempfile.mkdtemp(prefix="target_"))
    (target_dir / "secret.txt").write_text("SHOULD_NOT_BE_READABLE")
    os.symlink(target_dir, evil_link)

    import routes.filesystem as fs_mod
    monkeypatch.setattr(fs_mod, "ALLOWED_LOCAL_ROOTS", (fake_storage.resolve(),))

    # A path that traverses through the symlink must fail the allow-list check
    via_symlink = evil_link / "secret.txt"
    assert fs_mod._path_in_allowed_roots(via_symlink) is False

    # A direct path inside the allowed root (no symlink) is accepted
    normal = fake_storage / "legit.mp4"
    normal.write_text("ok")
    assert fs_mod._path_in_allowed_roots(normal) is True


def test_parent_traversal_rejected(tmp_path, monkeypatch):
    fake_storage = tmp_path / "storage"
    fake_storage.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("no")

    import routes.filesystem as fs_mod
    monkeypatch.setattr(fs_mod, "ALLOWED_LOCAL_ROOTS", (fake_storage.resolve(),))

    # Path that exits the allowed root via .. is rejected
    escape_attempt = fake_storage / ".." / "outside.txt"
    assert fs_mod._path_in_allowed_roots(escape_attempt) is False
