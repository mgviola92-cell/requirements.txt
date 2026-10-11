"""Question engine audit: python -m tests.question_audit --samples 100 --live

Offline mode checks procedural generation and source catalogues without network.
Live mode probes each public provider with bounded calls; never posts to Telegram.
Reports are saved under reports/ (JSON and Markdown). No database writes.
"""
import argparse
import collections
import datetime
import json
import pathlib
import random
import time
import traceback
import urllib.error

from core.procedural_questions import KINDS, generate
from core.question_quality import validate_question
from core.fact_question_engine import TOPICS
from core.wikidata_more_topics import MORE_TOPICS
from core.world_bank_indicators import METRICS
from core.wikipedia_questions import CATEGORIES
from core.metadata_quiz import OPENALEX_FIELDS, OPENLIBRARY_FIELDS, NASA_FIELDS

def inspect_procedural(samples):
    from unittest.mock import patch
    results=[]
    for kind in KINDS:
        for index in range(samples):
            started=time.monotonic()
            try:
                with patch("core.procedural_questions.random.choice",
                           side_effect=lambda values: kind if values is KINDS else random.Random(index+17).choice(values)):
                    item=generate(level=index%6+1)
                options=item["options"]
                valid=(len(options)==2 and options[0]!=options[1]
                       and item["answer"] in ("a","b") and "?" in item["question"])
                results.append({"source":"procedural","type":kind,"valid":valid,
                                "question":item["question"],"answer":options[0 if item["answer"]=="a" else 1],
                                "seconds":round(time.monotonic()-started,4),
                                "error":None if valid else "Invalid two-choice item"})
            except Exception as exc:
                results.append({"source":"procedural","type":kind,"valid":False,
                                "question":"","answer":"","seconds":round(time.monotonic()-started,4),
                                "error":repr(exc)})
    return results

def inspect_live(samples):
    from core.question_sources import trivia_api
    from core.fact_question_engine import wikidata_question,openalex_question
    from core.extra_question_sources import open_library_question,world_bank_question,nasa_images_question
    from core.wikipedia_questions import wikipedia_question
    sources={
        "the_trivia_api":trivia_api,
        "wikidata":wikidata_question,
        "openalex":openalex_question,
        "openlibrary":open_library_question,
        "worldbank":world_bank_question,
        "nasa":nasa_images_question,
        "wikipedia":wikipedia_question,
    }
    results=[]
    for name,provider in sources.items():
        for _ in range(samples):
            started=time.monotonic()
            try:
                raw=provider()
                item=validate_question(raw)
                valid=item is not None
                results.append({"source":name,"type":(raw or {}).get("source",name) if isinstance(raw,dict) else name,
                                "valid":valid,"question":item["question"] if valid else "",
                                "answer":item["answers"][item["correct_index"]] if valid else "",
                                "seconds":round(time.monotonic()-started,3),
                                "error":None if valid else "Provider returned no valid question"})
            except Exception as exc:
                status="rate_limited" if isinstance(exc,urllib.error.HTTPError) and exc.code==429 else "error"
                results.append({"source":name,"type":name,"valid":False,"status":status,
                                "question":"","answer":"","seconds":round(time.monotonic()-started,3),
                                "error":repr(exc)[:350]})
    return results

def build_report(rows, live):
    by_source=collections.defaultdict(list)
    for row in rows:
        by_source[row["source"]].append(row)
    summary={}
    for source,items in sorted(by_source.items()):
        successes=[x for x in items if x["valid"]]
        unique=len({x["question"].casefold().strip() for x in successes})
        summary[source]={
            "attempts":len(items),"valid":len(successes),"invalid":len(items)-len(successes),
            "rate_limited":sum(x.get("status")=="rate_limited" for x in items),
            "unique_questions":unique,"duplicate_questions":len(successes)-unique,
            "avg_seconds":round(sum(x["seconds"] for x in items)/len(items),3),
            "observed_types":sorted({x["type"] for x in successes}),
            "errors":[x["error"] for x in items if x["error"]][:8],
        }
    catalogues={
        "procedural_types":len(KINDS),
        "wikidata_rules":len(TOPICS+MORE_TOPICS),
        "worldbank_indicators":len(METRICS),
        "wikipedia_categories":len(CATEGORIES),
        "openalex_metadata_fields":len(OPENALEX_FIELDS),
        "openlibrary_metadata_fields":len(OPENLIBRARY_FIELDS),
        "nasa_metadata_fields":len(NASA_FIELDS),
    }
    return {"generated_at_utc":datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "mode":"live+offline" if live else "offline",
            "note":"Structure and consistency checks cannot prove external factual correctness.",
            "catalogues":catalogues,"summary":summary,"samples":rows}

def save_report(report, directory):
    directory=pathlib.Path(directory)
    directory.mkdir(parents=True,exist_ok=True)
    (directory/"question_audit.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    lines=["# Question Engine Audit","","Mode: **"+report["mode"]+"**",
           "","Generated (UTC): "+report["generated_at_utc"],"",
           "> "+report["note"],"","## Catalogue inventory",""]
    lines += ["- "+key+": "+str(value) for key,value in report["catalogues"].items()]
    lines += ["","## Generation results","","| Source | Attempts | Valid | Invalid | Duplicates | Average seconds |","|---|---:|---:|---:|---:|---:|"]
    for name,stats in report["summary"].items():
        lines.append("| "+name+" | "+str(stats["attempts"])+" | "+str(stats["valid"])+" | "+
                     str(stats["invalid"])+" | "+str(stats["duplicate_questions"])+" | "+
                     str(stats["avg_seconds"])+" |")
    lines += ["","## Rate-limited attempts",""]
    lines.extend("- "+name+": "+str(stats["rate_limited"]) for name,stats in report["summary"].items() if stats["rate_limited"])
    lines += ["","## Errors (first 8 per source)",""]
    for name,stats in report["summary"].items():
        if stats["errors"]:
            lines.append("### "+name)
            lines.extend("- "+error.replace("\n"," ") for error in stats["errors"])
    lines += ["","## Example questions",""]
    for name in report["summary"]:
        lines.append("### "+name)
        samples=[x for x in report["samples"] if x["source"]==name and x["valid"]][:5]
        lines.extend("- "+x["question"].replace("\n"," ")+" — **"+x["answer"]+"**" for x in samples)
    (directory/"question_audit.md").write_text("\n".join(lines)+"\n",encoding="utf-8")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--samples",type=int,default=20,help="Offline samples per procedural type (max 1000)")
    parser.add_argument("--live",action="store_true",help="Call external APIs; may take time and fail due to rate limits")
    parser.add_argument("--live-samples",type=int,default=2,help="Live calls per source (max 10)")
    parser.add_argument("--output",default="reports")
    args=parser.parse_args()
    if not 1<=args.samples<=1000 or not 1<=args.live_samples<=10:
        parser.error("samples must be 1..1000 and live-samples 1..10")
    rows=inspect_procedural(args.samples)
    if args.live:
        rows.extend(inspect_live(args.live_samples))
    report=build_report(rows,args.live)
    save_report(report,args.output)
    for name,stats in report["summary"].items():
        print(name+": "+str(stats["valid"])+"/"+str(stats["attempts"])+
              " valid, "+str(stats["duplicate_questions"])+" duplicates")
    print("Reports: "+str(pathlib.Path(args.output).resolve()))
    return 1 if any(x["invalid"] for x in report["summary"].values()) else 0

if __name__=="__main__":
    raise SystemExit(main())
