# =========================================================
# 🏆 RANK CONFIG
# =========================================================

RANKS = [
    {
        "id": "rookie",
        "name": "🌱 ROOKIE",
        "min_points": 0,
        "next_points": 20,
        "asset_key": "rookie"
    },
    {
        "id": "player",
        "name": "⭐ PLAYER",
        "min_points": 20,
        "next_points": 50,
        "asset_key": "player"
    },
    {
        "id": "pro",
        "name": "🔥 PRO",
        "min_points": 50,
        "next_points": 100,
        "asset_key": "pro"
    },
    {
        "id": "master",
        "name": "💎 MASTER",
        "min_points": 100,
        "next_points": 200,
        "asset_key": "master"
    },
    {
        "id": "legend",
        "name": "👑 LEGEND",
        "min_points": 200,
        "next_points": None,
        "asset_key": "legend"
    }
]


def get_rank_data(points):
    points = max(0, int(points))

    current_rank = RANKS[0]

    for rank in RANKS:
        if points >= rank["min_points"]:
            current_rank = rank
        else:
            break

    return current_rank


def get_rank_title(points):
    return get_rank_data(points)["name"]


def get_rank_progress(points):
    points = max(0, int(points))

    rank = get_rank_data(points)
    next_points = rank["next_points"]

    if next_points is None:
        return {
            "current": points,
            "needed": 0,
            "percent": 100,
            "next_rank": None
        }

    start = rank["min_points"]

    total_needed = next_points - start
    current_progress = points - start

    percent = int(
        (current_progress / total_needed) * 100
    )

    percent = max(0, min(100, percent))

    next_rank = None

    for item in RANKS:
        if item["min_points"] == next_points:
            next_rank = item["name"]
            break

    return {
        "current": current_progress,
        "needed": total_needed,
        "percent": percent,
        "next_rank": next_rank
    }
