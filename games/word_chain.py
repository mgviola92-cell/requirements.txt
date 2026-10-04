"""Group Word Chain. EN: last letter; MY: last space-separated word."""
import json
import random
import re
import threading
import time
import uuid
from pathlib import Path

from core.sessions import can_start_session, start_session, end_session

ROUND_SECONDS = 7 * 60
IDLE_SECONDS = 60
_lock = threading.RLock()
_games = {}
_WORDS = None
_START_EN = ("apple", "tiger", "river", "orange", "green", "music", "garden", "winter")
_START_MY = ("မိုး ရေ", "ရေ ခဲ", "ပန်း ပွင့်", "လေ ပြေ", "သစ် ပင်", "မီး အိမ်")


def _english_words():
    global _WORDS
    if _WORDS is None:
        path = Path(__file__).resolve().parent.parent / 'data' / 'word_chain_en.json'
        _WORDS = set(json.loads(path.read_text(encoding='utf8')))
    return _WORDS


def normalize(text, mode):
    text = re.sub(r'[\u200b-\u200d\ufeff]', '', str(text or '')).strip()
    if mode == 'en':
        return text.casefold() if re.fullmatch(r'[A-Za-z]{3,12}', text) else None
    text = ' '.join(text.split())
    if not re.fullmatch(r'[\u1000-\u109f\uaa60-\uaa7f ]+', text):
        return None
    parts = text.split(' ')
    # Explicit space-separated Burmese words: e.g. မိုး ရေ -> ရေ ခဲ.
    return text if 2 <= len(parts) <= 4 and all(parts) else None


def _first(value, mode):
    return value[0] if mode == 'en' else value.split(' ')[0]


def _last(value, mode):
    return value[-1] if mode == 'en' else value.split(' ')[-1]


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
        started, session = start_session(chat_id, 'word_chain', duration=ROUND_SECONDS + 5)
        if not started:
            return False, session
        starter = random.choice(_START_MY if mode == 'my' else _START_EN)
        now = time.monotonic()
        game = {
            'id': uuid.uuid4().hex, 'chat_id': chat_id, 'mode': mode,
            'word': starter, 'required': _last(starter, mode),
            'used': {starter}, 'last_user': None, 'scores': {}, 'names': {},
            'started': now, 'deadline': now + ROUND_SECONDS,
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
        # In EN, check vocabulary instead of treating arbitrary group chat as a word.
        if game['mode'] == 'en' and word not in _english_words():
            return {'status': 'ignore'}
        if _first(word, game['mode']) != game['required']:
            return {'status': 'ignore'}
        if word in game['used']:
            return {'status': 'used'}
        if game['last_user'] == user_id:
            return {'status': 'same_user'}
        game['used'].add(word)
        game['word'] = word
        game['required'] = _last(word, game['mode'])
        game['last_user'] = user_id
        game['scores'][user_id] = game['scores'].get(user_id, 0) + 1
        game['names'][user_id] = (user_name or 'Player')[:40]
        game['moves'] += 1
        game['idle_deadline'] = min(game['deadline'], now + IDLE_SECONDS)
        return {
            'status': 'valid', 'word': word, 'required': game['required'],
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
