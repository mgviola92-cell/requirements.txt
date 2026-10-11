"""Wikipedia category-membership questions based on live MediaWiki API records.

Categories are topic pools, not distinct question templates.
"""
import random
import urllib.parse

from core.question_quality import cached_json, make_mcq

CATEGORIES = (
    "Planets of the Solar System","Natural satellites of the Solar System",
    "Constellations","Galaxies","Nebulae","Asteroids","Comets",
    "Chemical elements","Noble gases","Alkali metals","Minerals",
    "Dinosaurs","Primates","Birds of prey","Marine mammals",
    "Carnivorans","Amphibians","Reptiles","Insects","Butterflies",
    "Mountains of Asia","Rivers of Europe","Lakes of Africa",
    "Volcanoes of Indonesia","Islands of Japan","Deserts of Asia",
    "Waterfalls of South America","National parks of Canada",
    "Capital cities in Europe","Cities in Australia",
    "Programming languages","Operating systems","Web browsers",
    "Database management systems","Computer scientists",
    "Mathematicians","Physicists","Astronomers",
    "Classical composers","Musical instruments","Symphonies",
    "Painters","Sculptors","Art museums",
    "Olympic sports","Board games","Chess openings",
    "Ancient Greek philosophers","Roman emperors","Egyptian pharaohs",
    "Nobel Prize in Physics laureates","Nobel Prize in Chemistry laureates",
)

def _members(category):
    params=urllib.parse.urlencode({
        "action":"query","format":"json","generator":"categorymembers",
        "gcmtitle":"Category:"+category,"gcmtype":"page",
        "gcmlimit":100,"prop":"info"})
    data=cached_json("https://en.wikipedia.org/w/api.php?"+params,ttl=3600)
    pages=(data.get("query") or {}).get("pages") or {}
    return [p["title"] for p in pages.values()
            if p.get("ns")==0 and isinstance(p.get("title"),str)
            and 3<=len(p["title"])<=80 and not p["title"].startswith("List of ")]

def wikipedia_question():
    for _ in range(2):
        chosen=random.sample(CATEGORIES,4)
        pools=[_members(category) for category in chosen]
        if any(not pool for pool in pools):
            continue
        correct=random.choice(pools[0])
        wrong=[random.choice(pool) for pool in pools[1:]]
        if len(set([correct]+wrong))!=4:
            continue
        return make_mcq(
            "Which Wikipedia article is listed directly under Category:"+chosen[0]+"?",
            correct,wrong,"wikipedia:category_membership")
    return None
