-- ============================================================================
--  Reddit Stock-Crawler – Physical schema for SQLite     (Version 1.2 | 2024-05)
-- ============================================================================

/* 0) Basis-PRAGMAs – gelten nur für die aktuelle Verbindung                 */
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
PRAGMA busy_timeout = 60000;

/* 1) Aufräumen (idempotent)                                                 */
DROP TABLE IF EXISTS crawl_logs;
DROP TABLE IF EXISTS trend_alerts;
DROP TABLE IF EXISTS daily_stats;
DROP TABLE IF EXISTS mentions;
DROP TABLE IF EXISTS tickers;
DROP TABLE IF EXISTS comments;
DROP TABLE IF EXISTS posts;
DROP TABLE IF EXISTS redditors;
DROP TABLE IF EXISTS subreddits;

/* 2) Kernobjekte: Subreddit ‑/ Redditor ‑/ Post ‑/ Comment                  */
CREATE TABLE subreddits (
    id           TEXT PRIMARY KEY,
    title        TEXT,
    description  TEXT,
    subscriber   INTEGER,
    created_utc  INTEGER,
    quarantaene  INTEGER CHECK (quarantaene IN (0,1)),
    gecrawlt_am  TEXT DEFAULT CURRENT_TIMESTAMP
) WITHOUT ROWID;

CREATE TABLE redditors (
    id            TEXT PRIMARY KEY,
    link_karma    INTEGER,
    comment_karma INTEGER,
    created_utc   INTEGER,
    gecrawlt_am   TEXT DEFAULT CURRENT_TIMESTAMP
) WITHOUT ROWID;

CREATE TABLE posts (
    id                     TEXT PRIMARY KEY,
    subreddit_id           TEXT NOT NULL,
    author_id              TEXT,
    title                  TEXT NOT NULL,
    selftext               TEXT,
    is_self                INTEGER CHECK (is_self IN (0,1)),
    url                    TEXT,
    permalink              TEXT,
    score                  INTEGER,
    upvote_ratio           REAL,
    num_comments           INTEGER,
    created_utc            INTEGER,
    edited_utc             INTEGER,
    distinguished          TEXT,
    is_original_content    INTEGER CHECK (is_original_content IN (0,1)),
    is_video               INTEGER CHECK (is_video IN (0,1)),
    over_18                INTEGER CHECK (over_18  IN (0,1)),
    spoiler                INTEGER CHECK (spoiler  IN (0,1)),
    stickied               INTEGER CHECK (stickied IN (0,1)),
    locked                 INTEGER CHECK (locked   IN (0,1)),
    link_flair_text        TEXT,
    link_flair_template_id TEXT,
    author_flair_text      TEXT,
    saved                  INTEGER CHECK (saved   IN (0,1)),
    clicked                INTEGER CHECK (clicked IN (0,1)),
    poll_data_json         TEXT,
    removed_by_category    TEXT,
    gecrawlt_am            TEXT DEFAULT CURRENT_TIMESTAMP,
    verarbeitet            INTEGER DEFAULT 0 CHECK (verarbeitet IN (0,1)),
    FOREIGN KEY (subreddit_id) REFERENCES subreddits(id) ON DELETE CASCADE,
    FOREIGN KEY (author_id)    REFERENCES redditors(id)
) WITHOUT ROWID;

CREATE INDEX idx_posts_subreddit ON posts(subreddit_id);
CREATE INDEX idx_posts_created   ON posts(created_utc);
CREATE INDEX idx_posts_score     ON posts(score);

CREATE TABLE comments (
    id           TEXT PRIMARY KEY,
    post_id      TEXT NOT NULL,
    parent_id    TEXT,                         -- verweist auf *Post*
    author_id    TEXT,
    body         TEXT,
    score        INTEGER,
    created_utc  INTEGER,
    edited_utc   INTEGER,
    distinguished TEXT,
    is_submitter INTEGER CHECK (is_submitter IN (0,1)),
    stickied     INTEGER CHECK (stickied    IN (0,1)),
    locked       INTEGER CHECK (locked      IN (0,1)),
    depth        INTEGER,
    gecrawlt_am  TEXT DEFAULT CURRENT_TIMESTAMP,
    verarbeitet  INTEGER DEFAULT 0 CHECK (verarbeitet IN (0,1)),
    FOREIGN KEY (post_id)   REFERENCES posts(id)     ON DELETE CASCADE,
    FOREIGN KEY (author_id) REFERENCES redditors(id)
) WITHOUT ROWID;

CREATE INDEX idx_comments_post    ON comments(post_id);
CREATE INDEX idx_comments_created ON comments(created_utc);

