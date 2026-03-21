#!/usr/bin/env python3

import os
import sys
import shutil
from pathlib import Path
from bs4 import BeautifulSoup
import markdown
import requests
from urllib.parse import urlparse
from datetime import datetime

# --- CONFIGURATION ---
MD_DIR = "md"
DITA_DIR = "dita"
HTML_DIR = "html"
TOC_MD = "toc.md"
LOG_FILE = "generate-dita.log"

# ---------------------------------------------------------------------
def log(message: str):
    """Write message to stdout and append to log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        logf.write(line + "\n")

def normalize_path(path: str) -> str:
    """Normalize a file path for consistent comparison."""
    # Strip leading ./ and /
    path = path.lstrip("./").lstrip("/")
    if path.endswith(".html"):
        path = path[:-5] + ".md"
    return os.path.normpath(path)

def resolve_image_path(img_src: str, md_file_path: str) -> str:
    """
    Resolve image path to point to the html directory.

    Since images are already downloaded in the html directory by generate-html.py,
    we just need to create a relative path from the DITA output location to the html directory.

    Args:
        img_src: The image src from the markdown/HTML (relative path)
        md_file_path: Path to the source markdown file

    Returns:
        Relative path from DITA directory to the image in html directory
    """
    # Skip data URIs and external URLs
    if img_src.startswith(('data:', 'http://', 'https://')):
        return img_src

    # The img_src is a path relative to the MD file location
    # We need to resolve it to an absolute path, then make it relative to DITA_DIR

    try:
        md_path = Path(md_file_path)

        # Resolve the image path relative to the markdown file
        if md_path.is_absolute():
            img_abs_path = (md_path.parent / img_src).resolve()
        else:
            img_abs_path = (Path(md_file_path).parent / img_src).resolve()

        # Make it relative to the DITA directory
        relative_to_dita = os.path.relpath(img_abs_path, DITA_DIR)

        log(f"✓ Resolved image path: {img_src} -> {relative_to_dita}")
        return relative_to_dita

    except Exception as e:
        log(f"⚠️  Could not resolve image path {img_src}: {e}")
        return img_src

def escape_xml(text: str) -> str:
    """Escape special XML characters and replace multi-byte UTF-8 characters.

    Apache Xerces has a bug in UTF8Reader where multi-byte UTF-8 characters
    landing on a 2048-byte buffer boundary cause an ArrayIndexOutOfBoundsException.
    We replace common non-ASCII characters with ASCII equivalents to avoid this.
    """
    text = (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace('"', "&quot;")
            .replace("'", "&apos;"))

    # Replace multi-byte UTF-8 characters that trigger Xerces buffer bug
    text = (text
            .replace("\u2014", "--")       # em-dash (—)
            .replace("\u2013", "-")        # en-dash (–)
            .replace("\u2192", "->")       # right arrow (→)
            .replace("\u2190", "<-")       # left arrow (←)
            .replace("\u2026", "...")       # ellipsis (…)
            .replace("\u201c", '"')        # left double quote
            .replace("\u201d", '"')        # right double quote
            .replace("\u2018", "'")        # left single quote
            .replace("\u2019", "'")        # right single quote
            .replace("\U0001f9ea", "[Test]")  # 🧪
            .replace("\U0001f4dd", "[Note]")  # 📝
            .replace("\U0001f527", "[Tool]")  # 🔧
            .replace("\U0001f50d", "[Search]"))  # 🔍

    # Catch any remaining non-ASCII characters and replace with '?'
    text = text.encode('ascii', errors='replace').decode('ascii')

    return text

def detect_language(code_text: str) -> str:
    """
    Auto-detect programming language for unlabeled code blocks.

    Uses heuristics to identify common languages based on syntax patterns.
    Returns the detected language name or None if unable to detect.
    """
    if not code_text or not code_text.strip():
        return None

    code_lower = code_text.lower()
    code_stripped = code_text.strip()

    # JSON detection - starts with { or [ (common for JSON)
    if code_stripped.startswith(('{', '[')):
        # Check for JSON-like patterns
        if any(pattern in code_text for pattern in ['":', '": ', '":"']):
            return 'json'

    # TypeScript/JavaScript detection
    ts_js_patterns = [
        'interface ', 'type ', 'const ', 'let ', 'var ',
        'function ', '=>', 'async ', 'await ', 'import ',
        'export ', 'class ', 'extends ', 'implements '
    ]
    if any(pattern in code_text for pattern in ts_js_patterns):
        # TypeScript-specific patterns
        if any(ts_pattern in code_text for ts_pattern in [
            'interface ', 'type ', ': string', ': number', ': boolean',
            '<T>', 'extends ', 'implements '
        ]):
            return 'typescript'
        return 'javascript'

    # Bash/shell script detection
    bash_patterns = [
        '#!/bin/bash', '#!/bin/sh', 'npm ', 'yarn ', 'npx ',
        'git ', 'cd ', 'ls ', 'mkdir ', 'chmod ', 'echo $',
        'export ', '${', 'if [', 'then', 'elif', 'fi'
    ]
    if code_stripped.startswith('#!/bin/') or code_stripped.startswith('$ '):
        return 'bash'
    if any(pattern in code_text for pattern in bash_patterns):
        return 'bash'

    # YAML detection
    yaml_patterns = ['---', 'apiVersion:', 'kind:', 'metadata:', 'spec:']
    if code_stripped.startswith('---') or any(pattern in code_text for pattern in yaml_patterns):
        # Make sure it's not markdown frontmatter
        lines = code_text.split('\n')
        if len(lines) > 1 and any(':' in line and not line.strip().startswith('#') for line in lines):
            return 'yaml'

    # Dockerfile detection
    if any(code_stripped.startswith(cmd) for cmd in ['FROM ', 'RUN ', 'COPY ', 'ADD ', 'ENV ', 'WORKDIR ']):
        return 'dockerfile'

    # Python detection
    python_patterns = ['def ', 'import ', 'from ', 'class ', 'if __name__', 'print(']
    if any(pattern in code_text for pattern in python_patterns):
        return 'python'

    # Markdown detection
    if code_stripped.startswith('#') and '\n## ' in code_text:
        return 'markdown'

    # Vim script detection
    if 'set ' in code_text and ('syntax ' in code_text or 'colorscheme ' in code_text):
        return 'vim'

    # Lua detection
    if 'local ' in code_text or 'function(' in code_text or 'end' in code_text:
        if 'require' in code_lower or 'return' in code_lower:
            return 'lua'

    # If unable to detect, return None
    return None

def is_inline_image(img_element) -> bool:
    """
    Determine if an image is inline (icon) or standalone (figure).

    Inline images are:
    - Wrapped in a span
    - Part of a block element that contains non-whitespace text content

    Standalone images are:
    - Direct child of a block element with no other non-whitespace content
    """
    parent = img_element.parent
    if not parent:
        return False

    # If wrapped in a span, it's inline
    if parent.name == 'span':
        return True

    # Check if the parent block has other non-whitespace content
    if parent.name in ['p', 'div', 'li', 'td', 'th']:
        # Get all text content excluding the img itself
        text_content = ""
        for child in parent.children:
            if child.name != 'img' and hasattr(child, 'get_text'):
                text_content += child.get_text()
            elif isinstance(child, str):
                text_content += child

        # If there's non-whitespace text, the image is inline
        if text_content.strip():
            return True

    return False

def convert_element_content(element) -> str:
    """Convert HTML element content to DITA, handling links."""
    result = []
    for child in element.children:
        if isinstance(child, str):
            result.append(escape_xml(child))
        elif child.name == "a":
            # Check if this is an internal DITA link
            if child.get("data-dita-href"):
                href = child["data-dita-href"]
                link_text = child.get_text(strip=True)
                result.append(f'<xref href="{href}" format="dita">{escape_xml(link_text)}</xref>')
            else:
                # External link or unresolved link
                href = child.get("href", "")
                link_text = child.get_text(strip=True)
                if href.startswith("http://") or href.startswith("https://"):
                    result.append(f'<xref href="{escape_xml(href)}" format="html" scope="external">{escape_xml(link_text)}</xref>')
                else:
                    # Just text for unresolved internal links
                    result.append(escape_xml(link_text))
        elif child.name == "code":
            result.append(f'<codeph>{escape_xml(child.get_text())}</codeph>')
        elif child.name == "strong" or child.name == "b":
            result.append(f'<b>{escape_xml(child.get_text())}</b>')
        elif child.name == "em" or child.name == "i":
            result.append(f'<i>{escape_xml(child.get_text())}</i>')
        elif child.name == "img":
            img_src = child.get("src", "")
            img_alt = child.get("alt", "")
            if img_src:
                # Determine if this is an inline icon or standalone figure
                if is_inline_image(child):
                    # Inline icon: height limited to line height
                    result.append(f'<image href="{escape_xml(img_src)}" placement="inline">')
                else:
                    # Standalone figure: full size, max 50% screen width
                    result.append(f'<image href="{escape_xml(img_src)}" placement="break" align="left">')
                if img_alt:
                    result.append(f'<alt>{escape_xml(img_alt)}</alt>')
                result.append('</image>')
        else:
            result.append(escape_xml(child.get_text()))
    return "".join(result)

def convert_list_item_content(li_element) -> list:
    """Convert list item content, handling both inline and block elements."""
    result = []

    for child in li_element.children:
        if isinstance(child, str):
            text = child.strip()
            if text:
                result.append(escape_xml(text))
        elif child.name == "p":
            # Paragraph in list item
            result.append('<p>' + convert_element_content(child) + '</p>')
        elif child.name == "pre":
            # Code block in list item
            code_elem = child.find("code")
            if code_elem:
                classes = code_elem.get("class", [])
                language = None

                if isinstance(classes, list):
                    for cls in classes:
                        if cls.startswith("language-"):
                            language = cls.replace("language-", "")
                            break
                elif isinstance(classes, str) and classes.startswith("language-"):
                    language = classes.replace("language-", "")

                code_text = code_elem.get_text()

                # Auto-detect language if not specified
                if not language:
                    detected = detect_language(code_text)
                    if detected:
                        language = detected
                        log(f"🔍 Auto-detected language in list: {language}")

                if language:
                    result.append(f'<codeblock outputclass="language-{language}">{escape_xml(code_text)}</codeblock>')
                else:
                    result.append(f'<codeblock>{escape_xml(code_text)}</codeblock>')
            else:
                code_text = child.get_text()

                # Try auto-detection for pre blocks without code element
                detected = detect_language(code_text)
                if detected:
                    log(f"🔍 Auto-detected language in list: {detected}")
                    result.append(f'<codeblock outputclass="language-{detected}">{escape_xml(code_text)}</codeblock>')
                else:
                    result.append(f'<codeblock>{escape_xml(code_text)}</codeblock>')
        elif child.name in ["ul", "ol"]:
            # Nested list - handle recursively
            # Note: For simplicity, we'll inline the list content
            # More sophisticated handling could be added here
            pass
        elif child.name == "code":
            result.append(f'<codeph>{escape_xml(child.get_text())}</codeph>')
        elif child.name == "strong" or child.name == "b":
            result.append(f'<b>{escape_xml(child.get_text())}</b>')
        elif child.name == "em" or child.name == "i":
            result.append(f'<i>{escape_xml(child.get_text())}</i>')
        elif child.name == "a":
            # Handle links
            if child.get("data-dita-href"):
                href = child["data-dita-href"]
                link_text = child.get_text(strip=True)
                result.append(f'<xref href="{href}" format="dita">{escape_xml(link_text)}</xref>')
            else:
                href = child.get("href", "")
                link_text = child.get_text(strip=True)
                if href.startswith("http://") or href.startswith("https://"):
                    result.append(f'<xref href="{escape_xml(href)}" format="html" scope="external">{escape_xml(link_text)}</xref>')
                else:
                    result.append(escape_xml(link_text))

    return result

def convert_table_to_dita(table_element) -> str:
    """Convert HTML table to DITA table with formatting preserved."""
    dita_table = ['    <table>']

    # Find thead and tbody
    thead = table_element.find("thead")
    tbody = table_element.find("tbody")

    # Determine column count from first row
    num_cols = 1
    if thead:
        first_row = thead.find("tr")
        if first_row:
            num_cols = len(first_row.find_all(["th", "td"]))
    elif tbody:
        first_row = tbody.find("tr")
        if first_row:
            num_cols = len(first_row.find_all(["td", "th"]))

    dita_table.append(f'      <tgroup cols="{num_cols}">')

    # Add column specifications
    for i in range(num_cols):
        dita_table.append('        <colspec colname="c{}" colnum="{}"/>'.format(i+1, i+1))

    if thead:
        dita_table.append('        <thead>')
        for tr in thead.find_all("tr"):
            dita_table.append('          <row>')
            for th in tr.find_all(["th", "td"]):
                # Preserve formatting in table cells
                cell_content = convert_element_content(th)

                # Handle colspan/rowspan
                colspan = th.get("colspan")
                rowspan = th.get("rowspan")

                entry_attrs = []
                if colspan:
                    entry_attrs.append(f'namest="c1" nameend="c{colspan}"')
                if rowspan:
                    entry_attrs.append(f'morerows="{int(rowspan)-1}"')

                if entry_attrs:
                    dita_table.append(f'            <entry {" ".join(entry_attrs)}>{cell_content}</entry>')
                else:
                    dita_table.append(f'            <entry>{cell_content}</entry>')
            dita_table.append('          </row>')
        dita_table.append('        </thead>')

    if tbody:
        dita_table.append('        <tbody>')
        for tr in tbody.find_all("tr"):
            dita_table.append('          <row>')
            for td in tr.find_all(["td", "th"]):
                # Preserve formatting in table cells
                cell_content = convert_element_content(td)

                # Handle colspan/rowspan
                colspan = td.get("colspan")
                rowspan = td.get("rowspan")

                entry_attrs = []
                if colspan:
                    entry_attrs.append(f'namest="c1" nameend="c{colspan}"')
                if rowspan:
                    entry_attrs.append(f'morerows="{int(rowspan)-1}"')

                if entry_attrs:
                    dita_table.append(f'            <entry {" ".join(entry_attrs)}>{cell_content}</entry>')
                else:
                    dita_table.append(f'            <entry>{cell_content}</entry>')
            dita_table.append('          </row>')
        dita_table.append('        </tbody>')

    dita_table.append('      </tgroup>')
    dita_table.append('    </table>')
    return "\n".join(dita_table)

def md_to_dita_topic(md_path: str, topic_id: str, title: str, file_to_topic: dict = None) -> str:
    """Convert a Markdown file to a DITA topic."""
    if not os.path.exists(md_path):
        log(f"⚠️  Missing Markdown file: {md_path}")
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">
<topic id="{topic_id}">
  <title>{title}</title>
  <body>
    <p><i>Missing file: {md_path}</i></p>
  </body>
</topic>
"""

    with open(md_path, "r", encoding="utf-8") as f:
        md_content = f.read()

    # Convert Markdown to HTML first
    html = markdown.markdown(md_content, extensions=[
        "extra",
        "tables",
        "fenced_code",
        "codehilite",  # Better code block handling with language detection
        "nl2br"        # Preserve line breaks in code examples
    ])
    soup = BeautifulSoup(html, "html.parser")

    # Process internal links if we have the mapping
    if file_to_topic:
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]

            # Skip fragment-only anchors
            if href.startswith("#"):
                continue

            # Extract base path from href (handle both absolute and relative URLs)
            # Examples:
            #   /photoshop/using/blending-modes.html#new-mode → /photoshop/using/blending-modes
            #   https://helpx.adobe.com/photoshop/using/blending-modes.html#new-mode → /photoshop/using/blending-modes
            #   ../layers.html → ../layers

            base_path = href

            # If it's an absolute URL, extract the path
            if href.startswith("http://") or href.startswith("https://"):
                parsed = urlparse(href)
                # Only process URLs from the same domain (helpx.adobe.com)
                if "helpx.adobe.com" in parsed.netloc or "adobe.com" in parsed.netloc:
                    base_path = parsed.path
                else:
                    # Different domain - keep as external link
                    continue

            # Strip anchor/fragment and query parameters
            if '#' in base_path:
                base_path = base_path.split('#')[0]
            if '?' in base_path:
                base_path = base_path.split('?')[0]

            # Strip file extension (.html)
            if base_path.endswith('.html'):
                base_path = base_path[:-5]

            # Skip if path is empty after stripping
            if not base_path or base_path == '/':
                continue

            # Normalize the link path to check against our file mapping
            # Add .md extension and MD_DIR prefix for comparison
            # The file mapping uses paths like "md/photoshop/using/file.md"
            link_path = base_path + '.md'
            # Convert to format matching file_to_topic keys (e.g., "md/photoshop/using/file.md")
            if link_path.startswith('/'):
                link_path = '.' + link_path
            elif not link_path.startswith('./'):
                link_path = './' + link_path

            # Join with MD_DIR to match the format in file_to_topic
            link_path_with_dir = os.path.join(MD_DIR, link_path)
            normalized = normalize_path(link_path_with_dir)

            # Check if this file is in our DITA map
            if normalized in file_to_topic:
                target_topic = file_to_topic[normalized]
                # Mark this as an internal link for DITA conversion
                a_tag["data-dita-href"] = target_topic["filename"]
                a_tag["data-dita-scope"] = "local"
                log(f"🔗 Found internal link: {href} → {target_topic['filename']}")
            else:
                # File doesn't exist in our collection - keep as external link
                log(f"⚠️  Link to file not in collection (will remain external): {base_path}")

    # Process images - update paths to point to html directory
    for img_tag in soup.find_all("img"):
        img_src = img_tag.get("src", "")
        if img_src:
            # Skip data URIs (embedded images) - they cause issues in DITA
            if img_src.startswith("data:"):
                log(f"⏭️  Skipping data URI image (embedded content)")
                img_tag.decompose()  # Remove the image tag entirely
                continue

            # Resolve image path to point to html directory
            resolved_path = resolve_image_path(img_src, md_path)

            # If it's an external URL, skip it
            if resolved_path.startswith(("http://", "https://")):
                log(f"⏭️  Skipping external image URL: {resolved_path}")
                img_tag.decompose()
            else:
                img_tag["src"] = resolved_path

    # Start building DITA topic
    dita_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE topic PUBLIC "-//OASIS//DTD DITA Topic//EN" "topic.dtd">',
        f'<topic id="{topic_id}">',
        f'  <title>{title}</title>',
        '  <body>'
    ]

    # Convert HTML elements to DITA
    for element in soup.children:
        if element.name == "h1":
            # Skip h1 since we use title
            continue
        elif element.name in ["h2", "h3", "h4", "h5", "h6"]:
            # Convert headings to sections (simplified)
            text = element.get_text(strip=True)
            dita_parts.append(f'    <section><title>{escape_xml(text)}</title></section>')
        elif element.name == "p":
            # Handle paragraphs with potential links
            dita_parts.append('    <p>' + convert_element_content(element) + '</p>')
        elif element.name == "ul":
            dita_parts.append('    <ul>')
            for li in element.find_all("li", recursive=False):
                li_parts = convert_list_item_content(li)
                dita_parts.append('      <li>')
                dita_parts.extend(['        ' + part for part in li_parts])
                dita_parts.append('      </li>')
            dita_parts.append('    </ul>')
        elif element.name == "ol":
            dita_parts.append('    <ol>')
            for li in element.find_all("li", recursive=False):
                li_parts = convert_list_item_content(li)
                dita_parts.append('      <li>')
                dita_parts.extend(['        ' + part for part in li_parts])
                dita_parts.append('      </li>')
            dita_parts.append('    </ol>')
        elif element.name == "pre":
            # Extract code element and language class
            code_elem = element.find("code")
            if code_elem:
                # Check for language class (e.g., "language-typescript")
                classes = code_elem.get("class", [])
                language = None

                if isinstance(classes, list):
                    for cls in classes:
                        if cls.startswith("language-"):
                            language = cls.replace("language-", "")
                            break
                elif isinstance(classes, str) and classes.startswith("language-"):
                    language = classes.replace("language-", "")

                code_text = code_elem.get_text()

                # Auto-detect language if not specified
                if not language:
                    detected = detect_language(code_text)
                    if detected:
                        language = detected
                        log(f"🔍 Auto-detected language: {language}")

                # Add outputclass for syntax highlighting
                if language:
                    dita_parts.append(f'    <codeblock outputclass="language-{language}">{escape_xml(code_text)}</codeblock>')
                else:
                    dita_parts.append(f'    <codeblock>{escape_xml(code_text)}</codeblock>')
            else:
                # Fallback to pre content
                code_text = element.get_text()

                # Try auto-detection for pre blocks without code element
                detected = detect_language(code_text)
                if detected:
                    log(f"🔍 Auto-detected language: {detected}")
                    dita_parts.append(f'    <codeblock outputclass="language-{detected}">{escape_xml(code_text)}</codeblock>')
                else:
                    dita_parts.append(f'    <codeblock>{escape_xml(code_text)}</codeblock>')
        elif element.name == "table":
            dita_parts.append(convert_table_to_dita(element))
        elif element.name == "img":
            img_src = element.get("src", "")
            img_alt = element.get("alt", "")
            if img_src:
                # Block-level images are standalone figures
                # placement="break" allows the image to be full size but max 50% screen width
                dita_parts.append(f'    <image href="{escape_xml(img_src)}" placement="break" align="left">')
                if img_alt:
                    dita_parts.append(f'      <alt>{escape_xml(img_alt)}</alt>')
                dita_parts.append('    </image>')

    dita_parts.append('  </body>')
    dita_parts.append('</topic>')

    return "\n".join(dita_parts)

