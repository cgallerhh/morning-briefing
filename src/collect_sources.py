from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

import feedparser
import requests
import yaml
from bs4 import BeautifulSoup
from dateutil import parser as date_parser

LOGGER = logging.getLogger("morning_briefing.collect")
USER_AGENT = "morning-briefing/1.0 (+https://github.com/cgallerhh/morning-briefing)"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"
WEATHER_CODES = {
    0: "klar",
    1: "ueberwiegend klar",
    2: "teilweise bewoelkt",
    3: "bedeckt",
    45: "neblig",
    48: "Reifnebel",
    51: "leichter Nieselregen",
    53: "Nieselregen",
    55: "starker Nieselregen",
    61: "leichter Regen",
    63: "Regen",
    65: "starker Regen",
    71: "leichter Schnee",
    73: "Schnee",
    75: "starker Schnee",
    80: "leichte Regenschauer",
    81: "Regenschauer",
    82: "starke Regenschauer",
    95: "Gewitter",
    96: "Gewitter mit leichtem Hagel",
    99: "Gewitter mit starkem Hagel",
}


@dataclass
class SourceItem:
    source_id: str
    source_name: str
    source_priority: str
    source_category: str
    title: str
    url: str
    published_at: str | None
    summary: str
    collected_at: str
    duplicate_key: str
    supporting_sources: list[str]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip()


def duplicate_key(title: str, url: str) -> str:
    cleaned = re.sub(r"[^a-z0-9 ]+", "", title.lower())
    words = [word for word in cleaned.split() if len(word) > 2][:10]
    basis = " ".join(words) or url
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()[:16]


