#!/usr/bin/env python3
"""
convert_md_to_pdf.py — Convert Markdown reports to styled PDF.

Preserves colors, emojis, tables, images, and formatting using
Python-Markdown → HTML → Playwright (headless Chromium) pipeline.

Usage:
  python convert_md_to_pdf.py --input report.md
  python convert_md_to_pdf.py --input report.md --output report.pdf
  python convert_md_to_pdf.py --input path/to/dir/   # batch convert
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

# ---------------------------------------------------------------------------
# CSS stylesheet — Fracktal Works branded, preserves report formatting
# ---------------------------------------------------------------------------
CSS = """
@page {
    size: A4;
    margin: 1.5cm 1.8cm 1.5cm 1.8cm;
    @bottom-center {
        content: "Fracktal Works — Confidential";
        font-family: 'Segoe UI', 'Calibri', sans-serif;
        font-size: 8pt;
        color: #999;
    }
}

body {
    font-family: 'Segoe UI', 'Calibri', 'Helvetica Neue', Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.5;
    color: #333;
}

/* ── Headings ─────────────────────────────────────────────── */
h1 {
    font-size: 18pt;
    color: #1A1A2E;
    border-bottom: 2px solid #C0392B;
    padding-bottom: 4pt;
    margin-top: 24pt;
    margin-bottom: 8pt;
    page-break-before: avoid;
}
h2 {
    font-size: 14pt;
    color: #1A1A2E;
    border-bottom: 1px solid #DDD;
    padding-bottom: 3pt;
    margin-top: 20pt;
    margin-bottom: 6pt;
    page-break-before: avoid;
}
h3 {
    font-size: 12pt;
    color: #C0392B;
    margin-top: 16pt;
    margin-bottom: 4pt;
    page-break-before: avoid;
}
h4 {
    font-size: 11pt;
    color: #1A1A2E;
    margin-top: 12pt;
    margin-bottom: 3pt;
    page-break-before: avoid;
}

/* ── Paragraphs & inline ──────────────────────────────────── */
p {
    margin: 3pt 0 6pt 0;
}
strong {
    color: #1A1A2E;
}
code {
    font-family: 'Cascadia Code', 'Consolas', 'Courier New', monospace;
    font-size: 9pt;
    background: #F5F5F5;
    padding: 1pt 4pt;
    border-radius: 2pt;
    color: #C0392B;
}
em {
    color: #555;
}

/* ── Tables (critical for morning reports) ────────────────── */
table {
    width: 100%;
    border-collapse: collapse;
    margin: 8pt 0 12pt 0;
    font-size: 9pt;
    page-break-inside: avoid;
}
th {
    background-color: #1A1A2E;
    color: #FFFFFF;
    font-weight: bold;
    padding: 5pt 6pt;
    text-align: left;
    border: 0.5pt solid #1A1A2E;
}
td {
    padding: 4pt 6pt;
    border: 0.5pt solid #CCC;
    vertical-align: top;
}
tr:nth-child(even) td {
    background-color: #FAFAFA;
}
tr:nth-child(odd) td {
    background-color: #FFFFFF;
}

/* ── Horizontal rules ─────────────────────────────────────── */
hr {
    border: none;
    border-top: 1.5px solid #C0392B;
    margin: 16pt 0;
}

/* ── Lists ────────────────────────────────────────────────── */
ul, ol {
    margin: 4pt 0 8pt 0;
    padding-left: 20pt;
}
li {
    margin: 2pt 0;
}

/* ── Blockquotes ──────────────────────────────────────────── */
blockquote {
    border-left: 3pt solid #C0392B;
    margin: 8pt 0;
    padding: 6pt 12pt;
    background: #FDF2F2;
    color: #555;
}

/* ── Images ───────────────────────────────────────────────── */
img {
    max-width: 100%;
    height: auto;
    display: block;
    margin: 8pt auto;
}

/* ── Emoji rendering ──────────────────────────────────────── */
* {
    font-variant-emoji: emoji;
}

/* ── Page breaks ──────────────────────────────────────────── */
@media print {
    h1, h2, h3, h4 {
        page-break-after: avoid;
    }
    table {
        page-break-inside: avoid;
    }
}
"""

# Markdown extensions for full feature support
MD_EXTENSIONS = [
    "tables",
    "fenced_code",
    "codehilite",
    "toc",
    "nl2br",
    "sane_lists",
]

# ---------------------------------------------------------------------------
# Core conversion
# ---------------------------------------------------------------------------


def convert_md_to_pdf(md_path: Path, pdf_path: Path | None = None) -> Path:
    """Convert a Markdown file to a styled PDF.

    Args:
        md_path: Path to the .md source file.
        pdf_path: Optional output path. Defaults to same dir, same stem, .pdf.

    Returns:
        Path to the generated PDF file.
    """
    if not md_path.exists():
        raise FileNotFoundError(f"Markdown file not found: {md_path}")

    if pdf_path is None:
        pdf_path = md_path.with_suffix(".pdf")

    # Read markdown
    md_text = md_path.read_text(encoding="utf-8")

    # Convert MD → HTML
    md_extensions = [e for e in MD_EXTENSIONS if e != "codehilite"]
    html_body = markdown.markdown(md_text, extensions=md_extensions)

    # Wrap in full HTML document with CSS
    full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>{CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""

    # Render to PDF via Playwright (headless Chromium)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(full_html, wait_until="networkidle")
        page.pdf(
            path=str(pdf_path),
            format="A4",
            margin={"top": "15mm", "right": "18mm", "bottom": "15mm", "left": "18mm"},
            print_background=True,
            display_header_footer=False,
        )
        browser.close()

    return pdf_path


def convert_directory(dir_path: Path) -> list[Path]:
    """Convert all .md files in a directory (non-recursive) to PDF.

    Args:
        dir_path: Path to directory containing .md files.

    Returns:
        List of generated PDF paths.
    """
    if not dir_path.is_dir():
        raise NotADirectoryError(f"Not a directory: {dir_path}")

    pdfs: list[Path] = []
    for md_file in sorted(dir_path.glob("*.md")):
        pdf_path = convert_md_to_pdf(md_file)
        pdfs.append(pdf_path)
        print(f"  ✓ {md_file.name} → {pdf_path.name}")
    return pdfs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Convert Markdown reports to styled PDF (preserves colors, emojis, tables, images)."
    )
    parser.add_argument(
        "--input", "-i",
        required=True,
        help="Path to .md file or directory of .md files to convert.",
    )
    parser.add_argument(
        "--output", "-o",
        default=None,
        help="Output PDF path (only for single-file conversion).",
    )
    args = parser.parse_args()

    in_path = Path(args.input).resolve()

    if not in_path.exists():
        print(f"[ERROR] Input not found: {in_path}")
        sys.exit(1)

    if in_path.is_dir():
        print(f"Converting all .md files in: {in_path}")
        pdfs = convert_directory(in_path)
        print(f"\nDone — {len(pdfs)} PDF(s) generated.")
    else:
        out_path = Path(args.output).resolve() if args.output else None
        pdf = convert_md_to_pdf(in_path, out_path)
        size_kb = pdf.stat().st_size / 1024
        print(f"✓ PDF generated: {pdf} ({size_kb:.1f} KB)")


if __name__ == "__main__":
    main()
