# -*- coding: utf-8 -*-
"""
Build an HTML (mermaid-rendering, Thai-font) file from RAG_Module.md.
The HTML is then printed to PDF via headless Chrome.
"""
import re
import html
import markdown
from pathlib import Path

HERE = Path(__file__).resolve().parent
MD_PATH = HERE / "RAG_Module.md"
HTML_PATH = HERE / "_RAG_Module.html"

md_text = MD_PATH.read_text(encoding="utf-8")

# ── 1. Extract mermaid fenced blocks before markdown conversion ──────────────
mermaid_blocks = []


def _stash_mermaid(m):
    code = m.group(1)
    idx = len(mermaid_blocks)
    mermaid_blocks.append(code)
    return f"\n\nMERMAIDPLACEHOLDER{idx}ENDPLACEHOLDER\n\n"


md_text = re.sub(r"```mermaid\n(.*?)```", _stash_mermaid, md_text, flags=re.DOTALL)


# ── 2. GitHub-like slugify (keeps Thai chars) so TOC anchors line up ─────────
def gh_slugify(value, separator="-"):
    value = value.strip().lower()
    # remove anything that's not a word char (incl. Thai), space, or hyphen
    value = re.sub(r"[^\w\s\-]", "", value, flags=re.UNICODE)
    value = re.sub(r"[\s]+", separator, value)
    return value


# ── 3. Markdown → HTML ───────────────────────────────────────────────────────
mdc = markdown.Markdown(
    extensions=["extra", "toc", "sane_lists", "admonition"],
    extension_configs={"toc": {"slugify": gh_slugify}},
)
body = mdc.convert(md_text)

# ── 4. Re-insert mermaid blocks as <pre class="mermaid"> (escaped text) ──────
def _restore_mermaid(m):
    idx = int(m.group(1))
    code = html.escape(mermaid_blocks[idx])
    return f'<pre class="mermaid">{code}</pre>'


# placeholders may be wrapped in <p>...</p> by markdown
body = re.sub(
    r"<p>MERMAIDPLACEHOLDER(\d+)ENDPLACEHOLDER</p>", _restore_mermaid, body
)
body = re.sub(
    r"MERMAIDPLACEHOLDER(\d+)ENDPLACEHOLDER", _restore_mermaid, body
)

# ── 5. Full HTML document ────────────────────────────────────────────────────
HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<title>RAG Module — Technical Documentation</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sarabun:wght@400;600;700&family=JetBrains+Mono:wght@400;600&display=swap" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
<style>
  @page {{ size: A4; margin: 18mm 15mm; }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Sarabun', 'Leelawadee UI', 'Tahoma', sans-serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: #1a1a1a;
    max-width: 100%;
    margin: 0;
  }}
  h1, h2, h3, h4 {{
    font-weight: 700;
    line-height: 1.25;
    margin-top: 1.4em;
    margin-bottom: 0.5em;
    color: #0b3d5c;
  }}
  h1 {{ font-size: 22pt; border-bottom: 3px solid #0b3d5c; padding-bottom: 6px; }}
  h2 {{ font-size: 16pt; border-bottom: 1px solid #c9d6df; padding-bottom: 4px; margin-top: 1.6em; page-break-after: avoid; }}
  h3 {{ font-size: 13pt; color: #11597f; page-break-after: avoid; }}
  h4 {{ font-size: 11.5pt; color: #11597f; }}
  p {{ margin: 0.5em 0; }}
  a {{ color: #1565a6; text-decoration: none; }}
  hr {{ border: none; border-top: 1px solid #d0d7de; margin: 1.5em 0; }}

  code {{
    font-family: 'JetBrains Mono', 'Consolas', monospace;
    font-size: 9pt;
    background: #f0f3f6;
    padding: 1px 5px;
    border-radius: 4px;
    color: #b5197a;
  }}
  pre {{
    background: #f6f8fa;
    border: 1px solid #d0d7de;
    border-radius: 8px;
    padding: 12px 14px;
    overflow-x: auto;
    page-break-inside: avoid;
    white-space: pre-wrap;
    word-break: break-word;
  }}
  pre code {{
    background: none;
    padding: 0;
    color: #24292f;
    font-size: 8.7pt;
  }}

  table {{
    border-collapse: collapse;
    width: 100%;
    margin: 0.8em 0;
    font-size: 9.3pt;
    page-break-inside: avoid;
  }}
  th, td {{
    border: 1px solid #c9d6df;
    padding: 6px 9px;
    text-align: left;
    vertical-align: top;
  }}
  th {{ background: #0b3d5c; color: #fff; font-weight: 600; }}
  tr:nth-child(even) td {{ background: #f4f8fb; }}

  blockquote {{
    border-left: 4px solid #1565a6;
    background: #eef5fb;
    margin: 0.8em 0;
    padding: 6px 14px;
    color: #33475b;
    border-radius: 0 6px 6px 0;
  }}
  ul, ol {{ margin: 0.5em 0; padding-left: 1.6em; }}
  li {{ margin: 0.2em 0; }}

  pre.mermaid {{
    background: #ffffff;
    border: 1px solid #e2e8f0;
    text-align: center;
    white-space: normal;
  }}
  pre.mermaid svg {{ max-width: 100%; height: auto; }}

  /* table-of-contents list at top */
  body > ol:first-of-type {{ }}
</style>
</head>
<body>
{body}
<script>
  mermaid.initialize({{ startOnLoad: false, theme: 'default', securityLevel: 'loose', flowchart: {{ htmlLabels: true, useMaxWidth: true }} }});
  window.addEventListener('load', async () => {{
    try {{ await mermaid.run({{ querySelector: 'pre.mermaid' }}); }}
    catch (e) {{ console.error('mermaid error', e); }}
    document.title = 'RENDER_DONE';
  }});
</script>
</body>
</html>
"""

HTML_PATH.write_text(HTML_TEMPLATE.format(body=body), encoding="utf-8")
print(f"[BUILD] HTML written: {HTML_PATH}")
print(f"[BUILD] mermaid blocks: {len(mermaid_blocks)}")
