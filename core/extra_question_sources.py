"""Extra factual quiz providers; batch fetch, bounded timeouts, no fabricated answers."""
import random
import urllib.parse
import urllib.request
import json
from core.fact_question_engine import _quiz

def _get(url):
    request=urllib.request.Request(url,headers={"User-Agent":"MyanmarGroupGamesBot/1.0 (educational quiz)","Accept":"application/json"})
    with urllib.request.urlopen(request,timeout=5) as response:
        return json.load(response)

def open_library_question():
    subject=random.choice(("science","history","astronomy","mathematics","biology","technology","geography","fiction"))
    params=urllib.parse.urlencode({"q":"subject:"+subject,"fields":"title,author_name,first_publish_year,language,edition_count",
                                    "limit":60,"page":random.randint(1,8)})
    rows=_get("https://openlibrary.org/search.json?"+params).get("docs",[])
    rows=[r for r in rows if r.get("title") and r.get("author_name") and isinstance(r.get("first_publish_year"),int)]
    random.shuffle(rows)
    for row in rows:
        title=row["title"]
        if not 5<=len(title)<=90:continue
        kinds=["author","year"]
        random.shuffle(kinds)
        for kind in kinds:
            if kind=="author":
                correct=row["author_name"][0]
                others=[r["author_name"][0] for r in rows if r.get("author_name") and r["title"]!=title]
                item=_quiz("Who wrote the book "+title+"?",correct,others,"openlibrary:author")
            else:
                year=row["first_publish_year"]
                if not 1450<=year<=2026:continue
                others=[r["first_publish_year"] for r in rows if r["first_publish_year"]!=year]
                item=_quiz("In what year was the book "+title+" first published?",year,others,"openlibrary:year")
            if item:return item
    return None

INDICATORS={
    "SP.POP.TOTL":("population","What was the population of {} in {}?"),
    "NY.GDP.MKTP.CD":("GDP","What was the approximate GDP (US dollars) of {} in {}?"),
    "SP.DYN.LE00.IN":("life expectancy","What was the approximate life expectancy (years) in {} in {}?"),
    "AG.SRF.TOTL.K2":("surface area","What was the surface area (sq km) of {} in {}?"),
    "SP.URB.TOTL.IN.ZS":("urban population","What percent of {} lived in urban areas in {}?"),
    "EN.ATM.CO2E.PC":("CO2 emissions","What was the CO2 emissions (metric tons per capita) of {} in {}?"),
    "IT.NET.USER.ZS":("internet users","What percent of people used the internet in {} in {}?"),
    "SE.ADT.LITR.ZS":("literacy rate","What was the adult literacy rate in {} in {}?"),
}
def world_bank_question():
    code=random.choice(tuple(INDICATORS))
    name,template=INDICATORS[code]
    year=random.randint(2010,2022)
    params=urllib.parse.urlencode({"format":"json","date":str(year),"per_page":300})
    data=_get("https://api.worldbank.org/v2/country/all/indicator/"+code+"?"+params)
    if not isinstance(data,list) or len(data)<2 or not isinstance(data[1],list):return None
    rows=[r for r in data[1] if r.get("value") is not None and r.get("countryiso3code")]
    if len(rows)<5:return None
    row=random.choice(rows)
    country=row["country"]["value"]
    value=row["value"]
    if code in ("SP.POP.TOTL","AG.SRF.TOTL.K2"):fmt=lambda x:f"{x:,.0f}"
    elif code=="NY.GDP.MKTP.CD":fmt=lambda x:f"{x/1e9:,.1f} billion"
    else:fmt=lambda x:f"{x:.1f}"
    correct=fmt(value)
    others=[fmt(r["value"]) for r in rows if r["country"]["value"]!=country]
    return _quiz(template.format(country,year),correct,others,"worldbank:"+name)

def nasa_images_question():
    term=random.choice(("galaxy","nebula","moon","mars","saturn","jupiter","asteroid"))
    params=urllib.parse.urlencode({"q":term,"media_type":"image","page_size":60,"page":random.randint(1,3)})
    data=_get("https://images-api.nasa.gov/search?"+params)
    rows=[]
    for item in data.get("collection",{}).get("items",[]):
        meta=(item.get("data") or [{}])[0]
        if meta.get("title") and meta.get("date_created") and meta.get("center"):
            rows.append(meta)
    if len(rows)<5:return None
    random.shuffle(rows)
    for row in rows:
        title=row["title"]
        if not 12<=len(title)<=95:continue
        year=row["date_created"][:4]
        if not year.isdigit():continue
        others=[r["date_created"][:4] for r in rows if r["date_created"][:4]!=year]
        item=_quiz("In which year was this NASA image created: "+title+"?",year,others,"nasa:image_year")
        if item:return item
    return None
