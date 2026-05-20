from __future__ import annotations

import argparse
import logging
import os
import smtplib
from email.message import EmailMessage
from pathlib import Path

LOGGER = logging.getLogger("morning_briefing.email")


def send_email(markdown_path: Path) -> None:
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT") or "587")
    username = os.environ.get("SMTP_USERNAME")
    password = os.environ.get("SMTP_PASSWORD")
    sender = os.environ.get("SMTP_FROM", username or "")
    recipients = [item.strip() for item in os.environ.get("SMTP_TO", "").split(",") if item.strip()]

    if not all([host, username, password, sender]) or not recipients:
        raise RuntimeError("SMTP_HOST, SMTP_USERNAME, SMTP_PASSWORD, SMTP_FROM and SMTP_TO must be set for email.")

    body = markdown_path.read_text(encoding="utf-8")
    message = EmailMessage()
    message["Subject"] = os.environ.get("SMTP_SUBJECT", f"Morning Briefing - {markdown_path.stem[-10:]}")
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)

    LOGGER.info("Sending briefing email to %s", ", ".join(recipients))
    with smtplib.SMTP(host, port, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(message)
    LOGGER.info("Briefing email sent")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a generated Morning Briefing via SMTP.")
    parser.add_argument("markdown_path")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(level=args.log_level, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
    send_email(Path(args.markdown_path))


if __name__ == "__main__":
    main()
