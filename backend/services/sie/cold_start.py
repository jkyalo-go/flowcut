"""Genre centroid vectors — default style profiles for new creators."""

GENRE_CENTROIDS: dict[str, dict] = {
    "gaming": {
        "pacing": {"cuts_per_min": 14, "speed_ramps": True},
        "captions": {"animation": "word_by_word", "font": "Montserrat"},
        "sound_design": {"music_bed_volume_db": -16, "sfx_enabled": True},
        "transitions": {"preferred_type": "hard_cut", "hard_cut_pct": 85},
        "narrative": {"hook_duration_sec": 1.5, "outro_duration_sec": 2.0},
        "max_cuts_per_min": 18,
    },
    "education": {
        "pacing": {"cuts_per_min": 5, "speed_ramps": False},
        "captions": {"animation": "fade", "font": "DM Sans"},
        "sound_design": {"music_bed_volume_db": -24, "sfx_enabled": False},
        "transitions": {"preferred_type": "crossfade", "hard_cut_pct": 40},
        "narrative": {"hook_duration_sec": 5.0, "outro_duration_sec": 5.0},
        "max_cuts_per_min": 8,
    },
    "podcast": {
        "pacing": {"cuts_per_min": 3, "speed_ramps": False},
        "captions": {"animation": "word_by_word", "font": "DM Sans"},
        "sound_design": {"music_bed_volume_db": -28, "sfx_enabled": False},
        "transitions": {"preferred_type": "crossfade", "hard_cut_pct": 20},
        "narrative": {"hook_duration_sec": 8.0, "outro_duration_sec": 3.0},
        "max_cuts_per_min": 5,
    },
    "vlog": {
        "pacing": {"cuts_per_min": 8, "speed_ramps": True},
        "captions": {"animation": "slide_up", "font": "DM Sans"},
        "sound_design": {"music_bed_volume_db": -20, "sfx_enabled": False},
        "transitions": {"preferred_type": "hard_cut", "hard_cut_pct": 65},
        "narrative": {"hook_duration_sec": 3.0, "outro_duration_sec": 2.0},
        "max_cuts_per_min": 12,
    },
    "fitness": {
        "pacing": {"cuts_per_min": 18, "speed_ramps": True},
        "captions": {"animation": "word_by_word", "font": "Montserrat"},
        "sound_design": {"music_bed_volume_db": -14, "sfx_enabled": True},
        "transitions": {"preferred_type": "hard_cut", "hard_cut_pct": 90},
        "narrative": {"hook_duration_sec": 1.0, "outro_duration_sec": 1.5},
        "max_cuts_per_min": 22,
    },
    "general": {
        "pacing": {"cuts_per_min": 8, "speed_ramps": False},
        "captions": {"animation": "fade", "font": "DM Sans"},
        "sound_design": {"music_bed_volume_db": -20, "sfx_enabled": False},
        "transitions": {"preferred_type": "hard_cut", "hard_cut_pct": 60},
        "narrative": {"hook_duration_sec": 3.0, "outro_duration_sec": 2.0},
        "max_cuts_per_min": 15,
    },
}
