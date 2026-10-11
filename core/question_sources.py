"""Additional question sources for Trivia and Pair Challenge; network failures are safe."""
import html
import json
import random
import urllib.parse
import urllib.request
from core.question_quality import cached_json, validate_question

def _json(url, timeout=5):
    return cached_json(url,timeout=timeout)

def trivia_api():
    """The Trivia API v2, four options."""
    data = _json("https://the-trivia-api.com/v2/questions?limit=10")
    if not isinstance(data, list):
        return None
    random.shuffle(data)
    for row in data:
        question = row.get("question", {})
        text = question.get("text") if isinstance(question, dict) else question
        correct = row.get("correctAnswer")
        wrong = row.get("incorrectAnswers", [])
        if text and correct and len(wrong) >= 3 and correct not in wrong:
            answers = [str(correct)] + [str(x) for x in wrong[:3]]
            random.shuffle(answers)
            return {"question": html.unescape(str(text)), "answers": [html.unescape(x) for x in answers],
                    "correct_index": answers.index(str(correct)), "source": "the_trivia_api"}
    return None

def wikidata_capital():
    """A bounded SPARQL query; country and capital labels come from Wikidata."""
    query = """SELECT ?countryLabel ?capitalLabel WHERE {
      ?country wdt:P31 wd:Q6256; wdt:P36 ?capital.
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    } LIMIT 150"""
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": query, "format": "json"})
    data = _json(url, timeout=6)
    rows = data.get("results", {}).get("bindings", [])
    pairs = [(r["countryLabel"]["value"], r["capitalLabel"]["value"]) for r in rows
             if "countryLabel" in r and "capitalLabel" in r]
    pairs = list(dict.fromkeys(pairs))
    if len(pairs) < 4:
        return None
    country, capital = random.choice(pairs)
    others = list(dict.fromkeys(c for _, c in pairs if c != capital))
    if len(others) < 3:
        return None
    answers = [capital] + random.sample(others, 3)
    random.shuffle(answers)
    return {"question": f"What is the capital of {country}?", "answers": answers,
            "correct_index": answers.index(capital), "source": "wikidata"}

def openalex_research():
    """Research publication-year quiz using OpenAlex metadata."""
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({
        "filter": "from_publication_date:2015-01-01,cited_by_count:>500",
        "per-page": 40, "select": "title,publication_year",
        "page": random.randint(1, 8)})
    data = _json(url, timeout=5)
    rows = [r for r in data.get("results", [])
            if isinstance(r.get("title"), str) and 20 <= len(r["title"]) <= 90
            and isinstance(r.get("publication_year"), int)
            and 2015 <= r["publication_year"] <= 2026]
    if not rows:
        return None
    row = random.choice(rows)
    year = row["publication_year"]
    wrong = [y for y in range(2015, 2027) if y != year]
    answers = [str(year)] + [str(y) for y in random.sample(wrong, 3)]
    random.shuffle(answers)
    return {"question": "In which year was this research published: " + row["title"] + "?",
            "answers": answers, "correct_index": answers.index(str(year)),
            "source": "openalex"}

def wikidata_facts():
    """Wikidata countries/currencies and elements/atomic numbers."""
    category = random.choice(("currency", "element"))
    if category == "currency":
        pattern, relation, template = "wdt:P31 wd:Q6256", "wdt:P38", "Which currency is used in {}?"
    else:
        pattern, relation, template = "wdt:P31 wd:Q11344", "wdt:P1086", "What is the atomic number of {}?"
    query = ("SELECT ?subjectLabel ?valueLabel WHERE { ?subject " + pattern +
             "; " + relation + " ?value. SERVICE wikibase:label { " +
             'bd:serviceParam wikibase:language "en". } } LIMIT 180')
    url = "https://query.wikidata.org/sparql?" + urllib.parse.urlencode({"query": query, "format": "json"})
    data = _json(url, timeout=5)
    pairs = [(r["subjectLabel"]["value"], r["valueLabel"]["value"])
             for r in data.get("results", {}).get("bindings", [])
             if "subjectLabel" in r and "valueLabel" in r]
    pairs = [(a, b) for a, b in dict.fromkeys(pairs) if len(a) < 60 and len(b) < 50]
    if len(pairs) < 4:
        return None
    subject, correct = random.choice(pairs)
    others = list({v for _, v in pairs if v != correct})
    if len(others) < 3:
        return None
    answers = [correct] + random.sample(others, 3)
    random.shuffle(answers)
    return {"question": template.format(subject), "answers": answers,
            "correct_index": answers.index(correct), "source": "wikidata"}

def fetch_question():
    from core.fact_question_engine import wikidata_question, openalex_question
    from core.extra_question_sources import open_library_question, world_bank_question, nasa_images_question
    sources = [trivia_api, wikidata_question, openalex_question, open_library_question, world_bank_question, nasa_images_question]
    random.shuffle(sources)
    for source in sources:
        try:
            item = source()
            item = validate_question(item)
            if item:
                return item
        except Exception as exc:
            print("Question provider unavailable:", source.__name__, exc)
    return None
