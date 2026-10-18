# ချော့စာ — Owner နှင့် သတ်မှတ်ထားသူအတွက်

`/ချော့ပေး` starts a group series. Only OWNER_TELEGRAM_ID may start. `/ရပြီ` is accepted only from that owner or the target saved in the run; ordinary members and other admins cannot stop it.

Owner setup: private `/control` -> Global/default settings (or a chosen group) -> Settings & Functions -> ချော့စာ. Set Target User ID and nickname. Default target is0, so no messages are sent before setup. Target must be an actual non-bot member of the group; membership lookup must succeed. A nickname is just the display label, not a username lookup. Default nickname ကလေး can be changed without editing243lines.

243 distinct authored one-line Burmese messages are provided, with no emoji in the authored bank. `{name}` uses the configured nickname. Bot Messages -> ချော့စာ စာတိုဘဏ် exposes every line individually for search/edit; the owner does not need to write or re-enter the bank. Settings and text overrides share the existing web/private editor and persistence.

Emoji bank is separate and empty by default. Open its Edit screen in private Owner control, then send normal or Premium emoji separated by spaces. Telegram `custom_emoji` entities are converted to stored IDs with UTF-16-correct offsets; `ce:ID:emoji` tokens are the storage representation. A plain web paste cannot recreate a Premium entity that was not supplied; existing saved ID tokens remain editable there. Randomly pick one emoji for each outgoing line. Telegram must permit this bot to send custom emoji (e.g. eligible bot owner's Premium subscription); a definite emoji-related400 error falls back once to the ordinary emoji. Other failures, especially ambiguous timeouts, are not retried.

Default6messages30secondsapart; owner-configurable1–12messages,15–300secondsapart. Hard maximum15minutes per run means a long interval may end before the requested count. Cooldown default10minutes, minimum5minutes, tracked globally per target. Only one active run per target across groups and one run per group.

Each outgoing message mentions only the configured target by Telegram ID. If the bot observes target text during the run, its next scheduled line replies to the latest such message (up to120secondsold); it does not send an extra immediate message. The reply pointer is then consumed. Group privacy/permissions determine what normal messages the bot can observe. Missing/deleted replied-to messages allow standalone sending.

The target's `/ရပြီ` stops all runs for that target and saves a global opt-out. The owner cannot override that opt-out. Only the target may press ပြန်လက်ခံမယ် to allow a new run; cooldown still applies. Owner stop ends only this group's run without opting the target out. An already in-flight Telegram request can complete while a stop is being handled; no new scheduled messages are started afterwards.

Small PostgreSQL tables: comfort_targets (consent/cooldown), comfort_runs (runidentity/status), comfort_used (rendered-text hashes). Shared advisory lock serializes start/stop/history changes. Claim a text hash before sending; ambiguous delivery is never replayed. Failed/uncertain sends can consume a line without delivery, favoring no duplicate mentions.

Random selection excludes all previously claimed text hashes for that target, including across groups/restarts. Duplicate owner-customized lines are deduplicated. On pool exhaustion, retain the latest30 and reset older history before randomly reusing earlier messages. Thus no promise of infinitely unique messages; after243distinctdefaults have been used the older pool cycles. If customizations leave <=30uniqueentries and they are exhausted, stop instead of repeating immediately.

Restart marks active runs interrupted; no catch-up messages, timers or old replies are resumed. No polling SQL loop when idle: a worker exists only for a bounded active run. No external AI, image generation or media uploads. Persistent refusal/history are retained. No automatic broadcast to other groups.

Automated tests cover authored uniqueness/length/noemoji, random nonrepeat/dedup, HTMLescape, UTF16PremiumIDs, editablecatalog, owner-onlystart, blockedtargetrefusal, stoppermissions, target-onlyconsent, latestreply, boundedworker, stop-before-send and no retry on ambiguous failure. Live Telegram delivery must be tested after a separately authorized deployment and configuration.
