"""Extra factual quiz providers; batch fetch, bounded timeouts, no fabricated answers."""
import random
import urllib.parse
import urllib.request
import json
from core.question_quality import cached_json
from core.fact_question_engine import _quiz

def _get(url):
    return cached_json(url)

def open_library_question():
    subject=random.choice(("science","history","astronomy","mathematics","biology","technology","geography","fiction"))
    params=urllib.parse.urlencode({"q":"subject:"+subject,"fields":"title,author_name,first_publish_year,language,edition_count,ratings_count,readinglog_count,want_to_read_count,currently_reading_count,already_read_count,number_of_pages_median,cover_i",
                                    "limit":60,"page":random.randint(1,8)})
    rows=_get("https://openlibrary.org/search.json?"+params).get("docs",[])
    rows=[r for r in rows if r.get("title") and r.get("author_name") and isinstance(r.get("first_publish_year"),int)]
    random.shuffle(rows)
    from core.metadata_quiz import field_quiz, OPENLIBRARY_FIELDS
    if random.random()<0.65:
        item=field_quiz(rows,OPENLIBRARY_FIELDS,"title","openlibrary")
        if item:
            return item
    for row in rows:
        title=row["title"]
        if not 5<=len(title)<=90:continue
        kinds=["author","year"]
        if row.get("edition_count") and row["edition_count"]>=1:
            kinds.append("editions")
        if row.get("language"):
            kinds.append("language")
        random.shuffle(kinds)
        for kind in kinds:
            if kind=="author":
                correct=row["author_name"][0]
                others=[r["author_name"][0] for r in rows if r.get("author_name") and r["title"]!=title]
                item=_quiz("Who wrote the book "+title+"?",correct,others,"openlibrary:author")
            elif kind=="year":
                year=row["first_publish_year"]
                if not 1450<=year<=2026:continue
                others=[r["first_publish_year"] for r in rows if r["first_publish_year"]!=year]
                item=_quiz("In what year was the book "+title+" first published?",year,others,"openlibrary:year")
            elif kind=="editions":
                count=row["edition_count"]
                wrong=[r["edition_count"] for r in rows if isinstance(r.get("edition_count"),int) and r["edition_count"]!=count]
                item=_quiz("How many editions does Open Library currently list for "+title+"?",count,wrong,"openlibrary:editions")
            else:
                codes={"eng":"English","fre":"French","spa":"Spanish","ger":"German",
                       "ita":"Italian","por":"Portuguese","jpn":"Japanese",
                       "rus":"Russian","chi":"Chinese","ara":"Arabic"}
                languages=[codes[x] for x in row["language"] if x in codes]
                if len(languages)!=1:continue
                others=[v for v in codes.values() if v!=languages[0]]
                item=_quiz("Which language is listed for the book "+title+"?",languages[0],others,"openlibrary:language")
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
    from core.world_bank_indicators import METRICS
    code=random.choice(tuple(METRICS))
    name,unit=METRICS[code]
    template='What was the {} ({}) in {{}} in {{}}?'.format(name,unit)
    year=random.randint(2010,2022)
    params=urllib.parse.urlencode({"format":"json","date":str(year),"per_page":300})
    data=_get("https://api.worldbank.org/v2/country/all/indicator/"+code+"?"+params)
    if not isinstance(data,list) or len(data)<2 or not isinstance(data[1],list):return None
    countries=_get("https://api.worldbank.org/v2/country?format=json&per_page=400")
    valid=set()
    if isinstance(countries,list) and len(countries)>1 and isinstance(countries[1],list):
        valid={r.get("iso2Code") for r in countries[1] if (r.get("region") or {}).get("id")!="NA" and r.get("iso2Code")}
    rows=[r for r in data[1] if isinstance(r.get("value"),(int,float))
          and r.get("country",{}).get("id") in valid
          and r.get("country",{}).get("value")]
    if len(rows)<5:return None
    row=random.choice(rows)
    country=row["country"]["value"]
    value=row["value"]
    if unit=="current US dollars" and abs(value)>1e9:fmt=lambda x:f"{x/1e9:,.2f} billion"
    elif unit in ("people","sq km","current US dollars"):fmt=lambda x:f"{x:,.0f}"
    else:fmt=lambda x:f"{x:.2f}"
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
    from core.metadata_quiz import field_quiz, NASA_FIELDS
    if random.random()<0.7:
        item=field_quiz(rows,NASA_FIELDS,"title","nasa")
        if item:
            return item
    for row in rows:
        title=row["title"]
        if not 12<=len(title)<=95:continue
        year=row["date_created"][:4]
        kinds=["year","center"]
        random.shuffle(kinds)
        for kind in kinds:
            if kind=="year":
                if not year.isdigit():
                    continue
                others=[r["date_created"][:4] for r in rows if r["date_created"][:4]!=year]
                item=_quiz("What year does NASA's catalog give for the image titled "+title+"?",year,others,"nasa:catalog_year")
            else:
                center=row["center"]
                others=[r["center"] for r in rows if r.get("center") and r["center"]!=center]
                item=_quiz("Which NASA center is credited for the image titled "+title+"?",center,others,"nasa:center")
            if item:
                return item
    return None
