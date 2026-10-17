# ကျားကွက်

`/checkers` or `/ကျားကွက်` creates an open group challenge. Reply to a person's message to restrict acceptance to that person. The challenger plays red and moves first. No bot opponent or points rewards are included.

Select a piece, then a green destination. This initial variant uses 8x8 short kings: ordinary men move/capture forward diagonally, captures are compulsory, multiple jumps must continue with the same piece, and promotion ends the turn. Kings move one square or jump one opponent in either diagonal direction; they are not flying kings. The largest available capture path is not compulsory.

No pieces or no legal moves loses. Three repeated positions or 80 consecutive non-capture/non-promotion half-moves draw. Players may offer a draw; only the opponent accepts. Moving clears an outstanding offer. Stop requires confirmation: a participant resigns, a nonparticipant group admin cancels. Cancelled/waiting-expired boards are deleted where Telegram permits; finished results replace the existing board and remove buttons.

Waiting and each turn default to five minutes, editable in Owner settings (60–1800 seconds). Merely selecting pieces, asking to stop or offering a draw does not extend the turn. Multi-capture uses the original turn deadline. A timeout is processed on interaction or within the next 30-second timer check; no countdown message edits.

One JSONB row per group in `checkers_games` preserves board, players, revision, turn deadline and invitation. Per-process lock and PostgreSQL advisory/row locks serialize actions. Callback game ID, card ID and revision reject obsolete/duplicate actions. Overdue games end after restart rather than replaying moves. Other active interactive games block new challenges through the shared session manager.

The board uses 64 Telegram buttons plus controls and updates the same text message. No image generation, photo upload or extra package. There is no traffic while idle except a small database timeout check for active matches. Telegram/API, DB and move traffic still count; no exact bandwidth saving guarantee.

`/checkersrules` provides Burmese instructions; `/checkersstop` asks to stop. All response templates and both timing settings are in Owner customization. Owner test/release menus and `/cmd`/downloadable guide include the game. Validate the 8-button rows on a real phone; fonts and narrow screens vary.

Tests cover compulsory/multiple captures, promotion, kings, immobilization, timeout, draw/resignation, targeted invites, group/card/revision isolation, serialization/UI payload limits, and 30 simulated random games. These are automated checks, not a claim of live two-person phone testing.
