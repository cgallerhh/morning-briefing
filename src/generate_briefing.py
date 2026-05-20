from __future__ import annotations

import argparse
import json
import logging
import os
from datetime import date
from pathlib import Path

from openai import OpenAI

LOGGER = logging.getLogger("morning_briefing.generate")


def build_user_payload(collected: dict, briefing_date: str) -> str:
    return (
        f"Datum: {briefing_date}\n\n"
        "Quellendaten als JSON. Erstelle daraus exakt das geforderte deutsche Markdown-Briefing.\n\n"
        f"{json.dumps(collected, ensure_ascii=False, indent=2)}"
    )


def generate_briefing(
    collected_path: Path,
    prompt_path: Path,
    output_dir: Path,
    model: str,
    briefing_date: str | None = None,
) -> Path:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set.")

    briefing_date = briefing_date or date.today().isoformat()
    collected = json.loads(collected_path.read_text(encoding="utf-8"))
    system_prompt = prompt_path.read_text(encoding="utf-8").replace("{Datum}", briefing_date)

    LOGGER.info("Generating briefing for %s with %s", briefing_date, model)
    client = OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model=model,
        temperature=0.2,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": build_user_payload(collected, briefing_date)},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise RuntimeError("OpenAI returned an empty briefing.")

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"morning-briefing-{briefing_date}.md"
    output_path.write_text(content.strip() + "\n", encoding="utf-8")
    LOGGER.info("Wrote briefing to %s", output_path)
    return output_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the German Morning Briefing with OpenAI.")
    parser.add_argument("--input", default="outputs/collected-sources.json")
    parser.add_argument("--prompt", default="prompts/morning_briefing_prompt.md")
    parser.add_argument("--output-dir", default="outputs")
    parser.add_argument("--date")
    parser.add_argument("--model", default=os.environ.get("OPENAI_MODEL", "gpt-4o-mini"))
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    generate_briefing(Path(args.input), Path(args.prompt), Path(args.output_dir), args.model, args.date)


if __name__ == "__main__":
    main()