def convert_headings_to_lists(md_text: str) -> str:
    """Convert heading-based TOC to nested list format.

    Example input:
        # Title
        ## Section 1
        1. [Link 1](url1)
        2. [Link 2](url2)
        ### Subsection 1.1
        1. [Link 3](url3)
        ## Section 2
        1. [Link 4](url4)

    Example output:
        1. Section 1
            1. [Link 1](url1)
            2. [Link 2](url2)
            3. Subsection 1.1
                1. [Link 3](url3)
        2. Section 2
            1. [Link 4](url4)
    """
    import re
    lines = md_text.split('\n')
    output = []
    heading_stack = []  # Stack to track heading levels (actual # count)
    item_counters = {}  # Counter for each indent level

    i = 0
    while i < len(lines):
        line = lines[i]

        # Check if this is a heading
        if line.strip().startswith('#'):
            # Parse heading level
            heading_match = line.strip()
            level = 0
            while heading_match.startswith('#'):
                level += 1
                heading_match = heading_match[1:]
            heading_text = heading_match.strip()

            # Skip the main title (level 1)
            if level == 1:
                i += 1
                continue

            # Adjust for ## being level 0 in our indentation
            indent_level = level - 2

            # Pop stack if we're going back to a higher level (fewer #s)
            while heading_stack and heading_stack[-1] >= level:
                heading_stack.pop()

            # Push current level
            heading_stack.append(level)

            # Clear counters for deeper levels
            for clear_level in range(indent_level + 1, 10):
                if clear_level in item_counters:
                    del item_counters[clear_level]

            # Increment counter at current level (for tracking child items)
            item_counters[indent_level] = item_counters.get(indent_level, 0) + 1

            # Add the heading as a list item (no link)
            # Strip any leading numbers from the heading text (like "1. " or "2.1 ")
            # to avoid double-numbering issues with markdown parsing
            clean_heading = heading_text
            # Check if starts with number(s) followed by dot and space
            match = re.match(r'^[\d.]+\s+(.+)$', heading_text)
            if match:
                clean_heading = match.group(1)

            # For level 0 (##), use no indent and add numbering
            # For deeper levels (###), use proper indentation
            if indent_level == 0:
                # Top-level heading - use simple numbered list
                output.append(f"{item_counters[indent_level]}. {clean_heading}")
            else:
                # Nested heading - use 4 spaces per level (CommonMark requires 4 spaces for nesting)
                indent = '    ' * indent_level
                output.append(f"{indent}{item_counters[indent_level]}. {clean_heading}")

        elif line.strip() and not line.strip().startswith('#'):
            # This is content under a heading (likely a numbered or bullet list)
            stripped = line.strip()

            # Check if it's a numbered list item with a link
            if stripped and stripped[0].isdigit() and '. ' in stripped[:5]:
                # This is a numbered list item - extract the content after "N. "
                content = stripped.split('. ', 1)[1] if '. ' in stripped else stripped

                # Indent under the current heading
                indent_level = len(heading_stack)
                # Use 4 spaces per level (CommonMark requires 4 spaces for nesting)
                indent = '    ' * indent_level

                # Increment counter for items at this level
                item_counters[indent_level] = item_counters.get(indent_level, 0) + 1

                output.append(f"{indent}{item_counters[indent_level]}. {content}")
            elif stripped.startswith('- '):
                # This is a bullet list item - extract the content after "- "
                content = stripped[2:].strip()

                # Indent under the current heading
                indent_level = len(heading_stack)
                # Use 4 spaces per level (CommonMark requires 4 spaces for nesting)
                indent = '    ' * indent_level

                # Increment counter for items at this level
                item_counters[indent_level] = item_counters.get(indent_level, 0) + 1

                output.append(f"{indent}{item_counters[indent_level]}. {content}")

        i += 1

    return '\n'.join(output)

