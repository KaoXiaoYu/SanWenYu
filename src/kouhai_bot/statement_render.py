"""Render problem cards into QQ-friendly PNG images.

The preferred path renders Markdown/HTML through Firefox so LaTeX, emoji and
embedded statement images look like they would in a browser. A small Pillow
fallback remains for deployments that have not installed Playwright yet.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import html
import os
import re
import textwrap
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import get_config


_LATEX_INLINE_RE = re.compile(r"(\$\$.*?\$\$|\$.*?\$|\\\(.*?\\\)|\\\[.*?\\\])", re.S)


def image_message_from_path(path: str) -> list[dict]:
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return [{"type": "image", "data": {"file": f"base64://{b64}"}}]


async def render_text_to_png(
    text: str,
    *,
    group_id: int,
    slug: str,
    max_width: int = 980,
) -> str:
    return await asyncio.to_thread(
        _render_markdown_to_png_sync,
        text,
        group_id=group_id,
        slug=slug,
        max_width=max_width,
    )


async def render_statement_html_to_png(
    statement_html: str,
    *,
    lead_text: str = "",
    group_id: int,
    slug: str,
    max_width: int = 980,
) -> str:
    return await asyncio.to_thread(
        _render_statement_html_to_png_sync,
        statement_html,
        lead_text=lead_text,
        group_id=group_id,
        slug=slug,
        max_width=max_width,
    )


def _render_markdown_to_png_sync(
    text: str,
    *,
    group_id: int,
    slug: str,
    max_width: int,
) -> str:
    body = _markdown_to_html(text)
    html_doc = _html_document(body, max_width=max_width)
    try:
        return _render_html_document_sync(html_doc, group_id=group_id, slug=slug)
    except Exception:
        return _render_text_to_png_fallback(text, group_id=group_id, slug=slug, max_width=max_width)


def _render_statement_html_to_png_sync(
    statement_html: str,
    *,
    lead_text: str,
    group_id: int,
    slug: str,
    max_width: int,
) -> str:
    pieces: list[str] = []
    if lead_text.strip():
        pieces.append(f'<div class="lead">{_markdown_to_html(lead_text)}</div>')
    pieces.append(f'<div class="statement">{statement_html}</div>')
    html_doc = _html_document("\n".join(pieces), max_width=max_width)
    try:
        return _render_html_document_sync(html_doc, group_id=group_id, slug=slug)
    except Exception:
        fallback_text = f"{lead_text}\n\n{_html_to_plain_text(statement_html)}".strip()
        return _render_text_to_png_fallback(fallback_text, group_id=group_id, slug=slug, max_width=max_width)


def _render_html_document_sync(html_doc: str, *, group_id: int, slug: str) -> str:
    from playwright.sync_api import sync_playwright

    path = _output_path(html_doc, group_id=group_id, slug=slug)
    with sync_playwright() as p:
        browser_name = os.environ.get("KOUHAI_RENDER_BROWSER", "firefox").strip().lower()
        browser_types = {
            "firefox": p.firefox,
            "chromium": p.chromium,
            "webkit": p.webkit,
        }
        order = [browser_name, "firefox", "chromium", "webkit"]
        browser = None
        last_error: Exception | None = None
        for name in dict.fromkeys(order):
            browser_type = browser_types.get(name)
            if browser_type is None:
                continue
            try:
                browser = browser_type.launch()
                break
            except Exception as exc:
                last_error = exc
        if browser is None:
            raise last_error or RuntimeError("No Playwright browser is available")
        page = browser.new_page(
            viewport={"width": 1040, "height": 2400},
            device_scale_factor=2,
        )
        page.set_content(html_doc, wait_until="networkidle")
        try:
            page.wait_for_function(
                "() => window.MathJax && MathJax.startup && MathJax.startup.promise",
                timeout=5000,
            )
            page.evaluate("() => MathJax.startup.promise")
        except Exception:
            pass
        page.locator(".card").screenshot(path=str(path), animations="disabled")
        browser.close()
    return str(path)


def _output_path(content: str, *, group_id: int, slug: str) -> Path:
    cfg = get_config()
    root = Path(cfg.data_dir) / "groups" / str(group_id) / "rendered"
    root.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha1(content.encode("utf-8")).hexdigest()[:12]
    return root / f"{slug}-{digest}-{int(time.time())}.png"


def _html_document(body: str, *, max_width: int) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <script>
    window.MathJax = {{
      tex: {{
        inlineMath: [['$', '$'], ['\\\\(', '\\\\)']],
        displayMath: [['$$', '$$'], ['\\\\[', '\\\\]']],
        processEscapes: true
      }},
      svg: {{ fontCache: 'none' }}
    }};
  </script>
  <script src="https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg.js"></script>
  <style>
    html, body {{
      margin: 0;
      background: #f3f4f1;
      color: #1f2933;
      font-family: "Microsoft YaHei", "Segoe UI Emoji", "Apple Color Emoji",
        "Noto Color Emoji", "Noto Sans CJK SC", sans-serif;
      font-size: 25px;
      line-height: 1.55;
    }}
    .card {{
      box-sizing: border-box;
      width: {max_width}px;
      padding: 34px 38px;
      background: #fffdfa;
      border: 2px solid #d8d6cc;
      border-radius: 18px;
    }}
    .lead {{
      margin-bottom: 28px;
      padding-bottom: 22px;
      border-bottom: 1px solid #e5e1d6;
    }}
    p {{ margin: 0 0 16px; }}
    .section-title {{
      margin: 28px 0 10px;
      font-size: 29px;
      font-weight: 700;
    }}
    pre {{
      white-space: pre-wrap;
      word-break: break-word;
      padding: 18px 20px;
      background: #f7f7f3;
      border: 1px solid #dedbd1;
      border-radius: 8px;
      font-family: Consolas, "Cascadia Mono", monospace;
      font-size: 23px;
      line-height: 1.4;
    }}
    img {{
      max-width: 100%;
      height: auto;
      vertical-align: middle;
    }}
    .tex-formula-text {{
      white-space: nowrap;
    }}
    mjx-container {{
      overflow-x: auto;
      overflow-y: hidden;
      max-width: 100%;
    }}
  </style>
</head>
<body>
  <div class="card">{body}</div>
</body>
</html>"""


