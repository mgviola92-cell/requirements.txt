"""Fact-backed quiz generators. Every answer comes from the returned data."""
import os
import random
import urllib.parse
import urllib.request
import json

TOPICS = [
 ("capital","wdt:P31 wd:Q6256","wdt:P36","What is the capital of {}?"),
 ("currency","wdt:P31 wd:Q6256","wdt:P38","Which currency is used in {}?"),
 ("continent","wdt:P31 wd:Q6256","wdt:P30","On which continent is {}?"),
 ("official language","wdt:P31 wd:Q6256","wdt:P37","Which is an official language of {}?"),
 ("country calling code","wdt:P31 wd:Q6256","wdt:P474","What is the calling code of {}?"),
 ("element number","wdt:P31 wd:Q11344","wdt:P1086","What is the atomic number of {}?"),
 ("element symbol","wdt:P31 wd:Q11344","wdt:P246","What is the chemical symbol for {}?"),
 ("element discoverer","wdt:P31 wd:Q11344","wdt:P61","Who discovered the element {}?"),
 ("planet discoverer","wdt:P31 wd:Q634","wdt:P61","Who discovered {}?"),
 ("river mouth","wdt:P31 wd:Q4022","wdt:P403","Where does the river {} flow into?"),
 ("mountain range","wdt:P31 wd:Q8502","wdt:P4552","Which mountain range contains {}?"),
 ("book author","wdt:P31 wd:Q571","wdt:P50","Who wrote {}?"),
 ("film director","wdt:P31 wd:Q11424","wdt:P57","Who directed {}?"),
 ("film composer","wdt:P31 wd:Q11424","wdt:P86","Who composed music for {}?"),
 ("film country","wdt:P31 wd:Q11424","wdt:P495","Which country produced the film {}?"),
 ("language family","wdt:P31 wd:Q34770","wdt:P279","Which family or class includes the language {}?"),
 ("animal taxon parent","wdt:P31 wd:Q16521","wdt:P171","Which taxon is the parent of {}?"),
 ("university location","wdt:P31 wd:Q3918","wdt:P131","Where is {} located?"),
 ("company founder","wdt:P31 wd:Q4830453","wdt:P112","Who founded {}?"),
 ("invention inventor","wdt:P31 wd:Q15401930","wdt:P61","Who invented {}?"),
]

def _read(url):
    req=urllib.request.Request(url,headers={"User-Agent":"MyanmarGroupGamesBot/1.0 (quiz)","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=5) as resp:
        return json.load(resp)

def _quiz(question, correct, distractors, source):
    correct=str(correct).strip()
    others=list(dict.fromkeys(str(x).strip() for x in distractors if str(x).strip()!=correct))
    if not correct or len(others)<3:
        return None
    answers=[correct]+random.sample(others,3)
    random.shuffle(answers)
    return {"question":question,"answers":answers,"correct_index":answers.index(correct),"source":source}

def wikidata_question():
    title,subject_filter,relation,template=random.choice(TOPICS)
    offset=random.choice((0,100,250,500,1000))
    query=("SELECT ?subjectLabel ?valueLabel WHERE { ?subject "+subject_filter+
           "; "+relation+" ?value. SERVICE wikibase:label { bd:serviceParam wikibase:language \"en\". } } "+
           "LIMIT 110 OFFSET "+str(offset))
    url="https://query.wikidata.org/sparql?"+urllib.parse.urlencode({"query":query,"format":"json"})
    data=_read(url)
    pairs=[]
    for r in data.get("results",{}).get("bindings",[]):
        try:
            a=r["subjectLabel"]["value"]; b=r["valueLabel"]["value"]
            if 2<=len(a)<=85 and 1<=len(b)<=70 and not a.startswith("Q") and not b.startswith("Q"):
                pairs.append((a,b))
        except (KeyError,TypeError):
            continue
    pairs=list(dict.fromkeys(pairs))
    random.shuffle(pairs)
    for a,b in pairs[:20]:
        item=_quiz(template.format(a),b,[v for _,v in pairs if v!=b],"wikidata:"+title)
        if item:return item
    return None

def openalex_question():
    key=os.getenv("OPENALEX_API_KEY")
    params={"filter":"from_publication_date:2015-01-01,cited_by_count:>200",
            "per-page":50,"page":random.randint(1,25),
            "select":"title,publication_year,cited_by_count,authorships,primary_location"}
    if key:params["api_key"]=key
    data=_read("https://api.openalex.org/works?"+urllib.parse.urlencode(params))
    rows=[r for r in data.get("results",[]) if isinstance(r.get("title"),str)
          and 15<=len(r["title"])<=100 and isinstance(r.get("publication_year"),int)]
    random.shuffle(rows)
    for row in rows:
        title=row["title"]
        year=row["publication_year"]
        author_names=[a.get("author",{}).get("display_name") for a in row.get("authorships",[])]
        author_names=[a for a in author_names if a]
        journal=((row.get("primary_location") or {}).get("source") or {}).get("display_name")
        kinds=["year"]
        if author_names:kinds.append("author")
        if journal:kinds.append("journal")
        random.shuffle(kinds)
        for kind in kinds:
            if kind=="year":
                wrong=[str(y) for y in range(max(1900,year-9),year+10) if y!=year]
                item=_quiz("In what year was this study published: "+title+"?",str(year),wrong,"openalex:year")
            elif kind=="author":
                others=[a.get("author",{}).get("display_name") for r in rows for a in r.get("authorships",[])]
                item=_quiz("Who is an author of this research: "+title+"?",author_names[0],
                           [x for x in others if x and x not in author_names],"openalex:author")
            else:
                others=[((r.get("primary_location") or {}).get("source") or {}).get("display_name") for r in rows]
                item=_quiz("Which journal or source published: "+title+"?",journal,
                           [x for x in others if x],"openalex:journal")
            if item:return item
    return None
