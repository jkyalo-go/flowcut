import pytest

from services.sie.gates import GateFailure, run_quality_gates
from services.sie.schemas import EditManifest, TrimAction, ZoomAction


def _base_manifest(**overrides):
    defaults = dict(
        trim=TrimAction(start_sec=0.0, end_sec=30.0),
        platform_targets=["tiktok"],
        confidence=0.85,
        reasoning="ok",
    )
    defaults.update(overrides)
    return EditManifest(**defaults)


def test_gates_pass_clean_manifest():
    m = _base_manifest()
    run_quality_gates(m, footage_duration_sec=60.0, style_profile={"max_cuts_per_min": 15})
    # no exception = pass


def test_gates_fail_trim_beyond_footage():
    m = _base_manifest(trim=TrimAction(start_sec=0.0, end_sec=90.0))
    with pytest.raises(GateFailure, match="trim.end_sec"):
        run_quality_gates(m, footage_duration_sec=60.0, style_profile={})


def test_gates_fail_zoom_beyond_trim():
    m = _base_manifest(zooms=[ZoomAction(at_sec=50.0, factor=1.5, duration_sec=0.3, curve="ease_out")])
    with pytest.raises(GateFailure, match="zoom at_sec"):
        run_quality_gates(m, footage_duration_sec=60.0, style_profile={})


def test_gates_fail_excessive_cuts_per_minute():
    from services.sie.schemas import TransitionAction
    cuts = [TransitionAction(at_sec=float(i), type="hard_cut") for i in range(30)]
    m = _base_manifest(transitions=cuts)  # 30 cuts in 30s = 60/min
    with pytest.raises(GateFailure, match="cuts_per_min"):
        run_quality_gates(m, footage_duration_sec=60.0, style_profile={"max_cuts_per_min": 20})


def test_gates_pass_with_no_style_constraint():
    from services.sie.schemas import TransitionAction
    cuts = [TransitionAction(at_sec=float(i), type="hard_cut") for i in range(30)]
    m = _base_manifest(transitions=cuts)
    # style_profile has no max_cuts_per_min → constraint not enforced
    run_quality_gates(m, footage_duration_sec=60.0, style_profile={})
