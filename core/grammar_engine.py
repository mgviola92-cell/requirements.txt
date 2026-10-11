"""Free offline English grammar checks with conservative, explainable rules.

This is NOT a general-purpose native-level grammar model. No text is sent
to a third-party API. Only high-confidence patterns are auto-corrected.
"""
import re

RULES = (
 ("DID_QUESTION",re.compile(r"\bdid\s+(I|you|he|she|it|we|they)\s+(went|ate|saw|came|made|took|wrote|bought|played|liked|visited|studied|watched|worked|called)\b",re.I),
  {"went":"go","ate":"eat","saw":"see","came":"come","made":"make","took":"take","wrote":"write","bought":"buy","played":"play","liked":"like","visited":"visit","studied":"study","watched":"watch","worked":"work","called":"call"},
  "Did နဲ့မေးခွန်းဖွဲ့ပြီးရင် Verb ကို Past Form မဟုတ်ဘဲ Base Form (V1) သုံးရပါတယ်။","Did + Subject + V1 + ... ?"),
 ("MODAL_BASE",re.compile(r"\b(can|can't|cannot|could|couldn't|will|won't|would|wouldn't|should|shouldn't|must|might|may)\s+(went|ate|saw|came|made|took|wrote|bought|played|liked|visited|studied|watched|worked|called)\b",re.I),
  {"went":"go","ate":"eat","saw":"see","came":"come","made":"make","took":"take","wrote":"write","bought":"buy","played":"play","liked":"like","visited":"visit","studied":"study","watched":"watch","worked":"work","called":"call"},
  "Modal Verb (can/will/should စသည်) နောက်မှာ Base Form (V1) သုံးပါတယ်။","Subject + Modal + V1"),
 ("DOES_QUESTION",re.compile(r"\bdoes\s+(he|she|it)\s+(likes|plays|wants|goes|eats|works|studies|watches|knows|has)\b",re.I),
  {"likes":"like","plays":"play","wants":"want","goes":"go","eats":"eat","works":"work","studies":"study","watches":"watch","knows":"know","has":"have"},
  "Does နဲ့မေးခွန်းဖွဲ့ရင် Main Verb မှာ s/es မထည့်ရပါဘူး။","Does + He/She/It + V1 + ... ?"),
 ("DID_BASE",re.compile(r"\b(didn't|did not)\s+(went|ate|saw|came|made|took|wrote|bought|played|liked|visited|studied|watched|worked|called)\b",re.I),
  {"went":"go","ate":"eat","saw":"see","came":"come","made":"make","took":"take","wrote":"write","bought":"buy","played":"play","liked":"like","visited":"visit","studied":"study","watched":"watch","worked":"work","called":"call"},
  "didn't / did not နောက်မှာ Verb ရဲ့ Base Form (V1) သုံးရပါတယ်။","Subject + didn't + V1"),
 ("DOES_BASE",re.compile(r"\b(doesn't|does not)\s+(likes|plays|wants|goes|eats|works|studies|watches|knows|has)\b",re.I),
  {"likes":"like","plays":"play","wants":"want","goes":"go","eats":"eat","works":"work","studies":"study","watches":"watch","knows":"know","has":"have"},
  "doesn't / does not နောက်က Verb ကို s/es မထည့်ဘဲ Base Form သုံးရပါတယ်။","Subject + doesn't + V1"),
 ("HE_SHE_DONT",re.compile(r"\b(he|she|it)\s+don't\b",re.I),None,
  "Present Simple မှာ he/she/it နဲ့ အငြင်းပုံစံရေးရင် doesn't သုံးပါတယ်။","He/She/It + doesn't + V1"),
 ("I_IS",re.compile(r"\bI\s+is\b",re.I),None,
  "Present Tense မှာ I နဲ့ am ကို တွဲသုံးပါတယ်။","I + am + adjective/noun/V-ing"),
 ("YOU_IS",re.compile(r"\b(you|we|they)\s+is\b",re.I),None,
  "you/we/they နဲ့ Present Tense မှာ are ကို သုံးပါတယ်။","You/We/They + are + ..."),
 ("HE_ARE",re.compile(r"\b(he|she|it)\s+are\b",re.I),None,
  "he/she/it နဲ့ Present Tense မှာ is ကို သုံးပါတယ်။","He/She/It + is + ..."),
 ("I_HAS",re.compile(r"\bI\s+has\b",re.I),None,
  "I နဲ့ ပိုင်ဆိုင်မှုဖော်ပြရင် have ကို သုံးပါတယ်။","I + have + noun"),
 ("THEY_HAS",re.compile(r"\b(you|we|they)\s+has\b",re.I),None,
  "you/we/they နဲ့ have ကို သုံးပါတယ်။","You/We/They + have + noun"),
 ("HE_HAVE",re.compile(r"\b(he|she|it)\s+have\b(?!\s+(?:been|done|gone|had|to)\b)",re.I),None,
  "Present Simple မှာ he/she/it နဲ့ ပိုင်ဆိုင်မှုဖော်ပြရင် has သုံးပါတယ်။","He/She/It + has + noun"),
)

