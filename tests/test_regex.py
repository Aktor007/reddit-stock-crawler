# tests/test_regex.py
from reddit_crawler_stock import extract_mentions, TICKER_RE

def test_regex_extracts_prefixed_and_plain():
    text = "Buy $AAPL or go all-in on TSLA!"
    wl   = {"AAPL", "TSLA"}
    assert extract_mentions(text, wl) == ["AAPL", "TSLA"]

def test_regex_ignores_words_longer_than_5():
    assert TICKER_RE.findall("BANANAS") == []          # 7 Zeichen