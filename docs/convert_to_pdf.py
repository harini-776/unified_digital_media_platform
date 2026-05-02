#!/usr/bin/env python3
"""Convert the journal paper Markdown to a clean, publication-ready PDF."""

import re
import markdown
from weasyprint import HTML, CSS
from weasyprint.text.fonts import FontConfiguration

# ── Read source markdown ──────────────────────────────────────────────────────
with open("/home/hari/finalyear/docs/JOURNAL_PAPER.md", "r") as f:
    md_content = f.read()

# ── Markdown → HTML ───────────────────────────────────────────────────────────
md = markdown.Markdown(extensions=["tables", "fenced_code", "toc"])
body_html = md.convert(md_content)

# ── Full HTML document with embedded CSS ─────────────────────────────────────
html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<style>
/* ── Google Fonts (loaded via @import for WeasyPrint) ── */
@import url('https://fonts.googleapis.com/css2?family=EB+Garamond:ital,wght@0,400;0,600;0,700;1,400&family=Source+Code+Pro:wght@400;600&display=swap');

/* ── Page geometry ── */
@page {{
    size: A4;
    margin: 22mm 20mm 24mm 20mm;
    @bottom-center {{
        content: counter(page);
        font-family: 'EB Garamond', Georgia, serif;
        font-size: 9pt;
        color: #555;
    }}
}}

/* ── Base typography ── */
* {{
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}}

body {{
    font-family: 'EB Garamond', Georgia, 'Times New Roman', serif;
    font-size: 10.5pt;
    line-height: 1.65;
    color: #1a1a1a;
    background: #fff;
    hyphens: auto;
    text-align: justify;
}}

/* ── Title block ── */
h1:first-of-type {{
    font-size: 17pt;
    font-weight: 700;
    text-align: center;
    line-height: 1.3;
    color: #0a1628;
    margin-bottom: 6pt;
    padding-bottom: 0;
    border: none;
    letter-spacing: -0.3px;
}}

/* ── Abstract ── */
blockquote, .abstract {{
    background: #f7f9fc;
    border-left: 3px solid #2d5fa6;
    margin: 14pt 0 18pt 0;
    padding: 10pt 14pt;
    font-size: 9.5pt;
    line-height: 1.6;
    color: #222;
    border-radius: 0 4px 4px 0;
}}

/* ── Section headings ── */
h2 {{
    font-size: 12pt;
    font-weight: 700;
    color: #0a1628;
    margin-top: 18pt;
    margin-bottom: 5pt;
    padding-bottom: 2pt;
    border-bottom: 1.5px solid #2d5fa6;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

h3 {{
    font-size: 10.5pt;
    font-weight: 700;
    color: #1e3a6e;
    margin-top: 12pt;
    margin-bottom: 3pt;
}}

h4 {{
    font-size: 10.5pt;
    font-weight: 600;
    font-style: italic;
    color: #2d5fa6;
    margin-top: 8pt;
    margin-bottom: 2pt;
}}

/* ── Paragraphs ── */
p {{
    margin-bottom: 6pt;
    orphans: 2;
    widows: 2;
}}

/* ── Two-column layout for body (after abstract) ── */
.two-col {{
    column-count: 2;
    column-gap: 14mm;
    column-rule: 0.5px solid #dce4f0;
}}

/* ── Tables ── */
table {{
    border-collapse: collapse;
    width: 100%;
    margin: 10pt 0 12pt 0;
    font-size: 9pt;
    break-inside: avoid;
}}

thead {{
    background-color: #0a1628;
    color: #ffffff;
}}

thead th {{
    padding: 5pt 7pt;
    text-align: left;
    font-weight: 600;
    letter-spacing: 0.2px;
}}

tbody tr:nth-child(even) {{
    background-color: #f0f4fb;
}}

tbody tr:hover {{
    background-color: #e4ecf7;
}}

tbody td {{
    padding: 4pt 7pt;
    border-bottom: 0.5px solid #d0d9ec;
    vertical-align: top;
}}

tfoot td {{
    font-style: italic;
    font-size: 8.5pt;
    color: #555;
    padding: 3pt 7pt;
}}

/* Bold rows (full TrustMedia rows in tables) */
tbody tr td strong, tbody tr td b {{
    font-weight: 700;
    color: #0a1628;
}}

/* ── Code blocks ── */
pre, code {{
    font-family: 'Source Code Pro', 'Courier New', monospace;
    font-size: 8pt;
    background: #f4f6fb;
    border: 0.5px solid #d0d9ec;
    border-radius: 3px;
}}

pre {{
    padding: 8pt 10pt;
    margin: 8pt 0 10pt 0;
    overflow-x: auto;
    line-height: 1.5;
    break-inside: avoid;
    white-space: pre-wrap;
    word-break: break-all;
}}

code {{
    padding: 1pt 3pt;
}}

pre code {{
    border: none;
    background: transparent;
    padding: 0;
}}

/* ── Lists ── */
ul, ol {{
    margin: 4pt 0 8pt 18pt;
}}

li {{
    margin-bottom: 2pt;
}}

/* ── Horizontal rule ── */
hr {{
    border: none;
    border-top: 1px solid #2d5fa6;
    margin: 16pt 0;
}}

/* ── Section numbers ── */
h2::before {{
    color: #2d5fa6;
}}

/* ── Math / equations ── */
.math {{
    font-family: 'EB Garamond', Georgia, serif;
    font-style: italic;
    text-align: center;
    margin: 8pt 20pt;
    color: #0a1628;
}}

/* ── Figure captions ── */
em {{
    color: #333;
}}

p > em:only-child {{
    display: block;
    text-align: center;
    font-size: 9pt;
    color: #555;
    margin: -6pt 0 10pt 0;
}}

/* ── References ── */
.references p {{
    font-size: 9pt;
    line-height: 1.5;
    margin-bottom: 3pt;
    text-indent: -14pt;
    padding-left: 14pt;
}}

/* ── Keywords block ── */
.keywords {{
    font-size: 9pt;
    margin: 8pt 0 16pt 0;
    color: #333;
}}

.keywords strong {{
    color: #0a1628;
}}

/* ── Page break helpers ── */
h2, h3 {{
    break-after: avoid;
}}

table, pre, figure {{
    break-inside: avoid;
}}
</style>
</head>
<body>

{body_html}

</body>
</html>"""

# ── Fix abstract paragraph: wrap the bold "Abstract" block ──────────────────
# The markdown renders "**Abstract** — ..." as a <p> — wrap it as a styled box
html_doc = re.sub(
    r'<p><strong>Abstract</strong>',
    r'<div class="abstract"><p><strong>Abstract</strong>',
    html_doc
)
html_doc = re.sub(
    r'(<div class="abstract">.*?</p>)\s*<p><strong>Keywords',
    r'\1</div>\n<p class="keywords"><strong>Keywords',
    html_doc,
    flags=re.DOTALL
)

# Close keywords paragraph properly
html_doc = re.sub(
    r'(<p class="keywords">.*?</p>)',
    r'\1',
    html_doc,
    flags=re.DOTALL
)

# ── Convert to PDF ────────────────────────────────────────────────────────────
font_config = FontConfiguration()
html_obj = HTML(string=html_doc, base_url="/home/hari/finalyear/docs/")
css = CSS(string="", font_config=font_config)

output_path = "/home/hari/finalyear/docs/TrustMedia_Journal_Paper.pdf"
html_obj.write_pdf(output_path, font_config=font_config)
print(f"PDF written to: {output_path}")
