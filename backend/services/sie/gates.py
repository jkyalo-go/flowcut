from services.sie.schemas import EditManifest


class GateFailure(ValueError):
    pass


def run_quality_gates(
    manifest: EditManifest,
    footage_duration_sec: float,
    style_profile: dict,
) -> None:
    """Raise GateFailure with a descriptive message if the manifest violates any gate.
    Gates run in order: format → grounding → style compliance."""

    clip_duration = manifest.trim.end_sec - manifest.trim.start_sec

    # Gate 1: trim grounding
    if manifest.trim.end_sec > footage_duration_sec + 0.1:
        raise GateFailure(
            f"trim.end_sec ({manifest.trim.end_sec}) exceeds footage duration ({footage_duration_sec})"
        )

    # Gate 2: zoom grounding — zooms must fall within the trim window
    for z in manifest.zooms:
        if z.at_sec < manifest.trim.start_sec or z.at_sec + z.duration_sec > manifest.trim.end_sec:
            raise GateFailure(
                f"zoom at_sec={z.at_sec} duration={z.duration_sec} extends outside trim window "
                f"[{manifest.trim.start_sec}, {manifest.trim.end_sec}]"
            )

    # Gate 3: style compliance — cuts per minute
    max_cuts = style_profile.get("max_cuts_per_min")
    if max_cuts is not None and clip_duration > 0:
        actual_cuts_per_min = len(manifest.transitions) / clip_duration * 60
        if actual_cuts_per_min > max_cuts:
            raise GateFailure(
                f"cuts_per_min={actual_cuts_per_min:.1f} exceeds style profile "
                f"max_cuts_per_min={max_cuts}"
            )
