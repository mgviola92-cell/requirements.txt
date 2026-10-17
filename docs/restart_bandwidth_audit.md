# Restart safety and outbound bandwidth audit — 2026-10-17

Scope: main Game Bot repository, based on b57e03d. No Render deployment and no
changes to the independent PythonAnywhere copy or Music Bot.

## Restart behavior

- `FreshUpdatesBot` filters messages/edits dated before this process started or
  more than 120 seconds old, before handlers, spam checks, usage tracking,
  activity spawns, commands or reward handling. Recent edits use edit_date.
- Polling uses `skip_pending=True`, intentionally discarding updates queued while
  the bot was offline (including old commands/clicks). This does not delete chat
  messages, points or database records. Existing menu clicks made after restart
  remain usable: menu message dates are not used to age callback queries.
- Daily and automatic news share a five-attempt-per-minute process budget. Each
  group/feature waits 30–330 seconds after startup, then retries through its normal
  scheduler. Manual commands bypass this gate. The limit bounds bursts, not total
  monthly traffic; replicas would each have their own budget.
- Daily checks today's card only; it does not iterate through missed calendar
  days. News sends one current digest and advances next_due from NOW(), rather
  than sending one digest for every missed interval.
- This or That cancels when a round is overdue by more than max(120 seconds,
  configured round length), removing the old keyboard without creating later
  rounds or granting participation rewards for that abandoned match.
- Draw and Nan Yate cancel after a deadline has passed and the stored heartbeat
  is more than one hour old. Unsent gameplay events for that match are superseded;
  cleanup/cancellation jobs remain. Brief outages retain the existing 30-second
  recovery grace. Existing reward transactions are not reversed.
- Imposter cancels if the current phase deadline is more than one hour overdue;
  it does not advance through old clue turns or award an unattended final vote.
- WYR already closes expired native polls and marks their rounds finished;
  it does not restart those games.
- Speed Tap automatic launch now passes the required update argument through
  the Owner editor wrapper, fixing the missing `update` TypeError.

Explicit owner broadcasts and schedules retain their existing durable semantics.
They are not silently discarded as if they were automatic chat replies. Pending
scheduled announcements can still be delivered after downtime and should be
reviewed in Owner tools before a long-suspended service is enabled. Uncertain
broadcast targets are not blindly resent. Draw/Nan terminal results and cleanup
may still complete once; cancellation does not erase valid prior rewards.

## Remaining outbound consumers

This is a source-code audit, not per-function billing measurement. Historical
workspace usage supplied by the owner was 6.02 GB service-initiated versus 4 MB
HTTP responses. That identifies a category, not a specific culprit.

| Path | What still leaves Render | Existing mitigation / practical implication |
| --- | --- | --- |
| Neon PostgreSQL | SQL queries, parameters, JSON state writes, TLS/protocol overhead | Connection pool, batched metadata, heartbeat-only idle ticks, Draw image separated from repeatedly saved state. Busy games and large writes still consume traffic. Query results received from Neon are inbound. |
| Draw canvas/image | Player drawing uploads to Telegram, image responses to canvas users, occasional changed image DB writes | Actual drawing is intentionally retained; exact-byte Telegram file_id cache avoids repeat uploads. New drawings still cost traffic. |
| Group memory book | Generated HTML containing up to 20 compressed thumbnails, uploaded on each export | Thumbnails limited to 720px JPEG quality 75; original-photo downloads are inbound, generated uploads are outbound. Repeated exports remain a potential large consumer. |
| Owner broadcast | Text/API requests or one Telegram copyMessage request per target | Telegram-side copy avoids downloading/re-uploading forwarded media. Group count and frequency still multiply requests. |
| `/guide` | About 228 KiB HTML per Telegram upload or browser download | User initiated; not a background loop. Repeated downloads add up. |
| Game/card updates | Text messages, keyboard edits, timer/result/role DM requests | Raster cards removed except real Draw content; update throttles retained. Large active groups and Nan role panels still generate requests. |
| RSS and Trivia sources | Request headers/URLs and connection overhead; cached item writes to Neon | RSS conditional requests and one shared source refresh per 30 minutes; fetched response bodies are inbound, not automatically equal to Render-billed outbound bytes. |
| Owner web panel | HTML/JSON responses when opened or refreshed, DB queries/writes for settings | Not continuously uploading a full dashboard by itself. Frequent browser refreshes/large reports still count. |
| Uptime check | Small home-page HTTP response and connection overhead | Far smaller payload than images/large exports; not proven to be the historical source. |

Render bills outbound traffic to public destinations, including external DB/API
requests and public HTTP responses; inbound traffic is excluded. Reference:
https://render.com/docs/outbound-bandwidth

Telegram retains unreceived updates for at most 24 hours, rather than every day
of a multi-day outage. Database-backed jobs have independent persistence:
https://core.telegram.org/bots/api#getting-updates

## Measurement and release

`/owner/bandwidth` already reports estimated payload by database caller/table,
Telegram operation, RSS and Flask. It includes incoming as well as outgoing
payload counters; use direction when comparing with Render. It excludes TLS,
protocol framing and other host traffic and resets on restart. It is not Render's
billing meter and cannot guarantee staying under 5 GB/month. Compare a measured
24-hour workload and Render metrics before estimating monthly cost.

Tests use mocked DB/Telegram delivery and simulated old/current updates, old-menu
clicks, startup budget, long/short outages and the actual Speed Tap launcher.
No live Render/Neon workload was started for this audit.