def parse_markdown_toc(md_file: str) -> tuple:
    """Convert toc.md to HTML and parse with BeautifulSoup.

    Supports two TOC formats:
    1. Numbered list format (indented with spaces/tabs)
    2. Heading-based format (using # ## ### for hierarchy)

    Returns: (BeautifulSoup object, extracted_title or None)
    """
    if not os.path.exists(md_file):
        raise FileNotFoundError(f"{md_file} not found")

    with open(md_file, "r", encoding="utf-8") as f:
        toc_md_text = f.read()

    # Extract title from first # heading if present
    extracted_title = None
    for line in toc_md_text.split('\n'):
        if line.strip().startswith('# '):
            extracted_title = line.strip()[2:].strip()
            log(f"📖 Extracted title from TOC: {extracted_title}")
            break

    # Detect TOC format
    has_headings = any(line.strip().startswith('#') for line in toc_md_text.split('\n'))
    has_indented_lists = any(line.startswith('  ') and (line.strip().startswith('[') or line.strip()[0].isdigit() if line.strip() else False)
                             for line in toc_md_text.split('\n'))

    if has_headings and not has_indented_lists:
        # Heading-based format - convert to nested list format
        log("📋 Detected heading-based TOC format, converting to nested lists...")
        toc_md_text = convert_headings_to_lists(toc_md_text)

    # Preprocess markdown to fix nested list parsing issues
    # The markdown library has trouble with nested lists that have blank lines
    # We need to remove blank lines within list structures
    lines = toc_md_text.split('\n')
    cleaned_lines = []

    for i, line in enumerate(lines):
        # Skip blank lines that are between indented list items
        if line.strip() == '':
            # Check if we're in the middle of a list (previous and next lines are indented)
            prev_is_list = i > 0 and lines[i-1].strip() and (lines[i-1].startswith('  ') or lines[i-1].startswith('\t'))
            next_is_list = i < len(lines)-1 and lines[i+1].strip() and (lines[i+1].startswith('  ') or lines[i+1].startswith('\t'))

            if prev_is_list and next_is_list:
                # Skip this blank line - it breaks nested list parsing
                continue

        cleaned_lines.append(line)

    cleaned_md = '\n'.join(cleaned_lines)

    toc_html = markdown.markdown(cleaned_md, extensions=["extra"])
    soup = BeautifulSoup(toc_html, "html.parser")
    return soup, extracted_title

