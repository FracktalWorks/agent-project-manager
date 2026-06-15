---
name: report-pdf-export
description: >
  Convert Markdown reports (morning reports, project plans, etc.) to styled PDF
  preserving colors, emojis, tables, images, and formatting. Uses weasyprint for
  pixel-perfect rendering. Trigger keywords: export pdf, convert to pdf, pdf
  report, save as pdf, morning report pdf, render pdf.
argument-hint: 'Markdown file path to convert to PDF, or a directory of .md files.'
user-invocable: true
disable-model-invocation: false
---

# Report PDF Export Skill

## Agent instructions — run this, verify the output

When the user asks to export a report to PDF:

1. **Run the conversion script:**
   ```bash
   python .github/skills/report-pdf-export/scripts/convert_md_to_pdf.py --input path/to/report.md
   ```

2. **Verify the PDF** was created alongside the `.md` file (same name, `.pdf` extension).

3. **Report success** with the output path and file size.

---

## Script reference

| Script | Purpose |
|---|---|
| `scripts/convert_md_to_pdf.py` | Convert a Markdown file to a styled PDF using weasyprint |

---

## Usage

```bash
# Single file
python .github/skills/report-pdf-export/scripts/convert_md_to_pdf.py \
  --input outputs/morning_reports/2026-06-15/morning_report_2026-06-15.md

# Custom output path
python .github/skills/report-pdf-export/scripts/convert_md_to_pdf.py \
  --input report.md \
  --output report.pdf

# Batch convert all .md files in a directory
python .github/skills/report-pdf-export/scripts/convert_md_to_pdf.py \
  --input outputs/morning_reports/2026-06-15/
```

---

## Preserved formatting

| Element | How it's preserved |
|---|---|
| **Bold / Italic** | Rendered via CSS `font-weight: bold` / `font-style: italic` |
| `Inline code` | Monospace font with light grey background |
| Headings (H1–H4) | Navy-colored, sized appropriately |
| Tables | Navy header row, alternating row shading, proper column widths |
| Emojis 🌅 ⚠️ 🤝 📋 | Rendered via system emoji font (Segoe UI Emoji on Windows) |
| Images | Embedded at full resolution via weasyprint |
| Horizontal rules | Styled as accent-red dividers |
| Bullet lists | Proper indentation with bullet markers |

---

## Dependencies

- `markdown` (Python-Markdown) — MD → HTML conversion
- `playwright` — Headless Chromium for pixel-perfect HTML → PDF rendering
- Chromium browser (auto-installed via `python -m playwright install chromium`)

---

## Notes

- The PDF inherits styling from the built-in CSS (navy headings, clean table styles).
- If the input is a directory, all `.md` files in it are converted (non-recursive).
- Output defaults to `{input_stem}.pdf` alongside the source `.md` file.
