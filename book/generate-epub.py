#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
import yaml
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION ---
DITA_DIR = "dita"
HTML_OUTPUT_DIR = "dita/out-html5"
OUTPUT_EPUB = "Building AI Coding Assistants.epub"
METADATA_FILE = "epub-metadata.yaml"  # Customizable metadata file
DITA_COMMAND = "dita"
EBOOK_CONVERT_COMMAND = "/Applications/calibre.app/Contents/MacOS/ebook-convert"
LOG_FILE = "generate-epub.log"
PRISM_THEME = "solarized"  # Options: default, solarized, bootstrap

# ---------------------------------------------------------------------
def log(message: str):
    """Write message to stdout and append to log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        logf.write(line + "\n")

def check_command(command: str, install_instructions: str = None) -> bool:
    """Check if a command is available."""
    try:
        result = subprocess.run(
            [command, "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        version_output = result.stdout.split('\n')[0]
        log(f"✓ {command} found: {version_output}")
        return True
    except (FileNotFoundError, subprocess.CalledProcessError):
        log(f"❌ Error: '{command}' command not found")
        if install_instructions:
            log(f"   {install_instructions}")
        return False

def generate_html5(ditamap_path: Path, output_dir: Path) -> bool:
    """Generate HTML5 output with Prism.js syntax highlighting."""
    log("🔨 Generating HTML5 with syntax highlighting...")

    # Check if Prism.js plugin is installed
    try:
        result = subprocess.run(
            [DITA_COMMAND, "plugins"],
            capture_output=True,
            text=True,
            check=True
        )
        if "fox.jason.prismjs" in result.stdout:
            log(f"✓ Prism.js syntax highlighting plugin is installed")
            has_prismjs = True
        else:
            log(f"⚠️  Warning: Prism.js plugin not installed - code blocks will not have syntax highlighting")
            log("   Install with: dita install https://github.com/jason-fox/fox.jason.prismjs/archive/master.zip")
            has_prismjs = False
    except subprocess.CalledProcessError as e:
        log(f"❌ Error checking installed plugins: {e}")
        return False

    # Clean old output
    if output_dir.exists():
        shutil.rmtree(output_dir)
        log(f"🧹 Cleaned old HTML output: {output_dir}")

    # Build DITA-OT command
    cmd = [
        DITA_COMMAND,
        "--input", str(ditamap_path),
        "--format", "html5",
        "--output", str(output_dir)
    ]

    # Add Prism.js theme if plugin is available
    if has_prismjs:
        cmd.append(f"-Dprism.use.theme={PRISM_THEME}")
        log(f"🎨 Using Prism.js theme: {PRISM_THEME}")

    log(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Check for warnings
        if "Warning" in result.stdout:
            for line in result.stdout.split('\n'):
                if "Warning" in line:
                    log(line)

        log(f"✅ HTML5 generated successfully")
        return True

    except subprocess.CalledProcessError as e:
        log(f"❌ Error generating HTML5:")
        log(e.stdout)
        log(e.stderr)
        return False

def load_metadata(metadata_file: Path) -> dict:
    """Load EPUB metadata from yaml file."""
    log("📝 Loading EPUB metadata...")

    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = yaml.safe_load(f)

        # Validate required fields
        required_fields = ['title', 'language']
        for field in required_fields:
            if field not in metadata or not metadata[field]:
                log(f"❌ Error: Required field '{field}' missing in {metadata_file}")
                return None

        log(f"✅ Metadata loaded: {metadata['title']}")
        if metadata.get('author'):
            log(f"   Author: {metadata['author']}")

        return metadata
    except FileNotFoundError:
        log(f"❌ Error: Metadata file not found: {metadata_file}")
        log(f"   Please ensure {METADATA_FILE} exists in the book directory")
        return None
    except yaml.YAMLError as e:
        log(f"❌ Error parsing metadata YAML: {e}")
        return None
    except Exception as e:
        log(f"❌ Error loading metadata: {e}")
        return None

def collect_html_files(html_dir: Path) -> list:
    """Collect HTML files in order."""
    log("📚 Collecting HTML files...")

    # Collect all topic files (topic_1.html, topic_2.html, etc.)
    # These contain the actual content with syntax highlighting
    topic_files = sorted(
        html_dir.glob("topic_*.html"),
        key=lambda x: int(x.stem.split('_')[1]) if '_' in x.stem and x.stem.split('_')[1].isdigit() else 0
    )

    if topic_files:
        log(f"✓ Found {len(topic_files)} topic files with content")
        # Optional: include index.html as the first "chapter" if it has content
        index_file = html_dir / "index.html"
        if index_file.exists():
            # Check if index has meaningful content (more than just navigation)
            try:
                with open(index_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if '<p>' in content or '<h1>' in content:  # Has actual content
                        topic_files.insert(0, index_file)
                        log(f"✓ Including index.html as introduction")
            except:
                pass

        return topic_files
    else:
        # Fallback: just use index.html if no topic files
        index_file = html_dir / "index.html"
        if index_file.exists():
            log(f"⚠️  Only found index.html (may not have full content)")
            return [index_file]
        else:
            log(f"❌ No HTML files found in {html_dir}")
            return []

def convert_to_epub(metadata: dict, html_files: list, output_epub: str, html_dir: Path) -> bool:
    """Convert HTML files to EPUB using Calibre's ebook-convert."""
    log("📖 Converting to EPUB with Calibre...")

    # Use index.html as the main input file
    # Calibre will follow links to other HTML files automatically
    input_html = html_dir / "index.html"
    if not input_html.exists():
        # Fallback to first topic file if index doesn't exist
        if html_files:
            input_html = html_files[0]
        else:
            log(f"❌ No input HTML file found")
            return False

    # Build ebook-convert command
    cmd = [
        EBOOK_CONVERT_COMMAND,
        str(input_html),
        output_epub
    ]

    # Add metadata arguments
    if metadata.get('title'):
        title = metadata['title']
        if metadata.get('subtitle'):
            title = f"{title}: {metadata['subtitle']}"
        cmd.extend(["--title", title])
        log(f"   Title: {title}")

    if metadata.get('author'):
        # Handle both single author string and list of authors
        authors = metadata['author']
        if isinstance(authors, list):
            authors = ' & '.join(authors)
        cmd.extend(["--authors", authors])
        log(f"   Author(s): {authors}")

    if metadata.get('language'):
        cmd.extend(["--language", metadata['language']])

    if metadata.get('publisher'):
        cmd.extend(["--publisher", metadata['publisher']])

    if metadata.get('description'):
        cmd.extend(["--comments", metadata['description']])

    if metadata.get('isbn'):
        cmd.extend(["--isbn", metadata['isbn']])

    if metadata.get('rights'):
        cmd.extend(["--book-producer", metadata['rights']])

    if metadata.get('series'):
        cmd.extend(["--series", metadata['series']])
        if metadata.get('series-number'):
            cmd.extend(["--series-index", str(metadata['series-number'])])

    # Add cover image if specified and exists
    if metadata.get('cover-image'):
        cover_path = Path(metadata['cover-image'])
        if not cover_path.is_absolute():
            # Resolve relative to metadata file location
            cover_path = Path(METADATA_FILE).parent / cover_path
        if cover_path.exists():
            cmd.extend(["--cover", str(cover_path)])
            log(f"   Cover image: {cover_path}")
        else:
            log(f"⚠️  Warning: Cover image not found: {cover_path}")

    # EPUB-specific options
    cmd.extend([
        "--no-default-epub-cover",  # Don't generate a default cover
        "--preserve-cover-aspect-ratio",  # Keep cover proportions
        "--chapter", "//h:h1",  # Use h1 tags as chapter breaks
        "--chapter-mark", "pagebreak",  # Start chapters on new pages
        "--insert-blank-line",  # Improve readability
        "--max-toc-links", "0",  # Include all headings in TOC
    ])

    log(f"   Converting {input_html.name} to EPUB...")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        if os.path.exists(output_epub):
            file_size = os.path.getsize(output_epub) / 1024  # KB
            log(f"✅ EPUB generated: {output_epub} ({file_size:.1f} KB)")
            return True
        else:
            log(f"❌ EPUB file not created")
            return False

    except subprocess.CalledProcessError as e:
        log(f"❌ Error converting to EPUB:")
        if e.stdout:
            log(e.stdout)
        if e.stderr:
            log(e.stderr)
        return False

