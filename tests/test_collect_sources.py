from datetime import datetime, timedelta, timezone

from src.collect_sources import SourceItem, deduplicate_items, duplicate_key, is_recent, parse_date


def test_parse_date_returns_utc_datetime() -> None:
    parsed = parse_date("Wed, 20 May 2026 05:00:00 +0200")

    assert parsed is not None
    assert parsed.tzinfo == timezone.utc
    assert parsed.hour == 3


def test_is_recent_keeps_unknown_dates() -> None:
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)

    assert is_recent(None, 24, now)


def test_is_recent_filters_old_dates() -> None:
    now = datetime(2026, 5, 20, tzinfo=timezone.utc)
    old = (now - timedelta(hours=25)).isoformat()

    assert not is_recent(old, 24, now)


def test_duplicate_key_ignores_punctuation_and_case() -> None:
    first = duplicate_key("OpenAI launches new model!", "https://example.com/a")
    second = duplicate_key("openai launches new model", "https://example.com/b")

    assert first == second


def test_deduplicate_items_keeps_first_item() -> None:
    first = SourceItem(
        source_id="a",
        source_name="A",
        source_priority="core",
        source_category="ai",
        title="OpenAI launches new model",
        url="https://example.com/a",
        published_at=None,
        summary="First",
        collected_at="2026-05-20T00:00:00+00:00",
        duplicate_key="same",
        supporting_sources=["A"],
    )
    second = SourceItem(
        source_id="b",
        source_name="B",
        source_priority="core",
        source_category="ai",
        title="OpenAI launches new model",
        url="https://example.com/b",
        published_at=None,
        summary="Second",
        collected_at="2026-05-20T00:00:00+00:00",
        duplicate_key="same",
        supporting_sources=["B"],
    )

    result = deduplicate_items([first, second])

    assert result == [first]
    assert result[0].supporting_sources == ["A", "B"]