def build_dita_map(toc_soup: BeautifulSoup, dita_dir: Path, base_path: str = "", title: str = None) -> tuple:
    """Build DITA map from TOC and generate topic files. Returns (ditamap_content, title)."""

    # Use provided title, or extract from first link in TOC, or use default
    doc_title = title
    if not doc_title:
        # Try to extract from first link
        top_ol = toc_soup.find(["ol", "ul"])
        if top_ol:
            first_li = top_ol.find("li")
            if first_li:
                first_link = first_li.find("a")
                if first_link:
                    doc_title = first_link.get_text(strip=True)

        # Final fallback
        if not doc_title:
            doc_title = "Documentation"

    log(f"📖 Document title: {doc_title}")

    # First pass: collect all files (build mapping first)
    topic_counter = [0]
    file_to_topic = {}
    files_to_process = []

    def collect_files(ol, level=1):
        for li in ol.find_all("li", recursive=False):
            link_tag = li.find("a", href=True)
            nested_ol = li.find(["ol", "ul"], recursive=False)

            if link_tag:
                title = link_tag.get_text(strip=True)
                href = link_tag["href"]

                # Skip URLs
                if href.startswith("http://") or href.startswith("https://"):
                    if nested_ol:
                        collect_files(nested_ol, level + 1)
                    continue

                # Normalize path
                if href.startswith("/"):
                    href = "." + href
                elif not href.startswith("./"):
                    href = "./" + href

                href = os.path.join(base_path, href)
                if href.endswith(".html"):
                    href = href[:-5] + ".md"

                # Build mapping
                normalized = normalize_path(href)
                if normalized not in file_to_topic:
                    topic_counter[0] += 1
                    topic_id = f"topic_{topic_counter[0]}"
                    topic_filename = f"{topic_id}.dita"

                    file_to_topic[normalized] = {
                        "id": topic_id,
                        "filename": topic_filename,
                        "title": title
                    }
                    files_to_process.append((href, topic_id, title, topic_filename))

            if nested_ol:
                collect_files(nested_ol, level + 1)

    top_ol = toc_soup.find(["ol", "ul"])
    if top_ol:
        collect_files(top_ol)

    log(f"📋 Found {len(file_to_topic)} files to convert to DITA")

    # Second pass: generate topics with link resolution
    for href, topic_id, title, topic_filename in files_to_process:
        # Convert MD to DITA with file mapping for link resolution
        dita_content = md_to_dita_topic(href, topic_id, title, file_to_topic)

        # Write DITA file
        topic_path = dita_dir / topic_filename
        with open(topic_path, "w", encoding="utf-8") as f:
            f.write(dita_content)

        log(f"✅ Generated DITA topic: {topic_filename} for {href}")

    # Third pass: build DITA map
    ditamap_parts = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE map PUBLIC "-//OASIS//DTD DITA Map//EN" "map.dtd">',
        '<map>',
        f'  <title>{escape_xml(doc_title)}</title>'
    ]

    def build_map_structure(ol, level=1, indent="  "):
        for li in ol.find_all("li", recursive=False):
            link_tag = li.find("a", href=True, recursive=False)  # Only check direct children
            nested_ol = li.find(["ol", "ul"], recursive=False)

            if link_tag:
                title = link_tag.get_text(strip=True)
                href = link_tag["href"]

                # Skip URLs
                if href.startswith("http://") or href.startswith("https://"):
                    log(f"⏭️  Skipping URL link in map: {title} ({href})")
                    if nested_ol:
                        build_map_structure(nested_ol, level + 1, indent)
                    continue

                # Normalize path
                if href.startswith("/"):
                    href = "." + href
                elif not href.startswith("./"):
                    href = "./" + href

                href = os.path.join(base_path, href)
                if href.endswith(".html"):
                    href = href[:-5] + ".md"

                normalized = normalize_path(href)
                if normalized in file_to_topic:
                    topic_info = file_to_topic[normalized]
                    if nested_ol:
                        ditamap_parts.append(f'{indent}<topicref href="{topic_info["filename"]}">')
                        build_map_structure(nested_ol, level + 1, indent + "  ")
                        ditamap_parts.append(f'{indent}</topicref>')
                    else:
                        ditamap_parts.append(f'{indent}<topicref href="{topic_info["filename"]}"/>')
            else:
                # Parent item without link - create topichead
                title_text = li.find(text=True, recursive=False)
                if title_text:
                    title_text = title_text.strip()
                    if title_text:
                        ditamap_parts.append(f'{indent}<topichead navtitle="{escape_xml(title_text)}">')
                        if nested_ol:
                            build_map_structure(nested_ol, level + 1, indent + "  ")
                        ditamap_parts.append(f'{indent}</topichead>')
                elif nested_ol:
                    build_map_structure(nested_ol, level + 1, indent)

    if top_ol:
        build_map_structure(top_ol)

    ditamap_parts.append('</map>')
    return "\n".join(ditamap_parts), doc_title

