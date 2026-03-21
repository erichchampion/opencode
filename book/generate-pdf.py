#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
from pathlib import Path
from datetime import datetime

# --- CONFIGURATION ---
DITA_DIR = "dita"
OUTPUT_PDF = "Building AI Coding Assistants.pdf"
DITA_COMMAND = "dita"
LOG_FILE = "generate-pdf.log"

# ---------------------------------------------------------------------
def log(message: str):
    """Write message to stdout and append to log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{timestamp}] {message}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as logf:
        logf.write(line + "\n")

def create_pdf_customization(dita_dir: Path):
    """Create a custom PDF configuration for better TOC styling."""
    custom_dir = dita_dir / "pdf-custom"
    custom_dir.mkdir(exist_ok=True)

    cfg_dir = custom_dir / "cfg" / "fo" / "attrs"
    cfg_dir.mkdir(parents=True, exist_ok=True)

    # Create custom TOC and image attribute configuration
    toc_attrs = """<?xml version="1.0" encoding="UTF-8"?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform"
                xmlns:fo="http://www.w3.org/1999/XSL/Format"
                version="2.0">

  <!-- TOC indent for nested levels -->
  <xsl:attribute-set name="__toc__indent">
    <xsl:attribute name="start-indent">
      <xsl:variable name="level" select="count(ancestor-or-self::*[contains(@class, ' topic/topic ')])"/>
      <xsl:value-of select="concat($level * 12, 'pt')"/>
    </xsl:attribute>
  </xsl:attribute-set>

  <!-- TOC entry styling by level -->
  <xsl:attribute-set name="__toc__topic__content">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
    <xsl:attribute name="font-weight">
      <xsl:variable name="level" select="count(ancestor-or-self::*[contains(@class, ' topic/topic ')])"/>
      <xsl:choose>
        <xsl:when test="$level = 1">bold</xsl:when>
        <xsl:otherwise>normal</xsl:otherwise>
      </xsl:choose>
    </xsl:attribute>
    <xsl:attribute name="font-size">
      <xsl:variable name="level" select="count(ancestor-or-self::*[contains(@class, ' topic/topic ')])"/>
      <xsl:choose>
        <xsl:when test="$level = 1">14pt</xsl:when>
        <xsl:when test="$level = 2">12pt</xsl:when>
        <xsl:otherwise>10pt</xsl:otherwise>
      </xsl:choose>
    </xsl:attribute>
  </xsl:attribute-set>

  <!-- Global font family settings for consistency -->
  <xsl:attribute-set name="common.border__top">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <xsl:attribute-set name="common.border__bottom">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <!-- Body text -->
  <xsl:attribute-set name="body__toplevel">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <xsl:attribute-set name="topic">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <!-- Title and headings -->
  <xsl:attribute-set name="topic.title">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <xsl:attribute-set name="topic.topic.title">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <xsl:attribute-set name="section.title">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <!-- Paragraphs and text -->
  <xsl:attribute-set name="p">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <!-- Lists -->
  <xsl:attribute-set name="ul">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <xsl:attribute-set name="ol">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <!-- Tables -->
  <xsl:attribute-set name="table">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <xsl:attribute-set name="table.title">
    <xsl:attribute name="font-family">sans-serif</xsl:attribute>
  </xsl:attribute-set>

  <!-- Standalone figure images: full size, max 50% of page width -->
  <xsl:attribute-set name="image" use-attribute-sets="image__block">
  </xsl:attribute-set>

  <xsl:attribute-set name="image__block">
    <xsl:attribute name="content-width">
      <xsl:text>scale-to-fit</xsl:text>
    </xsl:attribute>
    <xsl:attribute name="content-height">
      <xsl:text>100%</xsl:text>
    </xsl:attribute>
    <xsl:attribute name="width">
      <xsl:text>100%</xsl:text>
    </xsl:attribute>
    <xsl:attribute name="max-width">
      <xsl:text>5in</xsl:text>
    </xsl:attribute>
    <xsl:attribute name="scaling">
      <xsl:text>uniform</xsl:text>
    </xsl:attribute>
  </xsl:attribute-set>

  <!-- Inline icon images: height limited to line height, preserve aspect ratio -->
  <xsl:attribute-set name="image__inline">
    <xsl:attribute name="content-height">
      <xsl:text>1em</xsl:text>
    </xsl:attribute>
    <xsl:attribute name="content-width">
      <xsl:text>scale-to-fit</xsl:text>
    </xsl:attribute>
    <xsl:attribute name="scaling">
      <xsl:text>uniform</xsl:text>
    </xsl:attribute>
    <xsl:attribute name="vertical-align">
      <xsl:text>middle</xsl:text>
    </xsl:attribute>
  </xsl:attribute-set>

  <!-- Code block syntax highlighting -->
  <xsl:attribute-set name="codeblock">
    <xsl:attribute name="font-family">monospace</xsl:attribute>
    <xsl:attribute name="font-size">9pt</xsl:attribute>
    <xsl:attribute name="background-color">#f5f5f5</xsl:attribute>
    <xsl:attribute name="padding">6pt</xsl:attribute>
    <xsl:attribute name="border">0.5pt solid #cccccc</xsl:attribute>
    <xsl:attribute name="keep-together.within-page">auto</xsl:attribute>
    <xsl:attribute name="white-space-treatment">preserve</xsl:attribute>
    <xsl:attribute name="linefeed-treatment">preserve</xsl:attribute>
    <xsl:attribute name="white-space-collapse">false</xsl:attribute>
    <xsl:attribute name="wrap-option">wrap</xsl:attribute>
  </xsl:attribute-set>

  <!-- Inline code -->
  <xsl:attribute-set name="codeph">
    <xsl:attribute name="font-family">monospace</xsl:attribute>
    <xsl:attribute name="font-size">0.9em</xsl:attribute>
    <xsl:attribute name="background-color">#f5f5f5</xsl:attribute>
    <xsl:attribute name="padding-left">2pt</xsl:attribute>
    <xsl:attribute name="padding-right">2pt</xsl:attribute>
  </xsl:attribute-set>

