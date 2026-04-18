from services.storage import create_upload_path


def test_local_upload_paths_are_immutable_per_upload():
    path_a = create_upload_path("workspace-1", "clip.mp4")
    path_b = create_upload_path("workspace-1", "clip.mp4")

    assert path_a != path_b
    assert path_a.endswith("/clip.mp4")
    assert path_b.endswith("/clip.mp4")
