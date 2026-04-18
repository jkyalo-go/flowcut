

def _make_profile(extra: dict | None = None) -> dict:
    base = {
        "pacing": {"cuts_per_min": 10, "speed_ramps": False},
        "captions": {"font": "DM Sans", "animation": "word_by_word"},
    }
    if extra:
        base.update(extra)
    return base


def test_diff_detects_added_zoom():
    from services.sie.feedback import diff_manifests
    original = {"zooms": [], "transitions": [{"at_sec": 5.0, "type": "hard_cut"}]}
    modified = {"zooms": [{"at_sec": 3.0, "factor": 1.5}], "transitions": [{"at_sec": 5.0, "type": "hard_cut"}]}
    diff = diff_manifests(original, modified)
    assert "zooms" in diff
    assert diff["zooms"] == "added 1 item(s)"


def test_diff_detects_no_changes():
    from services.sie.feedback import diff_manifests
    m = {"zooms": [], "confidence": 0.9}
    assert diff_manifests(m, m) == {}


def test_apply_feedback_updates_pacing_doc():
    from services.sie.feedback import apply_feedback_to_profile
    profile = _make_profile()
    diff = {"transitions": "added 3 item(s)"}
    dimension_locks = {}
    updated = apply_feedback_to_profile(profile, diff, dimension_locks, action="approved")
    # pacing should reflect that more cuts were added (approved)
    assert "pacing" in updated


def test_locked_dimension_not_updated():
    from services.sie.feedback import apply_feedback_to_profile
    profile = _make_profile()
    diff = {"captions": "animation changed to fade"}
    dimension_locks = {"captions": True}
    updated = apply_feedback_to_profile(profile, diff, dimension_locks, action="approved")
    # captions locked — animation should remain word_by_word
    assert updated["captions"]["animation"] == "word_by_word"
