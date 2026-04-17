from __future__ import annotations
import copy
from services.sie.cold_start import GENRE_CENTROIDS


def diff_manifests(original: dict, modified: dict) -> dict:
    """Return a summary of differences between original and modified manifest dicts.
    Keys with no changes are omitted. Values are human-readable change descriptions."""
    diff = {}
    all_keys = set(original) | set(modified)
    for key in all_keys:
        orig_val = original.get(key)
        mod_val = modified.get(key)
        if orig_val == mod_val:
            continue
        if isinstance(orig_val, list) and isinstance(mod_val, list):
            delta = len(mod_val) - len(orig_val)
            if delta > 0:
                diff[key] = f"added {delta} item(s)"
            elif delta < 0:
                diff[key] = f"removed {abs(delta)} item(s)"
            else:
                diff[key] = "items modified"
        else:
            diff[key] = f"changed from {repr(orig_val)} to {repr(mod_val)}"
    return diff


def apply_feedback_to_profile(
    profile: dict,
    diff: dict,
    dimension_locks: dict,
    action: str,  # 'approved', 'modified', 'rejected'
) -> dict:
    """Apply a manifest diff to the style profile JSON document.
    Locked dimensions are never touched. Returns updated profile copy."""
    updated = copy.deepcopy(profile)

    _dimension_map = {
        "pacing": {"transitions", "speed_ramps", "trim"},
        "captions": {"captions"},
        "framing": {"zooms"},
        "sound_design": {"sfx", "music_bed_volume_db"},
        "narrative": {"intro_duration_sec", "outro_duration_sec"},
    }

    for dim, related_keys in _dimension_map.items():
        if dimension_locks.get(dim):
            continue
        relevant_changes = {k: v for k, v in diff.items() if k in related_keys}
        if not relevant_changes:
            continue

        if dim not in updated:
            updated[dim] = {}

        if dim == "pacing" and action == "approved":
            if "transitions" in relevant_changes and "added" in relevant_changes["transitions"]:
                cur = updated["pacing"].get("cuts_per_min", 10)
                new_val = round(cur * 1.05, 1)
                genre = profile.get("genre", "general")
                genre_max = GENRE_CENTROIDS.get(genre, {}).get("max_cuts_per_min", 30)
                updated["pacing"]["cuts_per_min"] = min(new_val, round(genre_max * 1.5, 1))

        if dim == "captions" and "captions" in relevant_changes and action in ("modified", "approved"):
            updated["captions"]["_feedback_applied"] = True

    return updated
