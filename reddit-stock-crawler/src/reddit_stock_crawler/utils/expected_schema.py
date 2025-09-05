# expected_schema.py
# ============================================================================
#  SOLL-Definition für health_db_check.py
#  ============================================================================
#  Jede Liste (tables, index, trigger) besteht aus Dictionaries mit mindestens
#  dem Schlüssel "name".  Bei den Spalten (columns) werden außer dem Namen noch
#  Typ, NOT-NULL-Flag und Default-Wert festgehalten, damit der Health-Checker
#  diese Werte 1-zu-1 gegen die echte Datenbank vergleichen kann.
#  ============================================================================
#  Hinweis:
#      • notnull = 1  → Spalte ist NOT NULL oder Teil des PRIMARY KEY
#      • dflt_value   → exakt so, wie ihn `PRAGMA table_info()` liefert
#                       (None = kein Default)
# ============================================================================

EXPECTED = {
    # ------------------------------------------------------------------ TABLES
    "table": [
        {"name": "subreddits"},
        {"name": "redditors"},
        {"name": "posts"},
        {"name": "comments"},
        {"name": "tickers"},
        {"name": "mentions"},
        {"name": "daily_stats"},
        {"name": "trend_alerts"},
        {"name": "crawl_logs"},
    ],

    # ------------------------------------------------------------- COLUMN-MAP
    "columns": {
        # --------------------------- subreddits
        "subreddits": [
            {"name": "id",           "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "title",        "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "description",  "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "subscriber",   "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "created_utc",  "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "quarantaene",  "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "gecrawlt_am",  "type": "TEXT",    "notnull": 0, "dflt_value": "CURRENT_TIMESTAMP"},
        ],

        # --------------------------- redditors
        "redditors": [
            {"name": "id",            "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "link_karma",    "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "comment_karma", "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "created_utc",   "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "gecrawlt_am",   "type": "TEXT",    "notnull": 0, "dflt_value": "CURRENT_TIMESTAMP"},
        ],

        # --------------------------- posts
        "posts": [
            {"name": "id",                     "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "subreddit_id",           "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "author_id",              "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "title",                  "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "selftext",               "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "is_self",                "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "url",                    "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "permalink",              "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "score",                  "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "upvote_ratio",           "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "num_comments",           "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "created_utc",            "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "edited_utc",             "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "distinguished",          "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "is_original_content",    "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "is_video",               "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "over_18",                "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "spoiler",                "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "stickied",               "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "locked",                 "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "link_flair_text",        "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "link_flair_template_id", "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "author_flair_text",      "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "saved",                  "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "clicked",                "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "poll_data_json",         "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "removed_by_category",    "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "gecrawlt_am",            "type": "TEXT",    "notnull": 0, "dflt_value": "CURRENT_TIMESTAMP"},
            {"name": "verarbeitet",            "type": "INTEGER", "notnull": 0, "dflt_value": 0},
        ],

        # --------------------------- comments
        "comments": [
            {"name": "id",           "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "post_id",      "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "parent_id",    "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "author_id",    "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "body",         "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "score",        "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "created_utc",  "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "edited_utc",   "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "distinguished","type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "is_submitter", "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "stickied",     "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "locked",       "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "depth",        "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "gecrawlt_am",  "type": "TEXT",    "notnull": 0, "dflt_value": "CURRENT_TIMESTAMP"},
            {"name": "verarbeitet",  "type": "INTEGER", "notnull": 0, "dflt_value": 0},
        ],

        # --------------------------- tickers
        "tickers": [
            {"name": "symbol",            "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "unternehmensname",  "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "sektor",            "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "branche",           "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "market_cap",        "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "last_price",        "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "last_volume",       "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "avg_volume_30d",    "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "pe_ratio",          "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "beta",              "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "dividend_yield",    "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "zuletzt_aktualisiert","type":"TEXT",   "notnull": 0, "dflt_value": "CURRENT_TIMESTAMP"},
            {"name": "aktiv",             "type": "INTEGER", "notnull": 0, "dflt_value": 1},
        ],

        # --------------------------- mentions
        "mentions": [
            {"name": "id",             "type": "INTEGER", "notnull": 1, "dflt_value": None},
            {"name": "symbol",         "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "post_id",        "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "comment_id",     "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "source",         "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "context",        "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "position",       "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "sentiment_score","type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "sentiment_label","type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "confidence",     "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "created_at",     "type": "TEXT",    "notnull": 0, "dflt_value": "CURRENT_TIMESTAMP"},
        ],

        # --------------------------- daily_stats
        "daily_stats": [
            {"name": "id",               "type": "INTEGER", "notnull": 1, "dflt_value": None},
            {"name": "symbol",           "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "date",             "type": "DATE",    "notnull": 1, "dflt_value": None},
            {"name": "mention_count",    "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "post_mentions",    "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "comment_mentions", "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "avg_sentiment",    "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "sentiment_std",    "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "pos_cnt",          "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "neg_cnt",          "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "neu_cnt",          "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "total_score",      "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "avg_score",        "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "unique_authors",   "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "trend_score",      "type": "REAL",    "notnull": 0, "dflt_value": 0},
            {"name": "rank",             "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "price_at_mention", "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "volume_at_mention","type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "created_at",       "type": "TEXT",    "notnull": 0, "dflt_value": "CURRENT_TIMESTAMP"},
        ],

        # --------------------------- trend_alerts
        "trend_alerts": [
            {"name": "id",             "type": "INTEGER", "notnull": 1, "dflt_value": None},
            {"name": "symbol",         "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "alert_type",     "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "threshold",      "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "current_value",  "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "percent_change", "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "window_minutes", "type": "INTEGER", "notnull": 0, "dflt_value": None},
            {"name": "message",        "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "priority",       "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "active",         "type": "INTEGER", "notnull": 0, "dflt_value": 1},
            {"name": "created_at",     "type": "TEXT",    "notnull": 0, "dflt_value": "CURRENT_TIMESTAMP"},
            {"name": "closed_at",      "type": "TEXT",    "notnull": 0, "dflt_value": None},
        ],

        # --------------------------- crawl_logs
        "crawl_logs": [
            {"name": "id",                 "type": "INTEGER", "notnull": 1, "dflt_value": None},
            {"name": "run_id",             "type": "TEXT",    "notnull": 1, "dflt_value": None},
            {"name": "subreddit_id",       "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "started_at",         "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "finished_at",        "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "posts_processed",    "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "comments_processed", "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "tickers_found",      "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "error_count",        "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "status",             "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "error_message",      "type": "TEXT",    "notnull": 0, "dflt_value": None},
            {"name": "api_calls",          "type": "INTEGER", "notnull": 0, "dflt_value": 0},
            {"name": "elapsed_seconds",    "type": "REAL",    "notnull": 0, "dflt_value": None},
            {"name": "created_at",         "type": "TEXT",    "notnull": 0, "dflt_value": "CURRENT_TIMESTAMP"},
        ],
    },

    # ----------------------------------------------------------------- INDEXE
    "index": [
        {"name": "idx_posts_subreddit"},
        {"name": "idx_posts_created"},
        {"name": "idx_posts_score"},
        {"name": "idx_comments_post"},
        {"name": "idx_comments_created"},
        {"name": "idx_mentions_symbol"},
        {"name": "idx_mentions_created_at"},
        {"name": "idx_daily_stats_date"},
        {"name": "idx_daily_stats_symbol"},
        {"name": "idx_trend_alerts_active"},
        {"name": "idx_crawl_logs_run_id"},
    ],

    # ------------------------------------------------------------- TRIGGER
    "trigger": [
        {"name": "trg_mentions_insert_ticker"},
    ],

    # ----------------------------------------------------------- PK-Mapping
    "pk_map": {
        "subreddits":  "id",
        "redditors":   "id",
        "posts":       "id",
        "comments":    "id",
        "tickers":     "symbol",
        "mentions":    "id",
        "daily_stats": "id",
        "trend_alerts":"id",
        "crawl_logs":  "id",
    },
}