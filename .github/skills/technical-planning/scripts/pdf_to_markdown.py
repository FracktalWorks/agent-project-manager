#!/usr/bin/env python3
"""
PDF to Markdown Converter

Converts academic PDF papers to markdown format for easy reading and processing.
Uses multiple extraction backends for robustness.

Usage:
    python pdf_to_markdown.py --input paper.pdf --output output.md
    python pdf_to_markdown.py --input ".tmp/papers/" --output ".tmp/paper_markdown/" --batch
"""

import os
import sys
import re
import argparse
from pathlib import Path
from typing import Optional, Tuple


def extract_with_pymupdf(pdf_path: Path) -> Optional[str]:
    """
    Extract text using PyMuPDF (fitz).
    Fast and handles most PDFs well.
    """
    try:
        import fitz  # PyMuPDF
        
        doc = fitz.open(pdf_path)
        pages = []
        
        for page_num, page in enumerate(doc, 1):
            text = page.get_text("text")
            if text.strip():
                pages.append(f"<!-- Page {page_num} -->\n{text}")
        
        doc.close()
        
        if pages:
            return "\n\n".join(pages)
        return None
        
    except ImportError:
        print("    PyMuPDF not installed (pip install pymupdf)")
        return None
    except Exception as e:
        print(f"    PyMuPDF extraction failed: {e}")
        return None


def extract_with_pdfplumber(pdf_path: Path) -> Optional[str]:
    """
    Extract text using pdfplumber.
    Better at preserving table structures.
    """
    try:
        import pdfplumber
        
        pages = []
        
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages, 1):
                text = page.extract_text()
                if text:
                    pages.append(f"<!-- Page {page_num} -->\n{text}")
                
                # Try to extract tables
                tables = page.extract_tables()
                for table in tables:
                    if table:
                        md_table = convert_table_to_markdown(table)
                        if md_table:
                            pages.append(md_table)
        
        if pages:
            return "\n\n".join(pages)
        return None
        
    except ImportError:
        print("    pdfplumber not installed (pip install pdfplumber)")
        return None
    except Exception as e:
        print(f"    pdfplumber extraction failed: {e}")
        return None


def extract_with_pypdf(pdf_path: Path) -> Optional[str]:
    """
    Extract text using pypdf.
    Most basic fallback.
    """
    try:
        from pypdf import PdfReader
        
        reader = PdfReader(pdf_path)
        pages = []
        
        for page_num, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text:
                pages.append(f"<!-- Page {page_num} -->\n{text}")
        
        if pages:
            return "\n\n".join(pages)
        return None
        
    except ImportError:
        print("    pypdf not installed (pip install pypdf)")
        return None
    except Exception as e:
        print(f"    pypdf extraction failed: {e}")
        return None


def extract_with_marker(pdf_path: Path) -> Optional[str]:
    """
    Extract using marker-pdf for high-quality ML-based conversion.
    Best quality but slowest.
    """
    try:
        from marker.convert import convert_single_pdf
        from marker.models import load_all_models
        
        models = load_all_models()
        full_text, images, out_meta = convert_single_pdf(str(pdf_path), models)
        
        return full_text if full_text else None
        
    except ImportError:
        # marker-pdf is optional and heavy
        return None
    except Exception as e:
        print(f"    marker extraction failed: {e}")
        return None


def convert_table_to_markdown(table: list) -> str:
    """Convert a table (list of lists) to markdown format."""
    if not table or not table[0]:
        return ""
    
    # Clean cells
    clean_table = []
    for row in table:
        clean_row = [str(cell).strip().replace("|", "\\|") if cell else "" for cell in row]
        clean_table.append(clean_row)
    
    # Build markdown table
    lines = []
    
    # Header row
    header = clean_table[0]
    lines.append("| " + " | ".join(header) + " |")
    lines.append("|" + "|".join(["---"] * len(header)) + "|")
    
    # Data rows
    for row in clean_table[1:]:
        # Pad row if needed
        while len(row) < len(header):
            row.append("")
        lines.append("| " + " | ".join(row[:len(header)]) + " |")
    
    return "\n".join(lines)


def clean_academic_text(text: str) -> str:
    """
    Clean and structure extracted text for readability.
    """
    # Remove excessive whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)
    
    # Fix common OCR/extraction issues
    text = text.replace('ﬁ', 'fi')
    text = text.replace('ﬂ', 'fl')
    text = text.replace('ﬀ', 'ff')
    
    # Try to identify section headers (ALL CAPS or numbered sections)
    lines = text.split('\n')
    processed_lines = []
    
    for line in lines:
        stripped = line.strip()
        
        # Skip empty lines
        if not stripped:
            processed_lines.append('')
            continue
        
        # Detect section headers
        # Pattern 1: ALL CAPS (likely header)
        if len(stripped) > 3 and len(stripped) < 100 and stripped.isupper():
            processed_lines.append(f"\n## {stripped.title()}\n")
            continue
        
        # Pattern 2: Numbered section (1., 1.1, etc.)
        if re.match(r'^\d+\.?\d*\s+[A-Z]', stripped):
            processed_lines.append(f"\n### {stripped}\n")
            continue
        
        # Pattern 3: Roman numeral sections
        if re.match(r'^[IVX]+\.\s+', stripped):
            processed_lines.append(f"\n## {stripped}\n")
            continue
        
        processed_lines.append(stripped)
    
    return '\n'.join(processed_lines)


