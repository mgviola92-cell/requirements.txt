# =========================================================
# 🖼️ ASSET MANAGER
# =========================================================

from pathlib import Path
import random
import threading


# =========================================================
# 📁 PROJECT PATHS
# =========================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_ROOT = PROJECT_ROOT / "assets"


# =========================================================
# 🔒 RECENT-ASSET MEMORY
#
# Visual repetition လျော့ဖို့ အသုံးပြုမည်။
# =========================================================

_recent_assets = {}
_recent_assets_lock = threading.RLock()


# =========================================================
# 🗂️ SUPPORTED IMAGE TYPES
# =========================================================

SUPPORTED_IMAGE_EXTENSIONS = {
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
}


# =========================================================
# 📂 GET ASSET DIRECTORY
# =========================================================

def get_asset_directory(*parts):
    return ASSETS_ROOT.joinpath(*parts)


# =========================================================
# 📄 GET ASSET FILE
# =========================================================

def get_asset_path(*parts):
    path = ASSETS_ROOT.joinpath(*parts)

    if path.exists():
        return path

    return None


# =========================================================
# 🖼️ LIST IMAGES IN FOLDER
# =========================================================

def list_images(
    *folder_parts,
    recursive=False
):
    folder = get_asset_directory(
        *folder_parts
    )

    if not folder.exists():
        return []

    if not folder.is_dir():
        return []

    if recursive:
        files = folder.rglob("*")
    else:
        files = folder.glob("*")

    images = [
        path
        for path in files
        if (
            path.is_file()
            and path.suffix.lower()
            in SUPPORTED_IMAGE_EXTENSIONS
        )
    ]

    return sorted(images)


# =========================================================
# 🎲 RANDOM ASSET
# =========================================================

def random_asset(
    *folder_parts,
    recursive=False
):
    images = list_images(
        *folder_parts,
        recursive=recursive
    )

    if not images:
        return None

    return random.choice(images)


# =========================================================
# 🔄 RANDOM ASSET WITH RECENT AVOIDANCE
#
# Example:
# Speed Tap / This or That / Random Event
# =========================================================

def random_asset_avoiding_recent(
    category_key,
    *folder_parts,
    recent_limit=10,
    recursive=False
):
    images = list_images(
        *folder_parts,
        recursive=recursive
    )

    if not images:
        return None

    recent_limit = max(
        0,
        int(recent_limit)
    )

    with _recent_assets_lock:
        recent = _recent_assets.get(
            category_key,
            []
        )

        recent_set = set(recent)

        available = [
            image
            for image in images
            if str(image) not in recent_set
        ]

        # Asset pool သေးလို့
        # အကုန် recent ဖြစ်နေခဲ့ရင် reset
        if not available:
            available = images
            recent = []

        selected = random.choice(
            available
        )

        recent.append(
            str(selected)
        )

        if recent_limit > 0:
            recent = recent[
                -recent_limit:
            ]
        else:
            recent = []

        _recent_assets[
            category_key
        ] = recent

    return selected


# =========================================================
# 🧹 CLEAR RECENT HISTORY
# =========================================================

def clear_recent_assets(
    category_key=None
):
    with _recent_assets_lock:

        if category_key is None:
            _recent_assets.clear()
            return

        _recent_assets.pop(
            category_key,
            None
        )


# =========================================================
# 📊 COUNT ASSETS
# =========================================================

def count_assets(
    *folder_parts,
    recursive=False
):
    return len(
        list_images(
            *folder_parts,
            recursive=recursive
        )
    )


# =========================================================
# ✅ ASSET EXISTS?
# =========================================================

def asset_exists(*parts):
    path = get_asset_path(
        *parts
    )

    return (
        path is not None
        and path.is_file()
    )