/* 3) Projektobjekt: Ticker                                                 */
CREATE TABLE tickers (
    symbol               TEXT PRIMARY KEY,
    unternehmensname     TEXT,
    sektor               TEXT,
    branche              TEXT,
    market_cap           REAL,
    last_price           REAL,
    last_volume          REAL,
    avg_volume_30d       REAL,
    pe_ratio             REAL,
    beta                 REAL,
    dividend_yield       REAL,
    zuletzt_aktualisiert TEXT DEFAULT CURRENT_TIMESTAMP,
    aktiv                INTEGER NOT NULL DEFAULT 1 CHECK (aktiv IN (0,1))
) WITHOUT ROWID;

/* 4) Mentions                                                              */
CREATE TABLE mentions (
    id              INTEGER PRIMARY KEY,
    symbol          TEXT    NOT NULL,
    post_id         TEXT,
    comment_id      TEXT,
    source          TEXT,
    context         TEXT,
    position        INTEGER,
    sentiment_score REAL,
    sentiment_label TEXT,
    confidence      REAL,
    created_at      TEXT DEFAULT CURRENT_TIMESTAMP,
    CHECK (post_id IS NOT NULL OR comment_id IS NOT NULL),
    FOREIGN KEY (symbol)     REFERENCES tickers(symbol)  ON DELETE CASCADE,
    FOREIGN KEY (post_id)    REFERENCES posts(id)        ON DELETE CASCADE,
    FOREIGN KEY (comment_id) REFERENCES comments(id)     ON DELETE CASCADE
);

CREATE INDEX idx_mentions_symbol      ON mentions(symbol);
CREATE INDEX idx_mentions_created_at  ON mentions(created_at);
CREATE INDEX idx_mentions_post_id     ON mentions(post_id);
CREATE INDEX idx_mentions_comment_id  ON mentions(comment_id);

/* fehlende Ticker automatisch anlegen                                      */
CREATE TRIGGER IF NOT EXISTS trg_mentions_insert_ticker
BEFORE INSERT ON mentions
FOR EACH ROW
WHEN (SELECT 1 FROM tickers WHERE symbol = NEW.symbol) IS NULL
BEGIN
    INSERT INTO tickers(symbol, aktiv) VALUES (NEW.symbol, 1);
END;

/* 5) Daily-Stats                                                          */
CREATE TABLE daily_stats (
    id                INTEGER PRIMARY KEY,
    symbol            TEXT NOT NULL,
    date              DATE NOT NULL,
    mention_count     INTEGER DEFAULT 0,
    post_mentions     INTEGER DEFAULT 0,
    comment_mentions  INTEGER DEFAULT 0,
    avg_sentiment     REAL,
    sentiment_std     REAL,
    pos_cnt           INTEGER DEFAULT 0,
    neg_cnt           INTEGER DEFAULT 0,
    neu_cnt           INTEGER DEFAULT 0,
    total_score       INTEGER DEFAULT 0,
    avg_score         REAL,
    unique_authors    INTEGER DEFAULT 0,
    trend_score       REAL DEFAULT 0,
    rank              INTEGER,
    price_at_mention  REAL,
    volume_at_mention REAL,
    created_at        TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX idx_daily_stats_symbol_date
              ON daily_stats(symbol, date);

CREATE INDEX idx_daily_stats_date   ON daily_stats(date);
CREATE INDEX idx_daily_stats_symbol ON daily_stats(symbol);

/* 6) Trend-Alerts                                                         */
CREATE TABLE trend_alerts (
    id             INTEGER PRIMARY KEY,
    symbol         TEXT NOT NULL,
    alert_type     TEXT,
    threshold      REAL,
    current_value  REAL,
    percent_change REAL,
    window_minutes INTEGER,
    message        TEXT,
    priority       TEXT,
    active         INTEGER DEFAULT 1 CHECK (active IN (0,1)),
    created_at     TEXT DEFAULT CURRENT_TIMESTAMP,
    closed_at      TEXT
);

CREATE INDEX idx_trend_alerts_active ON trend_alerts(active);

/* 7) Crawl-Logs                                                           */
CREATE TABLE crawl_logs (
    id                  INTEGER PRIMARY KEY,
    run_id              TEXT NOT NULL,
    subreddit_id        TEXT,
    started_at          TEXT,
    finished_at         TEXT,
    posts_processed     INTEGER DEFAULT 0,
    comments_processed  INTEGER DEFAULT 0,
    tickers_found       INTEGER DEFAULT 0,
    error_count         INTEGER DEFAULT 0,
    status              TEXT,
    error_message       TEXT,
    api_calls           INTEGER DEFAULT 0,
    elapsed_seconds     REAL,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (subreddit_id) REFERENCES subreddits(id)
);

CREATE INDEX idx_crawl_logs_run_id ON crawl_logs(run_id);

/* 8) PRAGMA erneut + Plan-Cache optimieren                                */
PRAGMA foreign_keys = ON;
PRAGMA busy_timeout = 60000;
PRAGMA optimize;

/* ----------------------------------------------------------------------- */
-- Done