def extract_metadata(text: str) -> dict:
    """
    Try to extract paper metadata from the text.
    """
    metadata = {}
    
    # Try to find title (usually first non-empty line, often larger)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if lines:
        # Title is usually in first few lines, before "Abstract"
        for i, line in enumerate(lines[:10]):
            if line.lower() == 'abstract':
                break
            if len(line) > 10 and not line.startswith('<!--'):
                metadata['title'] = line
                break
    
    # Try to find abstract
    abstract_match = re.search(
        r'(?:Abstract|ABSTRACT)[:\s]*(.+?)(?=\n\n|\n[A-Z][a-z]|\n\d+\.?\s|Introduction|INTRODUCTION|Keywords|1\s+)',
        text,
        re.DOTALL | re.IGNORECASE
    )
    if abstract_match:
        abstract = abstract_match.group(1).strip()
        # Clean up abstract
        abstract = re.sub(r'\s+', ' ', abstract)
        metadata['abstract'] = abstract[:1500]  # Limit length
    
    # Try to find DOI
    doi_match = re.search(r'10\.\d{4,}/[^\s]+', text)
    if doi_match:
        metadata['doi'] = doi_match.group(0).rstrip('.,;)')
    
    return metadata


def pdf_to_markdown(pdf_path: Path, output_path: Optional[Path] = None) -> Tuple[bool, str]:
    """
    Convert a PDF to markdown using multiple backends.
    Returns (success, content_or_error).
    """
    if not pdf_path.exists():
        return False, f"File not found: {pdf_path}"
    
    print(f"Converting: {pdf_path.name}")
    
    # Try extraction methods in order of preference
    text = None
    
    # Try marker first if available (best quality)
    text = extract_with_marker(pdf_path)
    if text:
        print("    Used: marker-pdf (ML-based)")
    
    # Try PyMuPDF (good balance of speed and quality)
    if not text:
        text = extract_with_pymupdf(pdf_path)
        if text:
            print("    Used: PyMuPDF")
    
    # Try pdfplumber (better for tables)
    if not text:
        text = extract_with_pdfplumber(pdf_path)
        if text:
            print("    Used: pdfplumber")
    
    # Try pypdf as last resort
    if not text:
        text = extract_with_pypdf(pdf_path)
        if text:
            print("    Used: pypdf")
    
    if not text:
        return False, "All extraction methods failed"
    
    # Clean and structure the text
    clean_text = clean_academic_text(text)
    
    # Extract metadata
    metadata = extract_metadata(clean_text)
    
    # Build final markdown
    md_content = []
    
    # Add header with metadata
    md_content.append(f"# {metadata.get('title', pdf_path.stem)}\n")
    
    if metadata.get('doi'):
        md_content.append(f"**DOI:** [{metadata['doi']}](https://doi.org/{metadata['doi']})\n")
    
    md_content.append(f"**Source:** {pdf_path.name}\n")
    
    if metadata.get('abstract'):
        md_content.append(f"\n## Abstract\n\n{metadata['abstract']}\n")
    
    md_content.append("\n---\n")
    md_content.append(clean_text)
    
    final_content = "\n".join(md_content)
    
    # Save if output path specified
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(final_content)
        print(f"    Saved: {output_path}")
    
    return True, final_content


def batch_convert(input_dir: Path, output_dir: Path) -> dict:
    """
    Convert all PDFs in a directory.
    """
    results = {"success": 0, "failed": 0, "files": []}
    
    pdf_files = list(input_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"No PDF files found in {input_dir}")
        return results
    
    print(f"Found {len(pdf_files)} PDF files")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    for pdf_path in pdf_files:
        output_path = output_dir / f"{pdf_path.stem}.md"
        success, result = pdf_to_markdown(pdf_path, output_path)
        
        if success:
            results["success"] += 1
            results["files"].append({"file": pdf_path.name, "status": "success"})
        else:
            results["failed"] += 1
            results["files"].append({"file": pdf_path.name, "status": "failed", "error": result})
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Convert PDF papers to markdown")
    parser.add_argument("--input", required=True, help="Input PDF file or directory")
    parser.add_argument("--output", help="Output markdown file or directory")
    parser.add_argument("--batch", action="store_true", help="Process all PDFs in input directory")
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    
    if args.batch:
        output_dir = Path(args.output) if args.output else input_path / "markdown"
        results = batch_convert(input_path, output_dir)
        print(f"\nBatch conversion complete:")
        print(f"  Success: {results['success']}")
        print(f"  Failed: {results['failed']}")
    else:
        output_path = Path(args.output) if args.output else input_path.with_suffix(".md")
        success, result = pdf_to_markdown(input_path, output_path)
        
        if success:
            print(f"\nConversion successful!")
            print(f"Output: {output_path}")
        else:
            print(f"\nConversion failed: {result}")
            sys.exit(1)


if __name__ == "__main__":
    main()
