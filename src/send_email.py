from __future__ import annotations

import argparse
import html
import logging
import os
import re
import smtplib
from email.message import EmailMessage
from pathlib import Path

LOGGER = logging.getLogger("morning_briefing.email")
DEFAULT_GMAIL_ADDRESS = "christian.galler@gmail.com"


def inline_markdown(value: str) -> str:
    escaped = html.escape(value)
    escaped = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2">\1</a>', escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    return escaped


def markdown_to_email_html(markdown: str) -> str:
    lines = markdown.splitlines()
    body_parts: list[str] = []
    in_list = False

    def close_list() -> None:
        nonlocal in_list
        if in_list:
            body_parts.append("</ul>")
            in_list = False

    for raw_line in lines:
        line = raw_line.strip()
        if not line:
            close_list()
            continue
        if line.startswith("# "):
            close_list()
            body_parts.append(f"<h1>{inline_markdown(line[2:])}</h1>")
        elif line.startswith("## "):
            close_list()
            body_parts.append(f"<h2>{inline_markdown(line[3:])}</h2>")
        elif line.startswith(("- ", "• ")):
            if not in_list:
                body_parts.append("<ul>")
                in_list = True
            body_parts.append(f"<li>{inline_markdown(line[2:])}</li>")
        else:
            close_list()
            body_parts.append(f"<p>{inline_markdown(line)}</p>")
    close_list()

    content = "\n".join(body_parts)
    return f"""<!doctype html>
<html lang="de">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
      body {{
        margin: 0;
        padding: 0;
        background: #f5f6f8;
        color: #202124;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
        line-height: 1.55;
      }}
      .wrapper {{
        max-width: 760px;
        margin: 0 auto;
        padding: 28px 16px;
      }}
      .briefing {{
        background: #ffffff;
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 28px;
      }}
      h1 {{
        margin: 0 0 20px;
        font-size: 28px;
        line-height: 1.2;
        color: #111827;
      }}
      h2 {{
        margin: 28px 0 12px;
        padding-top: 18px;
        border-top: 1px solid #e5e7eb;
        font-size: 18px;
        line-height: 1.3;
        color: #1f2937;
      }}
      p {{
        margin: 0 0 14px;
        font-size: 15px;
      }}
      ul {{
        margin: 0 0 18px;
        padding-left: 20px;
      }}
      li {{
        margin: 0 0 14px;
        font-size: 15px;
      }}
      strong {{
        color: #111827;
      }}
      a {{
        color: #0b57d0;
        text-decoration: none;
        font-weight: 600;
      }}
      .footer {{
        color: #6b7280;
        font-size: 12px;
        margin-top: 14px;
        text-align: center;
      }}
    </style>
  </head>
  <body>
    <div class="wrapper">
      <div class="briefing">
        {content}
      </div>
      <div class="footer">Automatisch erzeugtes Morning Briefing</div>
    </div>
  </body>
</html>"""


def send_email(markdown_path: Path) -> None:
    host = os.environ.get("SMTP_HOST") or "smtp.gmail.com"
    port = int(os.environ.get("SMTP_PORT") or "587")
    username = os.environ.get("SMTP_USERNAME") or os.environ.get("GMAIL_USERNAME") or DEFAULT_GMAIL_ADDRESS
    password = os.environ.get("SMTP_PASSWORD") or os.environ.get("GMAIL_APP_PASSWORD")
    sender = os.environ.get("SMTP_FROM", username or "")
    recipients_raw = os.environ.get("SMTP_TO") or os.environ.get("EMAIL_TO") or DEFAULT_GMAIL_ADDRESS
    recipients = [item.strip() for item in recipients_raw.split(",") if item.strip()]

    if not all([host, username, password, sender]) or not recipients:
        raise RuntimeError("GMAIL_APP_PASSWORD or SMTP_PASSWORD must be set for email.")

    body = markdown_path.read_text(encoding="utf-8")
    message = EmailMessage()
    message["Subject"] = os.environ.get("SMTP_SUBJECT", f"Morning Briefing - {markdown_path.stem[-10:]}")
    message["From"] = sender
    message["To"] = ", ".join(recipients)
    message.set_content(body)
    message.add_alternative(markdown_to_email_html(body), subtype="html")

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
