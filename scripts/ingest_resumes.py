#!/usr/bin/env python3
"""
ingest_resumes.py — Parse PDF resumes from data/ folders, extract skills via
heuristic keyword matching, then update hr_structure.json with enriched profile data.

Reads from:
  data/Resumes/Full-Time/*.pdf
  data/Resumes/Interns/*.pdf

Writes to:
  data/hr_structure.json      — skills arrays updated / new interns added
  data/resume_profiles.json   — full parsed profiles for all resumes

Usage:
  python scripts/ingest_resumes.py
  python scripts/ingest_resumes.py --dry-run        # preview without writing
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path(__file__).parent.parent
HR_FILE = REPO_ROOT / "data" / "hr_structure.json"
RESUME_PROFILES_FILE = REPO_ROOT / "data" / "resume_profiles.json"
RESUME_DIRS = [
    REPO_ROOT / "data" / "Resumes" / "Full-Time",
    REPO_ROOT / "data" / "Resumes" / "Interns",
]

# ---------------------------------------------------------------------------
# PDF text extraction (PyMuPDF)
# ---------------------------------------------------------------------------

def extract_pdf_text(pdf_path: Path) -> str:
    """Extract plain text from a PDF using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("  [WARN] PyMuPDF not installed. Trying pdfplumber...")
        return _extract_via_pdfplumber(pdf_path)

    doc = fitz.open(str(pdf_path))
    pages = []
    for page in doc:
        pages.append(page.get_text("text"))
    doc.close()
    return "\n".join(pages)


def _extract_via_pdfplumber(pdf_path: Path) -> str:
    try:
        import pdfplumber
        with pdfplumber.open(str(pdf_path)) as pdf:
            return "\n".join(
                p.extract_text() or "" for p in pdf.pages
            )
    except ImportError:
        print("  [ERROR] Neither PyMuPDF nor pdfplumber is installed.")
        print("          Run: pip install pymupdf   OR   pip install pdfplumber")
        return ""


# ---------------------------------------------------------------------------
# Heuristic skill extraction (no LLM)
# ---------------------------------------------------------------------------

# Broad skill vocabulary — extend as needed
SKILL_KEYWORDS = [
    # Programming languages
    "python", "javascript", "typescript", "c++", "c#", "java", "kotlin",
    "swift", "go", "rust", "matlab", "r", "php", "ruby", "sql", "bash",
    # Web / backend
    "react", "angular", "vue", "node.js", "django", "flask", "fastapi",
    "express", "spring", "graphql", "rest api", "html", "css",
    # Data / ML / AI
    "machine learning", "deep learning", "nlp", "computer vision",
    "tensorflow", "pytorch", "keras", "scikit-learn", "pandas", "numpy",
    "data analysis", "data science", "llm", "openai", "langchain",
    # Cloud / DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "ci/cd", "github actions",
    "terraform", "linux",
    # Mechanical / Embedded
    "cad", "solidworks", "fusion 360", "autocad", "ansys", "catia",
    "3d printing", "fdm", "sla", "mechatronics", "robotics",
    "embedded systems", "arduino", "raspberry pi", "firmware", "pcb design",
    "electronics", "fpga",
    # Business / design
    "project management", "agile", "scrum", "figma", "ui/ux",
    "graphic design", "adobe", "marketing", "seo", "content creation",
    "sales", "business development", "product management",
    # Generic engineering
    "hardware testing", "dfm", "quality control", "supply chain",
]


def extract_skills_heuristic(text: str) -> list[str]:
    """Return a deduplicated list of skills found in text via keyword matching."""
    text_lower = text.lower()
    found = []
    for kw in SKILL_KEYWORDS:
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower):
            found.append(kw)
    return found


