---
name: report-pdf-export
description: >
  Convert Markdown reports (morning reports, project plans, etc.) to styled PDF
  preserving colors, emojis, tables, images, and formatting. Uses Playwright +
  headless Chromium for pixel-perfect rendering with coloured emojis via
  Noto Color Emoji. Trigger keywords: export pdf, convert to pdf, pdf
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
| `scripts/convert_md_to_pdf.py` | Convert a Markdown file to a styled PDF using Playwright + headless Chromium |

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
| Emojis 🌅 ⚠️ 🤝 📋 | Rendered via Noto Color Emoji font (installed via `fonts-noto-color-emoji`) |
| Images | Embedded at full resolution via headless Chromium |
| Horizontal rules | Styled as accent-red dividers |
| Bullet lists | Proper indentation with bullet markers |

---

## Dependencies

- `markdown` (Python-Markdown) — MD → HTML conversion
- `playwright` — Headless Chromium for pixel-perfect HTML → PDF rendering
- Chromium browser (auto-installed via `python -m playwright install chromium`)
- **System packages** for Chromium: `libatk1.0-0t64 libatk-bridge2.0-0t64 libcups2t64 libdrm2 libxkbcommon0 libxcomposite1 libxdamage1 libxfixes3 libxrandr2 libgbm1 libpango-1.0-0 libcairo2 libasound2t64 libnspr4 libnss3`
- **Emoji font:** `fonts-noto-color-emoji` — required for coloured emoji rendering in PDF; without it emojis render as blank boxes.

---

## Notes

- The PDF inherits styling from the built-in CSS (navy headings, clean table styles).
- If the input is a directory, all `.md` files in it are converted (non-recursive).
- Output defaults to `{input_stem}.pdf` alongside the source `.md` file.

## Edge Cases

### Missing emoji rendering (Added 2026-07-04)
- **Symptom:** Emojis render as blank boxes or missing glyphs in the PDF even though they appear correctly in Markdown.
- **Root cause:** No colour emoji font installed on the system (Chromium falls back to monochrome or blank glyphs).
- **Fix:** `sudo apt-get install fonts-noto-color-emoji` + refresh font cache with `fc-cache -fv`. The CSS `font-family` must include `'Noto Color Emoji'` ahead of the generic `sans-serif` fallback.

### Chromium fails to launch (Added 2026-07-04)
- **Symptom:** `TargetClosedError: BrowserType.launch: ... error while loading shared libraries: libatk-1.0.so.0`
- **Root cause:** Missing system dependencies for headless Chromium on Linux.
- **Fix:** Install required system packages (see Dependencies above). Do NOT fall back to weasyprint — it doesn't render coloured emojis.