def _preserve_case(original, replacement):
    if original.isupper(): return replacement.upper()
    if original[:1].isupper(): return replacement.capitalize()
    return replacement

def analyze(sentence, max_issues=3):
    if not isinstance(sentence,str) or not (4 <= len(sentence.strip()) <= 500):
        return []
    if "http://" in sentence or "https://" in sentence or sentence.lstrip().startswith("/"):
        return []
    results=[]
    for rule_id,pattern,verb_map,explanation,structure in RULES:
        match=pattern.search(sentence)
        if not match:continue
        piece=match.group(0)
        if rule_id in ("DID_BASE","DOES_BASE","DID_QUESTION","MODAL_BASE","DOES_QUESTION"):
            wrong=match.group(3) if rule_id in ("DID_QUESTION","DOES_QUESTION") else match.group(2)
            right=verb_map[wrong.lower()]
            revised=piece[:match.start(3 if rule_id in ("DID_QUESTION","DOES_QUESTION") else 2)-match.start()]+_preserve_case(wrong,right)
        elif rule_id=="HE_SHE_DONT":
            revised=re.sub("don't","doesn't",piece,flags=re.I)
        else:
            replacements={"I_IS":"am","YOU_IS":"are","HE_ARE":"is",
                          "I_HAS":"have","THEY_HAS":"have","HE_HAVE":"has"}
            words=piece.split()
            revised=words[0]+" "+replacements[rule_id]
        results.append({"rule":rule_id,"original":piece,"replacement":revised,
                        "corrected":sentence[:match.start()]+revised+sentence[match.end():],
                        "explanation":explanation,"pattern":structure})
        if len(results)>=max_issues:break
    return results

def explain(sentence):
    found=analyze(sentence)
    if not found:
        return ("✅ သိသာတဲ့ Grammar အမှားကို Local Rules နဲ့ မတွေ့ပါဘူး။\n"
                "ဒါဟာ စာကြောင်း 100% မှန်တယ်လို့ အာမခံတာ မဟုတ်ပါဘူး။")
    fixed=sentence
    # Match by exact location on each iteration, allowing multiple independent
    # errors without repeating the same replacement or looping indefinitely.
    applied=set()
    for _ in range(12):
        candidates=[item for item in analyze(fixed,max_issues=30)
                    if item["rule"] not in applied]
        if not candidates:break
        item=candidates[0]
        applied.add(item["rule"])
        if item["corrected"]==fixed:break
        fixed=item["corrected"]
    lines=["📘 English Grammar Coach",f"❌ Original: {sentence}",f"✅ Correct: {fixed}"]
    for index,issue in enumerate(found,1):
        lines.extend([f"\n{index}. {issue['original']} → {issue['replacement']}",
                      f"💡 {issue['explanation']}",f"📐 Pattern: {issue['pattern']}"])
    return "\n".join(lines)
