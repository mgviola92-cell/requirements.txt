"""News source activation boundaries, updated atomically with owner preferences."""

def initialize(cur):
    cur.execute('CREATE TABLE IF NOT EXISTS news_source_activation(source_id TEXT PRIMARY KEY,enabled BOOLEAN NOT NULL,since TIMESTAMPTZ NOT NULL DEFAULT NOW())')
    cur.execute('CREATE TABLE IF NOT EXISTS news_auto_state(chat_id BIGINT PRIMARY KEY,cursor_at TIMESTAMPTZ NOT NULL DEFAULT NOW())')


def sync_sources(cur,selected):
    from data.news_sources import CATALOG
    initialize(cur)
    # A disabled -> enabled transition establishes a new boundary. Saving the
    # same set must not move it, or newly published stories could disappear.
    for sid in CATALOG:
        enabled=sid in selected
        cur.execute('''INSERT INTO news_source_activation(source_id,enabled) VALUES(%s,%s)
          ON CONFLICT(source_id) DO UPDATE SET enabled=EXCLUDED.enabled,
          since=CASE WHEN EXCLUDED.enabled AND NOT news_source_activation.enabled THEN NOW() ELSE news_source_activation.since END
          WHERE news_source_activation.enabled IS DISTINCT FROM EXCLUDED.enabled''',(sid,enabled))
