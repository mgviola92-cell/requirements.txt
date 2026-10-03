# =========================================================
# 😀 EMOJI GUESS GAME
# =========================================================

import json
import random
import threading
import time
from pathlib import Path


# =========================================================
# ⚙️ SETTINGS
# =========================================================

EMOJI_GUESS_TIME = 60
EMOJI_HINT_AFTER = 30

PROJECT_ROOT = (
    Path(__file__).resolve().parent.parent
)

QUESTION_FILE = (
    PROJECT_ROOT
    / "data"
    / "emoji_questions.json"
)


# =========================================================
# 🔒 ACTIVE GAME STORAGE
#
# One Emoji Guess per group.
# =========================================================

_active_games = {}
_games_lock = threading.RLock()


# =========================================================
# 📚 QUESTION CACHE
# =========================================================

_questions_cache = None
_questions_lock = threading.RLock()


# =========================================================
# 🧹 NORMALIZE ANSWER
# =========================================================

def normalize_answer(text):
    if text is None:
        return ""

    return (
        str(text)
        .strip()
        .lower()
        .replace(" ", "")
        .replace("-", "")
        .replace("_", "")
    )


# =========================================================
# 📥 LOAD QUESTIONS
# =========================================================

def load_emoji_questions():
    global _questions_cache

    with _questions_lock:

        if _questions_cache is not None:
            return _questions_cache

        if not QUESTION_FILE.exists():
            print(
                "⚠️ emoji_questions.json "
                "မရှိသေးပါ။"
            )

            _questions_cache = []
            return _questions_cache

        try:
            with open(
                QUESTION_FILE,
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            if not isinstance(data, list):
                raise ValueError(
                    "Question JSON must be a list."
                )

            valid = []

            for item in data:

                if not isinstance(item, dict):
                    continue

                question_id = item.get("id")
                emojis = item.get("emojis")
                answers = item.get("answers")

                if not question_id:
                    continue

                if not emojis:
                    continue

                if not isinstance(
                    answers,
                    list
                ):
                    continue

                normalized_answers = [
                    normalize_answer(answer)
                    for answer in answers
                    if normalize_answer(answer)
                ]

                if not normalized_answers:
                    continue

                clean_item = {
                    "id": str(question_id),
                    "emojis": str(emojis),
                    "answers":
                        normalized_answers,
                    "display_answer":
                        str(
                            item.get(
                                "display_answer",
                                answers[0]
                            )
                        ),
                    "category":
                        str(
                            item.get(
                                "category",
                                "general"
                            )
                        ),
                    "hint":
                        str(
                            item.get(
                                "hint",
                                ""
                            )
                        ),
                }

                valid.append(
                    clean_item
                )

            _questions_cache = valid

            print(
                f"✅ Emoji Guess Questions Loaded: "
                f"{len(valid)}"
            )

            return _questions_cache

        except Exception as e:

            print(
                f"❌ Emoji Question Load Error: {e}"
            )

            _questions_cache = []

            return _questions_cache


# =========================================================
# 🎲 RANDOM QUESTION
#
# Used-ID Neon tracking ကို နောက် DB step
# မှာ ဒီ function နဲ့ချိတ်မည်။
# =========================================================

def get_random_question(
    exclude_ids=None
):
    questions = load_emoji_questions()

    if not questions:
        return None

    exclude_ids = set(
        str(item)
        for item in (
            exclude_ids or []
        )
    )

    available = [
        question
        for question in questions
        if question["id"]
        not in exclude_ids
    ]

    if not available:
        available = questions

    return random.choice(
        available
    )


# =========================================================
# ▶️ START GAME
# =========================================================

def start_emoji_game(
    chat_id,
    question,
    duration=EMOJI_GUESS_TIME
):
    if not question:
        return False, None

    now = time.time()

    game = {
        "chat_id": chat_id,

        "question_id":
            question["id"],

        "emojis":
            question["emojis"],

        "answers":
            list(
                question["answers"]
            ),

        "display_answer":
            question["display_answer"],

        "category":
            question["category"],

        "hint":
            question["hint"],

        "started_at":
            now,

        "expires_at":
            now + float(duration),

        "winner_id":
            None,

        "finished":
            False,
    }

    with _games_lock:

        if chat_id in _active_games:
            return False, (
                _active_games[
                    chat_id
                ]
            )

        _active_games[
            chat_id
        ] = game

    return True, game


# =========================================================
# 🔎 GET ACTIVE GAME
# =========================================================

def get_emoji_game(chat_id):

    with _games_lock:

        game = _active_games.get(
            chat_id
        )

        if not game:
            return None

        if game["finished"]:
            return None

        if (
            time.time()
            >= game["expires_at"]
        ):
            _active_games.pop(
                chat_id,
                None
            )
            return None

        return game


# =========================================================
# ✅ CHECK ANSWER
# =========================================================

def check_emoji_answer(
    chat_id,
    user_id,
    text
):
    answer = normalize_answer(
        text
    )

    if not answer:
        return {
            "status": "ignored"
        }

    with _games_lock:

        game = _active_games.get(
            chat_id
        )

        if not game:
            return {
                "status": "no_game"
            }

        if game["finished"]:
            return {
                "status": "finished"
            }

        if (
            time.time()
            >= game["expires_at"]
        ):
            _active_games.pop(
                chat_id,
                None
            )

            return {
                "status": "expired",
                "answer":
                    game[
                        "display_answer"
                    ],
                "question_id":
                    game[
                        "question_id"
                    ],
            }

        if answer not in game[
            "answers"
        ]:
            return {
                "status": "wrong"
            }

        # First correct wins
        game["winner_id"] = user_id
        game["finished"] = True

        _active_games.pop(
            chat_id,
            None
        )

        return {
            "status": "correct",
            "winner_id": user_id,
            "answer":
                game[
                    "display_answer"
                ],
            "question_id":
                game[
                    "question_id"
                ],
        }


# =========================================================
# 💡 GET HINT
# =========================================================

def get_emoji_hint(chat_id):

    game = get_emoji_game(
        chat_id
    )

    if not game:
        return None

    return (
        game["hint"]
        or None
    )


# =========================================================
# ⏳ REMAINING TIME
# =========================================================

def get_emoji_time_left(
    chat_id
):
    game = get_emoji_game(
        chat_id
    )

    if not game:
        return 0

    return max(
        0,
        game["expires_at"]
        - time.time()
    )


# =========================================================
# ⏹️ END GAME
# =========================================================

def end_emoji_game(chat_id):

    with _games_lock:
        return _active_games.pop(
            chat_id,
            None
        )
