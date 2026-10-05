# =========================================================
# 🏆 EXPANDED PLAYER RANK LADDER
# Existing low-rank thresholds are preserved; ranks continue far beyond LEGEND.
# =========================================================

RANKS = [
    {"title": "ROOKIE",       "name": "ROOKIE",       "min_points": 0,    "max_points": 19,   "min": 0,    "max": 19,   "emoji": "🌱"},
    {"title": "PLAYER",       "name": "PLAYER",       "min_points": 20,   "max_points": 49,   "min": 20,   "max": 49,   "emoji": "🎮"},
    {"title": "PRO",          "name": "PRO",          "min_points": 50,   "max_points": 99,   "min": 50,   "max": 99,   "emoji": "⚡"},
    {"title": "MASTER",       "name": "MASTER",       "min_points": 100,  "max_points": 199,  "min": 100,  "max": 199,  "emoji": "🔥"},
    {"title": "LEGEND",       "name": "LEGEND",       "min_points": 200,  "max_points": 399,  "min": 200,  "max": 399,  "emoji": "🏆"},
    {"title": "MYTHIC",       "name": "MYTHIC",       "min_points": 400,  "max_points": 699,  "min": 400,  "max": 699,  "emoji": "💠"},
    {"title": "IMMORTAL",     "name": "IMMORTAL",     "min_points": 700,  "max_points": 1099, "min": 700,  "max": 1099, "emoji": "👑"},
    {"title": "CELESTIAL",    "name": "CELESTIAL",    "min_points": 1100, "max_points": 1599, "min": 1100, "max": 1599, "emoji": "✨"},
    {"title": "TITAN",        "name": "TITAN",        "min_points": 1600, "max_points": 2299, "min": 1600, "max": 2299, "emoji": "🗿"},
    {"title": "ETERNAL",      "name": "ETERNAL",      "min_points": 2300, "max_points": 3199, "min": 2300, "max": 3199, "emoji": "🌌"},
    {"title": "ASCENDANT",    "name": "ASCENDANT",    "min_points": 3200, "max_points": 4499, "min": 3200, "max": 4499, "emoji": "🚀"},
    {"title": "OMEGA",        "name": "OMEGA",        "min_points": 4500, "max_points": 5999, "min": 4500, "max": 5999, "emoji": "🌠"},
    {"title": "APEX",         "name": "APEX",         "min_points": 6000, "max_points": 7999, "min": 6000, "max": 7999, "emoji": "🔱"},
    {"title": "TRANSCENDENT", "name": "TRANSCENDENT", "min_points": 8000, "max_points": None, "min": 8000, "max": None, "emoji": "💫"},
]


def _points(value):
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0


def get_rank_data(points):
    points = _points(points)
    for index, rank in enumerate(RANKS):
        maximum = rank["max_points"]
        if maximum is None or points <= maximum:
            data = dict(rank)
            next_rank = RANKS[index + 1] if index + 1 < len(RANKS) else None
            data["next_rank"] = next_rank["title"] if next_rank else None
            data["next_points"] = next_rank["min_points"] if next_rank else None
            return data
    return dict(RANKS[-1])


def get_rank_title(points):
    return get_rank_data(points)["title"]


def get_rank_progress(points):
    """Return a 0.0-1.0 progress ratio inside the current rank."""
    points = _points(points)
    rank = get_rank_data(points)
    start = rank["min_points"]
    end = rank["max_points"]
    if end is None:
        return 1.0
    span = max(1, end - start + 1)
    return max(0.0, min(1.0, (points - start) / span))