# ---------------------------------------------------------------------
def main():
    # Clear old log
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    log("🚀 Starting generate-epub.py (Calibre version)")
    log(f"📂 Reading DITA files from: {DITA_DIR}/")

    # Check prerequisites
    if not check_command(DITA_COMMAND, "Install from: https://www.dita-ot.org/download"):
        sys.exit(1)

    # Check for Calibre's ebook-convert
    if not os.path.exists(EBOOK_CONVERT_COMMAND):
        log(f"❌ Error: Calibre's ebook-convert not found at: {EBOOK_CONVERT_COMMAND}")
        log("   Install Calibre from: https://calibre-ebook.com/download")
        sys.exit(1)
    else:
        log(f"✓ ebook-convert found: {EBOOK_CONVERT_COMMAND}")

    # Check if DITA directory exists
    dita_dir = Path(DITA_DIR)
    if not dita_dir.exists():
        log(f"❌ Error: {DITA_DIR}/ directory not found. Run generate-dita.py first.")
        sys.exit(1)

    # Check if ditamap exists
    ditamap_path = dita_dir / "userguide.ditamap"
    if not ditamap_path.exists():
        log(f"❌ Error: {ditamap_path} not found. Run generate-dita.py first.")
        sys.exit(1)

    # Step 1: Load EPUB metadata
    metadata_file = Path(METADATA_FILE)
    metadata = load_metadata(metadata_file)
    if not metadata:
        log(f"❌ Failed to load metadata")
        sys.exit(1)

    # Step 2: Generate HTML5 with syntax highlighting
    html_output_dir = Path(HTML_OUTPUT_DIR)
    if not generate_html5(ditamap_path, html_output_dir):
        log(f"❌ Failed to generate HTML5")
        sys.exit(1)

    # Step 3: Collect HTML files
    html_files = collect_html_files(html_output_dir)
    if not html_files:
        log(f"❌ No HTML files to convert")
        sys.exit(1)

    # Step 4: Convert to EPUB using Calibre
    if not convert_to_epub(metadata, html_files, OUTPUT_EPUB, html_output_dir):
        log(f"❌ Failed to create EPUB")
        sys.exit(1)

    log(f"🎉 Done! EPUB saved to {OUTPUT_EPUB}")
    log("")
    log("📖 To view the EPUB:")
    log("   • macOS: open 'Building AI Coding Assistants.epub'")
    log("   • Linux: ebook-viewer 'Building AI Coding Assistants.epub'")
    log("   • Windows: Open with Calibre or Edge browser")
    log("")
    log("✨ Syntax highlighting may be better preserved with Calibre!")
    log(f"   To customize metadata, edit: {METADATA_FILE}")

if __name__ == "__main__":
    main()
