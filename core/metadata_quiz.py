"""Data-backed multiple-choice templates shared by OpenAlex, Open Library and NASA.

Only fields present in the provider response are eligible. Wrong choices are
taken from the same data batch, excluding all known correct values.
"""
import random
from core.question_quality import make_mcq

def _value(row, path):
    value=row
    for key in path.split("."):
        if not isinstance(value,dict):
            return None
        value=value.get(key)
    if isinstance(value,(str,int,float)) and not isinstance(value,bool):
        result=str(value).strip()
        if 1<=len(result)<=140:
            return result
    return None

def field_quiz(rows, fields, label_key, source):
    """fields: (field_path, question_template) pairs, using record title as {title}."""
    candidates=list(rows)
    random.shuffle(candidates)
    for row in candidates[:35]:
        title=_value(row,label_key)
        if not title or not 5<=len(title)<=95:
            continue
        choices=list(fields)
        random.shuffle(choices)
        for path,template in choices:
            correct=_value(row,path)
            if not correct:
                continue
            # A record may have several valid values; this routine handles
            # only single-valued scalar metadata.
            others=[_value(other,path) for other in rows if other is not row]
            wrong=[v for v in others if v and v.casefold()!=correct.casefold()]
            item=make_mcq(template.format(title=title),correct,wrong,source+":"+path)
            if item:
                return item
    return None

OPENALEX_FIELDS=(
 ("publication_year","In which year was the research '{title}' published?"),
 ("publication_date","What exact publication date is recorded for '{title}'?"),
 ("type","What type of scholarly work is '{title}'?"),
 ("language","What language code is recorded for '{title}'?"),
 ("cited_by_count","How many citations does OpenAlex currently record for '{title}'?"),
 ("primary_topic.display_name","What primary research topic is assigned to '{title}'?"),
 ("primary_topic.subfield.display_name","What research subfield is assigned to '{title}'?"),
 ("primary_topic.field.display_name","What research field is assigned to '{title}'?"),
 ("primary_topic.domain.display_name","What broad research domain is assigned to '{title}'?"),
 ("primary_location.source.display_name","Which publication source hosts '{title}'?"),
 ("primary_location.source.type","What type of publication source hosts '{title}'?"),
 ("open_access.oa_status","What open-access status is recorded for '{title}'?"),
 ("biblio.volume","In which volume is '{title}' listed?"),
 ("biblio.issue","In which issue is '{title}' listed?"),
 ("biblio.first_page","On what first page does '{title}' begin?"),
 ("biblio.last_page","On what last page does '{title}' end?"),
)
OPENLIBRARY_FIELDS=(
 ("first_publish_year","What was the first publication year of '{title}'?"),
 ("edition_count","How many editions does Open Library list for '{title}'?"),
 ("ratings_count","How many ratings does Open Library record for '{title}'?"),
 ("readinglog_count","How many reading-log entries are recorded for '{title}'?"),
 ("want_to_read_count","How many users marked '{title}' want-to-read?"),
 ("currently_reading_count","How many users marked '{title}' currently-reading?"),
 ("already_read_count","How many users marked '{title}' already-read?"),
 ("number_of_pages_median","What median page count is listed for '{title}'?"),
)
NASA_FIELDS=(
 ("date_created","What catalog date is recorded for the NASA item '{title}'?"),
 ("center","Which NASA center is credited for '{title}'?"),
 ("location","Which location is listed for the NASA item '{title}'?"),
 ("photographer","Who is credited as photographer of '{title}'?"),
 ("secondary_creator","Who is listed as secondary creator of '{title}'?"),
)
