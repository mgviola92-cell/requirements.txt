"""Strict visual registry for This or That.

Never silently substitute unrelated pictures. Each option resolves to a
tagged local image, otherwise the round must not use a photo.
"""
from pathlib import Path
import hashlib
import json
from data.this_or_that_questions import get_question

ROOT = Path(__file__).resolve().parents[1] / "assets" / "this_or_that"
MANIFEST = ROOT / "manifest.json"
IMAGE_EXTS = {".webp", ".jpg", ".jpeg", ".png"}


def _safe_image(name):
    if not isinstance(name,str):
        return None
    candidate = (ROOT / name).resolve()
    if ROOT.resolve() not in candidate.parents or candidate.suffix.lower() not in IMAGE_EXTS:
        return None
    return candidate if candidate.is_file() else None


def get_visuals(question, manifest=None):
    """Return matching images or None; no approximate guesses."""
    if manifest is None:
        if not MANIFEST.is_file():
            return None
        manifest=json.loads(MANIFEST.read_text(encoding="utf-8"))
    paths=[]
    for tag in question["visual_tags"]:
        options = manifest.get(tag)
        if not isinstance(options,list) or not options:
            return None
        found = [_safe_image(value) for value in options]
        found = [p for p in found if p is not None]
        if not found:
            return None
        # A stable rotation avoiding the same default image for every round.
        index = int(hashlib.sha256((question["id"]+tag).encode()).hexdigest()[:8],16)
        paths.append(found[index % len(found)])
    return tuple(paths)


def visual_coverage(manifest=None):
    from data.this_or_that_questions import CATEGORIES
    if manifest is None:
        manifest=json.loads(MANIFEST.read_text(encoding="utf-8")) if MANIFEST.is_file() else {}
    total=sum(len(options) for options in CATEGORIES.values())
    ready=0
    for category,options in CATEGORIES.items():
        for option in options:
            tag=f"{category}/{option}"
            files=manifest.get(tag,[])
            if isinstance(files,list) and any(_safe_image(file) for file in files):
                ready+=1
    return {"ready":ready,"total":total,"missing":total-ready}
