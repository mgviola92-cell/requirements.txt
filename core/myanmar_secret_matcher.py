"""Conservative Myanmar secret-word matching, without fuzzy guessing."""
import re
import unicodedata

# Zero-width display separators do not change the lexical answer.
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\ufeff\u2060"), None)
_SPACES = re.compile(r"\s+",re.UNICODE)

def normalize_secret(value):
    if not isinstance(value,str):
        return ""
    text=unicodedata.normalize("NFC",value).translate(_INVISIBLE).strip()
    # Normalize the two common placements of Myanmar dot below and asat.
    # Preserve consonants, vowels, and tone marks otherwise.
    text=text.replace("\u1037\u103a", "\u103a\u1037")
    return _SPACES.sub("",text).casefold()

def matches_secret(guess,secret):
    return bool(normalize_secret(guess)) and normalize_secret(guess)==normalize_secret(secret)