# ---------------------------------------------------------------------
def main():
    import argparse

    # Parse command line arguments
    parser = argparse.ArgumentParser(
        description='Convert Markdown files to DITA topics and generate ditamap',
        epilog='If no title is provided, the script will try to extract it from the first heading in the TOC'
    )
    parser.add_argument('--title', type=str, help='Title for the DITA map')
    args = parser.parse_args()

    # Clear old log
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    log("🚀 Starting generate-dita.py")
    log(f"📂 Reading Markdown files from: {MD_DIR}/")
    log(f"📂 DITA files will be saved to: {DITA_DIR}/")

    # Check if MD directory exists
    md_dir_path = Path(MD_DIR)
    if not md_dir_path.exists():
        log(f"❌ Error: {MD_DIR}/ directory not found. Run generate-md.py first.")
        sys.exit(1)

    # Check if toc.md exists
    toc_file = md_dir_path / TOC_MD
    if not toc_file.exists():
        log(f"❌ Error: {toc_file} not found. Run generate-md.py first.")
        sys.exit(1)

    # Parse TOC and extract title
    toc_soup, extracted_title = parse_markdown_toc(str(toc_file))

    # Determine final title (CLI arg > extracted from TOC > first link > default)
    final_title = args.title or extracted_title
    if args.title:
        log(f"📖 Using title from command line: {args.title}")
    elif extracted_title:
        log(f"📖 Using title extracted from TOC")

    # Create DITA directory
    dita_dir = Path(DITA_DIR)
    dita_dir.mkdir(parents=True, exist_ok=True)

    # Clean up old DITA files (but keep images)
    for dita_file in dita_dir.glob("*.dita"):
        dita_file.unlink()
    for ditamap_file in dita_dir.glob("*.ditamap"):
        ditamap_file.unlink()

    # Build DITA map and generate topics
    ditamap_content, doc_title = build_dita_map(toc_soup, dita_dir, base_path=str(md_dir_path), title=final_title)

    # Write DITA map
    ditamap_path = dita_dir / "userguide.ditamap"
    with open(ditamap_path, "w", encoding="utf-8") as f:
        f.write(ditamap_content)
    log(f"✅ Generated DITA map: {ditamap_path}")

    log(f"🎉 Done! Generated DITA files in {DITA_DIR}/")

if __name__ == "__main__":
    main()
