from config import MUSIC_BASE_VOLUME, MUSIC_DUCK_VOLUME, MUSIC_FADE_DURATION


def compute_volume_envelope(
    timeline_segments: list[dict],
    total_duration: float,
    base_volume: float = MUSIC_BASE_VOLUME,
    duck_volume: float = MUSIC_DUCK_VOLUME,
    fade_duration: float = MUSIC_FADE_DURATION,
) -> list[dict]:
    """
    Compute a volume envelope as a list of {t, v} keypoints.

    timeline_segments: list of {start, end, clip_type} dicts representing
                       the timeline items laid out sequentially.
    """
    # 1. Collect talking segments
    talking = [
        (seg["start"], seg["end"])
        for seg in timeline_segments
        if seg.get("clip_type") == "talking"
    ]

    if not talking:
        return [{"t": 0, "v": base_volume}, {"t": total_duration, "v": base_volume}]

    # 2. Merge segments that are close together
    talking.sort(key=lambda s: s[0])
    merged = [talking[0]]
    for start, end in talking[1:]:
        prev_start, prev_end = merged[-1]
        if start - prev_end <= fade_duration * 2:
            merged[-1] = (prev_start, max(prev_end, end))
        else:
            merged.append((start, end))

    # 3. Generate keypoints
    keypoints = []
    for talk_start, talk_end in merged:
        fade_out_start = max(0, talk_start - fade_duration)
        fade_in_end = min(total_duration, talk_end + fade_duration)

        keypoints.append({"t": fade_out_start, "v": base_volume})
        keypoints.append({"t": talk_start, "v": duck_volume})
        keypoints.append({"t": talk_end, "v": duck_volume})
        keypoints.append({"t": fade_in_end, "v": base_volume})

    # 4. Ensure envelope starts at 0 and ends at total_duration
    if keypoints[0]["t"] > 0:
        keypoints.insert(0, {"t": 0, "v": base_volume})
    if keypoints[-1]["t"] < total_duration:
        keypoints.append({"t": total_duration, "v": base_volume})

    # 5. Remove duplicate times (keep first occurrence)
    seen = set()
    deduped = []
    for kp in keypoints:
        t = round(kp["t"], 4)
        if t not in seen:
            seen.add(t)
            deduped.append({"t": t, "v": kp["v"]})

    return deduped


def envelope_to_ffmpeg_expr(keypoints: list[dict]) -> str:
    """
    Convert volume keypoints to an FFmpeg volume filter expression.
    Uses piecewise linear interpolation via nested if(between(...)).
    """
    if len(keypoints) < 2:
        return str(keypoints[0]["v"] if keypoints else MUSIC_BASE_VOLUME)

    parts = []
    for i in range(len(keypoints) - 1):
        t0, v0 = keypoints[i]["t"], keypoints[i]["v"]
        t1, v1 = keypoints[i + 1]["t"], keypoints[i + 1]["v"]

        if abs(v1 - v0) < 0.001:
            # Constant segment
            parts.append(f"if(between(t,{t0},{t1}),{v0}")
        else:
            # Linear interpolation: v0 + (v1-v0) * (t-t0) / (t1-t0)
            slope = (v1 - v0) / (t1 - t0) if t1 != t0 else 0
            parts.append(f"if(between(t,{t0},{t1}),{v0}+{slope}*(t-{t0})")

    # Build nested expression
    expr = f"{keypoints[-1]['v']}"  # fallback value
    for part in reversed(parts):
        expr = f"{part},{expr})"

    return expr
