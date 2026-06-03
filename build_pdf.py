"""Convert intern_report.md to a polished academic-style PDF using WeasyPrint."""

from pathlib import Path

import markdown
from weasyprint import HTML, CSS

HERE = Path(__file__).parent
SRC = HERE / "intern_report.md"
OUT = HERE / "intern_report.pdf"

md_text = SRC.read_text(encoding="utf-8")

html_body = markdown.markdown(
    md_text,
    extensions=["tables", "fenced_code", "codehilite", "toc", "sane_lists"],
    extension_configs={
        "codehilite": {"guess_lang": False, "noclasses": True, "pygments_style": "friendly"},
    },
)

css = """
@page {
    size: A4;
    margin: 1in 0.9in 1in 1in;
    @bottom-right {
        content: "Page " counter(page) " of " counter(pages);
        font-family: "Times New Roman", Times, serif;
        font-size: 9pt;
        color: #555;
    }
    @top-center {
        content: "Internship Report — TrustMedia Project";
        font-family: "Times New Roman", Times, serif;
        font-size: 9pt;
        color: #777;
    }
}

html { font-family: "Times New Roman", Times, serif; }
body {
    font-size: 11.5pt;
    line-height: 1.55;
    color: #111;
    text-align: justify;
    hyphens: auto;
    widows: 3;
    orphans: 3;
}

h1 {
    font-size: 22pt;
    font-weight: bold;
    text-align: center;
    color: #1a3a6d;
    margin-top: 0;
    margin-bottom: 0.4em;
    page-break-before: avoid;
    page-break-after: avoid;
}
h2 {
    font-size: 16pt;
    color: #1a3a6d;
    border-bottom: 2px solid #1a3a6d;
    padding-bottom: 4px;
    margin-top: 1.2em;
    page-break-before: always;
    page-break-after: avoid;
}
/* Don't force a page break before the very first h2 */
h2:first-of-type { page-break-before: auto; }

h3 {
    font-size: 13pt;
    color: #2b4f87;
    margin-top: 1.1em;
    margin-bottom: 0.3em;
    page-break-after: avoid;
}
h4 {
    font-size: 12pt;
    color: #2b4f87;
    margin-top: 0.9em;
    margin-bottom: 0.2em;
    page-break-after: avoid;
}

p { margin: 0.5em 0; }

ul, ol { margin: 0.5em 0 0.5em 1.4em; }
li { margin: 0.2em 0; }

strong { color: #111; }
em { color: #333; }

/* Tables */
table {
    border-collapse: collapse;
    width: 100%;
    margin: 0.8em 0;
    font-size: 10pt;
    page-break-inside: avoid;
}
th, td {
    border: 1px solid #888;
    padding: 5px 8px;
    text-align: left;
    vertical-align: top;
}
th {
    background-color: #d6e2f0;
    color: #1a3a6d;
    font-weight: bold;
}
tr:nth-child(even) td { background-color: #f5f8fc; }

/* Code */
pre {
    background-color: #f4f4f4;
    border: 1px solid #d0d0d0;
    border-left: 3px solid #1a3a6d;
    padding: 8px 10px;
    font-size: 9pt;
    line-height: 1.35;
    overflow-x: auto;
    page-break-inside: avoid;
    white-space: pre-wrap;
    word-wrap: break-word;
}
code {
    font-family: "Courier New", Courier, monospace;
    font-size: 10pt;
    background-color: #f0f0f0;
    padding: 1px 4px;
    border-radius: 2px;
}
pre code {
    background: none;
    padding: 0;
    font-size: 9pt;
}

/* Blockquote — used for the ★ Insight callouts */
blockquote {
    border-left: 4px solid #f0a500;
    background-color: #fff8e8;
    margin: 0.8em 0;
    padding: 6px 12px;
    font-style: italic;
    page-break-inside: avoid;
}

hr {
    border: none;
    border-top: 1px solid #bbb;
    margin: 1.2em 0;
}

a { color: #1a3a6d; text-decoration: none; }
"""

html_doc = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Internship Report — TrustMedia</title>
</head>
<body>
{html_body}
</body>
</html>
"""

(HERE / "intern_report_preview.html").write_text(html_doc, encoding="utf-8")

HTML(string=html_doc, base_url=str(HERE)).write_pdf(
    OUT, stylesheets=[CSS(string=css)],
)

print(f"PDF written to: {OUT}")
print(f"Size: {OUT.stat().st_size / 1024:.1f} KB")