def parse_date(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        text = str(value)
        try:
            parsed = parsedate_to_datetime(text)
        except (TypeError, ValueError, IndexError):
            try:
                parsed = date_parser.parse(text, fuzzy=True)
            except (TypeError, ValueError, OverflowError):
                return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def is_recent(published_at: str | None, hours: int, now: datetime) -> bool:
    if not published_at:
        return True
    parsed = parse_date(published_at)
    if not parsed:
        return True
    return parsed >= now - timedelta(hours=hours)


def load_sources(path: Path) -> list[dict[str, Any]]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return [*(data.get("core_sources") or []), *(data.get("supplemental_sources") or [])]


def load_config(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def fetch_url(url: str, timeout: int) -> requests.Response:
    response = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    return response


def weather_description(code: int | None) -> str | None:
    if code is None:
        return None
    return WEATHER_CODES.get(code, f"Wettercode {code}")


def collect_weather(weather_config: dict[str, Any] | None, timeout: int) -> dict[str, Any] | None:
    if not weather_config:
        return None

    params = {
        "latitude": weather_config["latitude"],
        "longitude": weather_config["longitude"],
        "timezone": weather_config.get("timezone", "Europe/Berlin"),
        "forecast_days": 1,
        "current": "temperature_2m,relative_humidity_2m,precipitation,weather_code,wind_speed_10m",
        "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,sunrise,sunset",
    }
    response = requests.get(OPEN_METEO_URL, params=params, headers={"User-Agent": USER_AGENT}, timeout=timeout)
    response.raise_for_status()
    data = response.json()
    current = data.get("current") or {}
    daily = data.get("daily") or {}
    daily_code = (daily.get("weather_code") or [None])[0]
    current_code = current.get("weather_code")

    return {
        "location": weather_config.get("name", "Hamburg 21077"),
        "provider": weather_config.get("provider", "Open-Meteo"),
        "retrieved_at": utc_now().isoformat(),
        "current": {
            "time": current.get("time"),
            "temperature_c": current.get("temperature_2m"),
            "relative_humidity_percent": current.get("relative_humidity_2m"),
            "precipitation_mm": current.get("precipitation"),
            "wind_speed_kmh": current.get("wind_speed_10m"),
            "weather_code": current_code,
            "description": weather_description(current_code),
        },
        "today": {
            "date": (daily.get("time") or [None])[0],
            "temperature_max_c": (daily.get("temperature_2m_max") or [None])[0],
            "temperature_min_c": (daily.get("temperature_2m_min") or [None])[0],
            "precipitation_probability_max_percent": (daily.get("precipitation_probability_max") or [None])[0],
            "sunrise": (daily.get("sunrise") or [None])[0],
            "sunset": (daily.get("sunset") or [None])[0],
            "weather_code": daily_code,
            "description": weather_description(daily_code),
        },
    }


def collect_rss(source: dict[str, Any], timeout: int) -> list[SourceItem]:
    response = fetch_url(source["url"], timeout)
    parsed = feedparser.parse(response.content)
    if parsed.bozo:
        LOGGER.warning("Feed parse warning for %s: %s", source["name"], parsed.bozo_exception)

    items: list[SourceItem] = []
    for entry in parsed.entries[:20]:
        title = normalize_text(entry.get("title", ""))
        url = entry.get("link") or source["url"]
        summary = normalize_text(BeautifulSoup(entry.get("summary", ""), "html.parser").get_text(" "))
        published = entry.get("published") or entry.get("updated")
        published_dt = parse_date(published)
        published_at = published_dt.isoformat() if published_dt else None
        if title:
            items.append(
                make_item(
                    source,
                    title=title,
                    url=url,
                    summary=summary,
                    published_at=published_at,
                )
            )
    return items


def collect_webpage(source: dict[str, Any], timeout: int) -> list[SourceItem]:
    response = fetch_url(source["url"], timeout)
    soup = BeautifulSoup(response.text, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg"]):
        tag.decompose()

    items: list[SourceItem] = []
    article_nodes = soup.find_all(["article", "li", "section"], limit=60)
    for node in article_nodes:
        heading = node.find(["h1", "h2", "h3"])
        link = node.find("a", href=True)
        title = normalize_text(heading.get_text(" ") if heading else link.get_text(" ") if link else "")
        if len(title) < 12:
            continue
        href = link["href"] if link else source["url"]
        url = requests.compat.urljoin(source["url"], href)
        summary = normalize_text(node.get_text(" "))
        summary = summary[:900]
        published_at = extract_node_date(node)
        items.append(make_item(source, title=title, url=url, summary=summary, published_at=published_at))
        if len(items) >= 15:
            break

    if not items:
        title = normalize_text(soup.title.get_text(" ") if soup.title else source["name"])
        summary = normalize_text(soup.get_text(" "))[:1200]
        items.append(make_item(source, title=title, url=source["url"], summary=summary, published_at=None))
    return items


def extract_node_date(node: Any) -> str | None:
    time_node = node.find("time")
    candidates = []
    if time_node:
        candidates.extend([time_node.get("datetime"), time_node.get_text(" ")])
    text = normalize_text(node.get_text(" "))
    match = re.search(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.? \d{1,2}, \d{4}\b",
        text,
        flags=re.IGNORECASE,
    )
    if match:
        candidates.append(match.group(0))
    for candidate in candidates:
        parsed = parse_date(candidate)
        if parsed:
            return parsed.isoformat()
    return None


def make_item(source: dict[str, Any], title: str, url: str, summary: str, published_at: str | None) -> SourceItem:
    return SourceItem(
        source_id=source["id"],
        source_name=source["name"],
        source_priority=source.get("priority", "supplemental"),
        source_category=source.get("category", "world"),
        title=title,
        url=url,
        published_at=published_at,
        summary=summary,
        collected_at=utc_now().isoformat(),
        duplicate_key=duplicate_key(title, url),
        supporting_sources=[source["name"]],
    )


def deduplicate_items(items: list[SourceItem]) -> list[SourceItem]:
    seen: dict[str, SourceItem] = {}
    unique: list[SourceItem] = []
    for item in items:
        existing = seen.get(item.duplicate_key)
        if existing:
            existing.supporting_sources = sorted({*existing.supporting_sources, *item.supporting_sources})
            if item.source_name not in existing.summary:
                existing.summary = f"{existing.summary}\n\nWeitere Quelle: {item.source_name} - {item.title}"
            continue
        seen[item.duplicate_key] = item
        unique.append(item)
    return unique


def collect_sources(config_path: Path, output_path: Path, hours: int, timeout: int) -> dict[str, Any]:
    now = utc_now()
    collected: list[SourceItem] = []
    errors: list[dict[str, str]] = []
    config = load_config(config_path)

    for source in [*(config.get("core_sources") or []), *(config.get("supplemental_sources") or [])]:
        try:
            LOGGER.info("Collecting %s", source["name"])
            items = collect_rss(source, timeout) if source.get("type") == "rss" else collect_webpage(source, timeout)
            recent_items = [item for item in items if is_recent(item.published_at, hours, now)]
            collected.extend(recent_items or items[:3])
            LOGGER.info("Collected %s items from %s", len(recent_items or items[:3]), source["name"])
        except Exception as exc:  # noqa: BLE001 - workflow should continue with explicit source error.
            LOGGER.exception("Could not collect %s", source.get("name", source.get("id", "unknown")))
            errors.append({"source": source.get("name", source.get("id", "unknown")), "error": str(exc)})

    weather = None
    weather_error = None
    try:
        weather = collect_weather(config.get("weather"), timeout)
        if weather:
            LOGGER.info("Collected weather for %s", weather["location"])
    except Exception as exc:  # noqa: BLE001 - weather should not block the briefing.
        LOGGER.exception("Could not collect weather")
        weather_error = str(exc)

    unique_items = deduplicate_items(collected)
    payload = {
        "generated_at": now.isoformat(),
        "recency_window_hours": hours,
        "weather": weather,
        "weather_error": weather_error,
        "items": [asdict(item) for item in unique_items],
        "source_errors": errors,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    LOGGER.info("Wrote %s unique items to %s", len(unique_items), output_path)
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect configured Morning Briefing sources.")
    parser.add_argument("--config", default="config/sources.yml")
    parser.add_argument("--output", default="outputs/collected-sources.json")
    parser.add_argument("--hours", type=int, default=24)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    collect_sources(Path(args.config), Path(args.output), args.hours, args.timeout)


if __name__ == "__main__":
    main()