</xsl:stylesheet>
"""

    toc_attrs_file = cfg_dir / "toc-attr.xsl"
    with open(toc_attrs_file, "w", encoding="utf-8") as f:
        f.write(toc_attrs)

    # Create plugin configuration
    plugin_xml = """<?xml version="1.0" encoding="UTF-8"?>
<plugin id="com.custom.pdf">
  <feature extension="dita.conductor.xslt.param" file="cfg/fo/attrs/toc-attr.xsl"/>
</plugin>
"""

    plugin_file = custom_dir / "plugin.xml"
    with open(plugin_file, "w", encoding="utf-8") as f:
        f.write(plugin_xml)

    log(f"✅ Created PDF customization in {custom_dir}")
    return custom_dir

def run_dita_ot(ditamap_path: Path, output_dir: Path, output_pdf: str, dita_dir: Path):
    """Run DITA-OT to generate PDF."""
    log(f"🔨 Running DITA-OT to generate PDF...")

    # Check if DITA-OT command is available
    try:
        result = subprocess.run(
            [DITA_COMMAND, "--version"],
            capture_output=True,
            text=True,
            check=True
        )
        log(f"📦 DITA-OT version: {result.stdout.strip()}")
    except FileNotFoundError:
        log(f"❌ Error: DITA-OT command '{DITA_COMMAND}' not found.")
        log("   Please install DITA-OT and ensure 'dita' is in your PATH.")
        log("   Download: https://www.dita-ot.org/download")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        log(f"❌ Error checking DITA-OT version: {e}")
        sys.exit(1)

    # Check if pdf-theme plugin is installed
    try:
        result = subprocess.run(
            [DITA_COMMAND, "plugins"],
            capture_output=True,
            text=True,
            check=True
        )
        if "pdf-theme" not in result.stdout:
            log(f"❌ Error: pdf-theme plugin is not installed.")
            log("   Please run ./install-pdf-theme.sh to install the plugin.")
            sys.exit(1)
        log(f"✓ pdf-theme plugin is installed")
    except subprocess.CalledProcessError as e:
        log(f"❌ Error checking installed plugins: {e}")
        sys.exit(1)

    # Create custom PDF configuration
    custom_dir = create_pdf_customization(dita_dir)

    # Run DITA-OT
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        DITA_COMMAND,
        "-i", str(ditamap_path),
        "-f", "pdf-theme",
        "-o", str(output_dir),
        f"-Dargs.rellinks=none",
        f"-Dpdf.formatter=fop"
    ]

    log(f"   Command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        log(result.stdout)

        # Find the generated PDF
        pdf_files = list(output_dir.glob("*.pdf"))
        if pdf_files:
            generated_pdf = pdf_files[0]
            # Move to desired output location
            shutil.move(str(generated_pdf), output_pdf)
            log(f"✅ PDF generated: {output_pdf}")
        else:
            log(f"⚠️  PDF generated but not found in {output_dir}")

    except subprocess.CalledProcessError as e:
        log(f"❌ Error running DITA-OT:")
        log(e.stdout)
        log(e.stderr)
        sys.exit(1)

# ---------------------------------------------------------------------
def main():
    # Clear old log
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)

    log("🚀 Starting generate-pdf.py")
    log(f"📂 Reading DITA files from: {DITA_DIR}/")

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

    # Clean up old output directory
    out_dir = dita_dir / "out"
    if out_dir.exists():
        shutil.rmtree(out_dir)

    # Run DITA-OT to generate PDF
    run_dita_ot(ditamap_path, out_dir, OUTPUT_PDF, dita_dir)

    # Clean up temporary output directory (optional)
    # Uncomment the next lines if you want to remove the temp directory
    # if out_dir.exists():
    #     shutil.rmtree(out_dir)
    #     log(f"🧹 Cleaned up temporary directory: {out_dir}")

    log(f"🎉 Done! PDF saved to {OUTPUT_PDF}")

if __name__ == "__main__":
    main()
