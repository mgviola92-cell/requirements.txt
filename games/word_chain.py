"""Group Word Chain. EN: last letter; MY: last pronounced syllable's initial consonant."""
import json
import random
import re
import threading
import time
import uuid
from pathlib import Path

from core.sessions import can_start_session, start_session, end_session

ROUND_MIN_SECONDS = 8 * 60
ROUND_MAX_SECONDS = 15 * 60
IDLE_SECONDS = 60
SELF_RETRY_SECONDS = 20
_lock = threading.RLock()
_games = {}
_WORDS = None
_START_EN = ("apple", "tiger", "river", "orange", "green", "music", "garden", "winter")
_START_MY = ("ပင်စည်", "စားစရာ", "ရထား", "သစ်ပင်", "ပန်းကန်", "လေယာဉ်")

# Myanmar letters (not combining vowel signs, asat or medials).
_MY_CONSONANT = re.compile(r'[\u1000-\u1021\u103f]')
_MY_WRITING = re.compile(r'[\u1000-\u109f\uaa60-\uaa7f ]+')


def _english_words():
    global _WORDS
    if _WORDS is None:
        path = Path(__file__).resolve().parent.parent / 'data' / 'word_chain_en.json'
        _WORDS = set(json.loads(path.read_text(encoding='utf8')))
    return _WORDS


def _myanmar_onsets(value):
    """Extract base consonants, excluding codas killed by asat (e.g., င်, ည်).

    Myanmar orthography is more complex than Unicode character boundaries. This
    handles ordinary unstacked written words (e.g., ပင်စည် => ပ,စ).
    """
    result = []
    for i, ch in enumerate(value):
        if not _MY_CONSONANT.fullmatch(ch):
            continue
        # A base consonant immediately followed by virama (stacked letters)
        # or asat (final consonant) is not the syllable onset to chain from.
        if i + 1 < len(value) and value[i + 1] in ('\u103a', '\u1039'):
            continue
        result.append(ch)
    return result


def normalize(text, mode):
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', str(text or '')).strip()
    if mode == 'en':
        return text.casefold() if re.fullmatch(r'[A-Za-z]{3,12}', text) else None
    text = ' '.join(text.split())
    if not text or len(text) > 40 or not _MY_WRITING.fullmatch(text):
        return None
    if not _myanmar_onsets(text):
        return None
    # Both "ပင်စည်" and naturally spaced phrases are accepted.
    return text


def _first(value, mode):
    return value[0] if mode == 'en' else _myanmar_onsets(value)[0]


def _last(value, mode):
    return value[-1] if mode == 'en' else _myanmar_onsets(value)[-1]


def get_game(chat_id):
    with _lock:
        game = _games.get(chat_id)
        return dict(game) if game else None


def start_game(chat_id, mode='en'):
    mode = 'my' if mode in ('my', 'mm', 'burmese', 'မြန်မာ') else 'en'
    with _lock:
        if chat_id in _games:
            return False, 'word_chain'
        allowed, blocker = can_start_session(chat_id, 'word_chain')
        if not allowed:
            return False, blocker
        round_seconds = random.randint(ROUND_MIN_SECONDS, ROUND_MAX_SECONDS)
        started, session = start_session(chat_id, 'word_chain', duration=round_seconds + 5)
        if not started:
            return False, session
        starter = random.choice(_START_MY if mode == 'my' else _START_EN)
        now = time.monotonic()
        game = {
            'id': uuid.uuid4().hex, 'chat_id': chat_id, 'mode': mode,
            'word': starter, 'required': _last(starter, mode),
            'used': {starter}, 'last_user': None, 'last_move_at': None, 'scores': {}, 'names': {},
            'started': now, 'round_seconds': round_seconds, 'deadline': now + round_seconds,
            'idle_deadline': now + IDLE_SECONDS, 'moves': 0,
            'message_id': None,
        }
        _games[chat_id] = game
        return True, dict(game)


def set_message_id(chat_id, game_id, message_id):
    with _lock:
        game = _games.get(chat_id)
        if game and game['id'] == game_id:
            game['message_id'] = message_id
            return True
        return False


def submit(chat_id, game_id, user_id, user_name, text):
    with _lock:
        game = _games.get(chat_id)
        if not game or game['id'] != game_id:
            return {'status': 'closed'}
        now = time.monotonic()
        if now >= min(game['idle_deadline'], game['deadline']):
            return {'status': 'expired'}
        word = normalize(text, game['mode'])
        if not word:
            return {'status': 'ignore'}
        if game['mode'] == 'en' and word not in _english_words():
            return {'status': 'ignore'}
        if _first(word, game['mode']) != game['required']:
            return {'status': 'ignore'}
        if word in game['used']:
            return {'status': 'used'}
        self_retry = game['last_user'] == user_id
        if self_retry and now - (game.get('last_move_at') or now) < SELF_RETRY_SECONDS:
            return {'status': 'same_user'}
        game['used'].add(word)
        game['word'] = word
        game['required'] = _last(word, game['mode'])
        game['last_user'] = user_id
        game['last_move_at'] = now
        if not self_retry:
            game['scores'][user_id] = game['scores'].get(user_id, 0) + 1
        game['names'][user_id] = (user_name or 'Player')[:40]
        game['moves'] += 1
        game['idle_deadline'] = min(game['deadline'], now + IDLE_SECONDS)
        return {
            'status': 'valid', 'word': word, 'required': game['required'],
            'self_retry': self_retry,
            'moves': game['moves'], 'scores': dict(game['scores']),
            'names': dict(game['names']), 'deadline': game['deadline'],
            'idle_deadline': game['idle_deadline'], 'message_id': game['message_id'],
            'game_id': game['id'], 'mode': game['mode'],
        }


def finish(chat_id, game_id):
    with _lock:
        game = _games.get(chat_id)
        if not game or game['id'] != game_id:
            return None
        result = dict(game)
        result['scores'] = dict(game['scores'])
        result['names'] = dict(game['names'])
        _games.pop(chat_id, None)
        end_session(chat_id, 'word_chain')
        return result
