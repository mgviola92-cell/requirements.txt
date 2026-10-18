# Database compute and automatic quiet periods

The Telegram process stays available. Its PostgreSQL workers sleep when idle; a
fixed nightly shutdown would interrupt active games and scheduled messages and
is intentionally not used.

## Work scheduling

- Draw, Nan Yate and Imposter keep their original 3-second active tick. Draw and
  Nan Yate also keep retries/deletion outboxes responsive after a game ends.
- Idle workers no longer perform 3-, 10-, 30- or 60-second empty polling.
- Group Studio sleeps until the earliest persisted pending job, so future
  capsules and command chains remain durable.
- News cleanup sleeps until the earliest persisted inactivity deadline. Each
  inline tap still moves that message's deadline five minutes forward. Database
  row locks continue to serialize button taps and deletion.
- News refresh/auto delivery sleeps until known fetch/delivery/retry deadlines;
  the existing startup delivery rate gate is retained.
- Daily uses the same per-group random Myanmar morning minute and remembers
  cards already posted that day. The cache resets on day rollover; persisted
  card IDs still prevent duplicate posts on restart.
- Owner schedules and broadcast recovery wake for committed work. A blocked
  overdue schedule backs off for 60 seconds rather than spinning.

`core/db_work.py` supplies local table-specific wake signals. The metered cursor
records affected DML tables only for successful statements affecting rows.
`get_db_connection()` detaches those records before returning a pooled connection
and signals workers only after the transaction context commits successfully.
Rollback/commit failure never announces an uncommitted job. Connection reuse
cannot overwrite the previous borrower's pending notifications.

There is still one aligned recovery read period every 15 minutes. This catches
work written by another process or external SQL and recovers after missed local
notifications. A new Telegram command/web request handled by this process does
not wait for that period: its committed writes wake the relevant worker.

Use one Telegram polling process. Multi-process writers are discovered by the
recovery scan, not by distributed push notifications.

## Compute limits

The observed Neon account is Free, with 100 CU-hours per monthly billing period,
minimum 0.25 CU, maximum configured 2 CU, and 5-minute idle suspension.
At 0.25 CU: 24 hours x 30 days = 180 CU-hours; 31 days = 186 CU-hours.
100 / 0.25 = 400 active wall hours (16.67 continuous days). For 31 days the
allowance is about 12.9 active hours/day, including idle tails.

Quiet recovery reads aligned every 15 minutes can still keep the database awake
for roughly five minutes per cycle. At minimum compute this is an illustrative
~62 CU-hours over 31 days before user traffic and extra deadlines. It is not a
measurement or savings guarantee: query duration, network delay, autoscaling,
user traffic, news deadlines, and other clients sharing this project change it.
A heavily used always-on database cannot fit 100 CU-hours merely by reducing
query counts. Validate actual Neon CU-hour trends after access is restored.

Idle pool minimum is zero and unused connections can retire after 60 seconds;
this does not replace eliminating idle queries.

## Incident and data safety

On 2026-10-18 Neon rejected connections with a project/account quota error. The
console explicitly said monthly compute allowance was exhausted. Railway build
of e763e46 succeeded, but deployment 116e40af-8934-45db-a5d6-cf5d9cdad7ff failed
its startup/health check while database access was blocked. Code optimization
does not restore an exhausted quota. No data has been deleted or reset.

Do not switch DATABASE_URL to an empty project if continuity matters. The old
project's data remains there until it is deleted, but a new project does not
inherit points, settings or history. Export/import must be verified before a
cutover. A quota-blocked source may need access restored before it can be dumped.

No games were removed as part of this change. Inactive games are primarily a
worker-scheduling problem; active long-running social/drawing games naturally
keep PostgreSQL awake. No production deploy or database migration is part of
this source-only optimization while Neon is blocked.