def _markdown_to_html(text: str) -> str:
    blocks: list[str] = []
    paragraph: list[str] = []
    in_code = False
    code_lines: list[str] = []
    for raw in text.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if raw.strip().startswith("```"):
            if in_code:
                blocks.append(f"<pre>{html.escape(chr(10).join(code_lines))}</pre>")
                code_lines = []
                in_code = False
            else:
                _flush_paragraph(blocks, paragraph)
                in_code = True
            continue
        if in_code:
            code_lines.append(raw)
            continue
        if not raw.strip():
            _flush_paragraph(blocks, paragraph)
            continue
        paragraph.append(raw)
    if in_code:
        blocks.append(f"<pre>{html.escape(chr(10).join(code_lines))}</pre>")
    _flush_paragraph(blocks, paragraph)
    return "\n".join(blocks)


def _flush_paragraph(blocks: list[str], paragraph: list[str]) -> None:
    if not paragraph:
        return
    text = "\n".join(paragraph).strip()
    escaped = _escape_preserving_latex(text).replace("\n", "<br>")
    blocks.append(f"<p>{escaped}</p>")
    paragraph.clear()


def _escape_preserving_latex(text: str) -> str:
    parts: list[str] = []
    last = 0
    for match in _LATEX_INLINE_RE.finditer(text):
        parts.append(html.escape(text[last:match.start()]))
        parts.append(match.group(0))
        last = match.end()
    parts.append(html.escape(text[last:]))
    return "".join(parts)


def _html_to_plain_text(value: str) -> str:
    text = re.sub(r"<br\s*/?>", "\n", value, flags=re.I)
    text = re.sub(r"</(?:p|div|pre|li)>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    return html.unescape(re.sub(r"\n{3,}", "\n\n", text)).strip()


def _font(size: int, *, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\seguiemj.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return ImageFont.truetype(candidate, size=size)
    return ImageFont.load_default()


def _display_text(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        token = match.group(0).strip()
        token = token.removeprefix("$$").removesuffix("$$")
        token = token.removeprefix("$").removesuffix("$")
        token = token.removeprefix(r"\(").removesuffix(r"\)")
        token = token.removeprefix(r"\[").removesuffix(r"\]")
        return token.strip()

    return _LATEX_INLINE_RE.sub(repl, text)


def _wrap_line(line: str, width: int) -> list[str]:
    if not line:
        return [""]
    return textwrap.wrap(
        line,
        width=width,
        replace_whitespace=False,
        drop_whitespace=False,
        break_long_words=True,
        break_on_hyphens=False,
    ) or [""]


def _render_text_to_png_fallback(
    text: str,
    *,
    group_id: int,
    slug: str,
    max_width: int,
) -> str:
    path = _output_path(text, group_id=group_id, slug=slug)
    body_font = _font(26)
    code_font = _font(24)
    title_font = _font(30, bold=True)
    padding_x = 34
    padding_y = 30
    line_gap = 10
    para_gap = 14
    wrap_width = 52

    normalized = _display_text(text).replace("\r\n", "\n").replace("\r", "\n").strip()
    paragraphs = normalized.split("\n")
    draw_probe = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    rendered: list[tuple[str, ImageFont.ImageFont, int]] = []
    for raw in paragraphs:
        font = title_font if raw.strip().endswith(":") and len(raw.strip()) <= 24 else body_font
        if raw.startswith(("Input:", "Output:")) or re.match(r"^\s*\d+(\s+\d+)*\s*$", raw):
            font = code_font
        lines = _wrap_line(raw, wrap_width)
        for line in lines:
            rendered.append((line, font, line_gap))
        rendered[-1] = (rendered[-1][0], rendered[-1][1], para_gap)

    height = padding_y * 2
    for line, font, gap in rendered:
        bbox = draw_probe.textbbox((0, 0), line or " ", font=font)
        height += (bbox[3] - bbox[1]) + gap
    height = max(height, 160)

    image = Image.new("RGB", (max_width, height), "#fbfbf8")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (10, 10, max_width - 10, height - 10),
        radius=18,
        fill="#ffffff",
        outline="#d8d6cc",
        width=2,
    )
    y = padding_y
    for line, font, gap in rendered:
        draw.text((padding_x, y), line, fill="#1f2933", font=font)
        bbox = draw.textbbox((padding_x, y), line or " ", font=font)
        y += (bbox[3] - bbox[1]) + gap

    image.save(path, format="PNG", optimize=True)
    return str(path)
