from datetime import datetime, timedelta, timezone

from src.collect_sources import SourceItem, collect_weather, deduplicate_items, duplicate_key, is_recent, parse_date


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


def test_collect_weather_maps_open_meteo_response(monkeypatch) -> None:
    class FakeResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict:
            return {
                "current": {
                    "time": "2026-05-21T10:00",
                    "temperature_2m": 17.4,
                    "relative_humidity_2m": 62,
                    "precipitation": 0,
                    "weather_code": 2,
                    "wind_speed_10m": 13.2,
                },
                "daily": {
                    "time": ["2026-05-21"],
                    "weather_code": [61],
                    "temperature_2m_max": [19.1],
                    "temperature_2m_min": [9.5],
                    "precipitation_probability_max": [40],
                    "sunrise": ["2026-05-21T05:08"],
                    "sunset": ["2026-05-21T21:25"],
                },
            }

    def fake_get(url, params, headers, timeout):  # noqa: ANN001
        assert "api.open-meteo.com" in url
        assert params["latitude"] == 53.4609
        assert timeout == 10
        return FakeResponse()

    monkeypatch.setattr("src.collect_sources.requests.get", fake_get)

    weather = collect_weather(
        {
            "name": "Hamburg 21077",
            "provider": "Open-Meteo",
            "latitude": 53.4609,
            "longitude": 9.9794,
            "timezone": "Europe/Berlin",
        },
        timeout=10,
    )

    assert weather is not None
    assert weather["location"] == "Hamburg 21077"
    assert weather["current"]["description"] == "teilweise bewoelkt"
    assert weather["today"]["description"] == "leichter Regen"
    assert weather["today"]["precipitation_probability_max_percent"] == 40
