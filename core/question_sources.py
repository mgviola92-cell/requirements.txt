"""Additional question sources for Trivia and Pair Challenge; network failures are safe."""
import html
import json
import random
import urllib.parse
import urllib.request

def _json(url, timeout=5):
    req = urllib.request.Request(url, headers={"User-Agent": "MyanmarGroupGamesBot/1.0 (educational trivia)", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.load(response)

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

def fetch_question():
    sources = [trivia_api, wikidata_capital]
    random.shuffle(sources)
    for source in sources:
        try:
            item = source()
            if item:
                return item
        except Exception as exc:
            print("Question provider unavailable:", source.__name__, exc)
    return None