def _heuristic_profile(text: str, filename: str) -> dict[str, Any]:
    """Build a minimal profile using regex and keyword matching."""
    # Attempt to extract name from filename (e.g. "Raja Sohal_Resume.pdf")
    stem = Path(filename).stem
    name_guess = re.sub(r"[_\-]?(resume|cv|curriculum|vitae).*$", "", stem, flags=re.IGNORECASE).strip()
    name_guess = re.sub(r"[_\-]", " ", name_guess).strip()
    # Split camelCase: "SureshNagaraj" → "Suresh Nagaraj"
    name_guess = re.sub(r"([a-z])([A-Z])", r"\1 \2", name_guess).strip()

    # Try to find email in text
    email_match = re.search(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}", text)
    email = email_match.group(0) if email_match else None

    skills = extract_skills_heuristic(text)

    return {
        "name": name_guess,
        "email": email,
        "phone": None,
        "education": [],
        "skills": skills,
        "experience_summary": "",
        "years_experience": None,
        "domain": "Unknown",
    }


# ---------------------------------------------------------------------------
# Fuzzy name matching against hr_structure.json
# ---------------------------------------------------------------------------

def normalise_name(name: str) -> str:
    return re.sub(r"\s+", " ", name).strip().lower()


def build_hr_index(hr_data: dict) -> dict[str, Any]:
    """Return a flat dict: normalised_name -> member object (with path info)."""
    index = {}
    for dept in hr_data.get("departments", []):
        for team in dept.get("teams", []):
            for member in team.get("members", []):
                key = normalise_name(member.get("name", ""))
                index[key] = {"member": member, "dept": dept["name"], "team": team["name"]}
    return index


def fuzzy_match(profile_name: str, hr_index: dict[str, Any]) -> str | None:
    """
    Return the best matching HR key for a profile name, or None.

    Rules (strongest → weakest):
    1. Exact normalised match.
    2. All meaningful tokens (len >= 3) from profile appear in HR name.
    3. First meaningful token (first name, len >= 4) matches first token of HR name.
    Single-character tokens are never used for matching to avoid false positives.
    """
    needle = normalise_name(profile_name)
    # Exact match
    if needle in hr_index:
        return needle

    meaningful = [t for t in needle.split() if len(t) >= 3]
    if not meaningful:
        return None
    meaningful_set = set(meaningful)

    # All meaningful tokens must appear in the HR key
    for key in hr_index:
        key_tokens = set(key.split())
        if meaningful_set.issubset(key_tokens):
            return key

    # First-name match: first meaningful token (len>=4) must match
    # first meaningful token of HR name, AND they share at least one more token
    first_token = meaningful[0]
    if len(first_token) >= 4:
        for key in hr_index:
            key_tokens = [t for t in key.split() if len(t) >= 3]
            if not key_tokens:
                continue
            if key_tokens[0] == first_token and len(meaningful_set & set(key_tokens)) >= 2:
                return key

    return None


# ---------------------------------------------------------------------------
# Update hr_structure.json
# ---------------------------------------------------------------------------

