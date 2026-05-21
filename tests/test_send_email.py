from src.send_email import inline_markdown, markdown_to_email_html


def test_inline_markdown_converts_links_and_bold_text() -> None:
    result = inline_markdown("Der [Economist](https://example.com) berichtet **heute**.")

    assert '<a href="https://example.com">Economist</a>' in result
    assert "<strong>heute</strong>" in result


def test_markdown_to_email_html_builds_styled_html_document() -> None:
    markdown = "# Morning Briefing\n\n## 1. Executive Summary\n\n- **Headline.** Text."

    result = markdown_to_email_html(markdown)

    assert "<!doctype html>" in result
    assert "<h1>Morning Briefing</h1>" in result
    assert "<h2>1. Executive Summary</h2>" in result
    assert "<li><strong>Headline.</strong> Text.</li>" in result