def upsert_member(hr_data: dict, profile: dict[str, Any], matched_key: str | None,
                  hr_index: dict[str, Any], source_file: str) -> str:
    """
    If matched_key found: merge skills and add resume_profile metadata.
    If not found: add person to an 'Interns' department.
    Returns "updated" | "added" | "skipped".
    """
    new_skills = [s.lower() for s in profile.get("skills", [])]

    if matched_key:
        entry = hr_index[matched_key]
        member = entry["member"]
        # Merge skills (deduplicate)
        existing = set(s.lower() for s in member.get("skills", []))
        merged = sorted(existing | set(new_skills))
        member["skills"] = merged
        # Store resume metadata
        member["resume_profile"] = {
            "source_file": source_file,
            "education": profile.get("education", []),
            "experience_summary": profile.get("experience_summary", ""),
            "years_experience": profile.get("years_experience"),
            "domain": profile.get("domain", ""),
        }
        if profile.get("email") and not member.get("email"):
            member["email"] = profile["email"]
        return "updated"

    # Not found — add to Interns department
    interns_dept = next(
        (d for d in hr_data["departments"] if d["name"] == "Interns"), None
    )
    if not interns_dept:
        interns_dept = {
            "name": "Interns",
            "head": "TBD",
            "teams": [{"name": "Intern Pool", "members": []}],
        }
        hr_data["departments"].append(interns_dept)

    intern_team = interns_dept["teams"][0]
    new_member = {
        "name": profile.get("name", "Unknown"),
        "email": profile.get("email"),
        "role": "Intern",
        "skills": sorted(set(new_skills)),
        "status": "active",
        "capacity_hours_per_week": 40,
        "current_load_hours_per_week": 0,
        "available_hours_per_week": 40,
        "clickup_user_id": None,
        "resume_profile": {
            "source_file": source_file,
            "education": profile.get("education", []),
            "experience_summary": profile.get("experience_summary", ""),
            "years_experience": profile.get("years_experience"),
            "domain": profile.get("domain", ""),
        },
    }
    intern_team["members"].append(new_member)
    return "added"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest resumes → update hr_structure.json")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    args = parser.parse_args()

    if args.dry_run:
        print("[DRY RUN] No files will be written.\n")

    # Load .env
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                os.environ.setdefault(k.strip(), v.strip())

    # Load HR data
    with open(HR_FILE, "r", encoding="utf-8") as f:
        hr_data = json.load(f)
    hr_index = build_hr_index(hr_data)

    # Collect all PDFs
    pdf_files: list[Path] = []
    for resume_dir in RESUME_DIRS:
        if resume_dir.exists():
            pdf_files.extend(resume_dir.glob("*.pdf"))
        else:
            print(f"[SKIP] Directory not found: {resume_dir}")

    if not pdf_files:
        print("[WARN] No PDF files found in resume directories.")
        return

    print(f"Found {len(pdf_files)} resume(s):\n")

    all_profiles: list[dict[str, Any]] = []
    stats = {"updated": 0, "added": 0, "skipped": 0}

    for pdf_path in sorted(pdf_files):
        print(f"Processing: {pdf_path.name}")

        text = extract_pdf_text(pdf_path)
        if not text.strip():
            print("  [WARN] No text extracted — skipping.\n")
            stats["skipped"] += 1
            continue

        profile = _heuristic_profile(text, pdf_path.name)

        profile["source_file"] = str(pdf_path.relative_to(REPO_ROOT))
        all_profiles.append(profile)

        matched_key = fuzzy_match(profile.get("name", ""), hr_index)
        if matched_key:
            print(f"  Matched to HR record: '{hr_index[matched_key]['member']['name']}'")
        else:
            print(f"  No HR match found for '{profile.get('name', '?')}' — will add as Intern")

        print(f"  Skills extracted ({len(profile.get('skills', []))}): {', '.join(profile.get('skills', [])[:10])}")

        if not args.dry_run:
            result = upsert_member(hr_data, profile, matched_key, hr_index, str(pdf_path.name))
            stats[result] += 1
            # Re-build index after potential additions
            hr_index = build_hr_index(hr_data)
            print(f"  → {result.upper()}\n")
        else:
            print(f"  [DRY RUN] Would {'update' if matched_key else 'add'} record.\n")

    if not args.dry_run:
        # Write updated HR data
        with open(HR_FILE, "w", encoding="utf-8") as f:
            json.dump(hr_data, f, indent=2, ensure_ascii=False)
        print(f"\nhr_structure.json updated.")

        # Write resume profiles cache
        with open(RESUME_PROFILES_FILE, "w", encoding="utf-8") as f:
            json.dump({"profiles": all_profiles}, f, indent=2, ensure_ascii=False)
        print(f"resume_profiles.json written ({len(all_profiles)} profiles).")

    print(f"\nSummary: {stats['updated']} updated | {stats['added']} added | {stats['skipped']} skipped")


if __name__ == "__main__":
    main()
