#!/usr/bin/env python3
"""
Paper Fetcher

Downloads academic papers from open access sources.
Attempts: Unpaywall, arXiv, PubMed Central, CORE, direct publisher links.

Usage:
    python fetch_paper.py --doi "10.1234/example" --output ".tmp/papers/"
    python fetch_paper.py --arxiv "2301.00001" --output ".tmp/papers/"
    python fetch_paper.py --json ".tmp/discovered_papers.json" --output ".tmp/papers/"
"""

import os
import sys
import json
import time
import argparse
from pathlib import Path
from urllib.parse import quote_plus, urlparse

# Ensure .tmp/scripts/ is importable (for load_env)
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".tmp" / "scripts"))
from load_env import load_env; load_env()

import requests

# Configuration
USER_AGENT = "ResearchAgent/1.0 (Academic Research; mailto:research@example.com)"
TIMEOUT = 60


def sanitize_filename(s: str, max_length: int = 100) -> str:
    """Create a safe filename from a string."""
    # Remove or replace problematic characters
    safe = "".join(c if c.isalnum() or c in "._- " else "_" for c in s)
    safe = "_".join(safe.split())  # Normalize whitespace
    return safe[:max_length]


def fetch_from_unpaywall(doi: str, output_dir: Path) -> dict:
    """
    Try to get paper from Unpaywall (free open access lookup).
    """
    email = os.getenv("UNPAYWALL_EMAIL", "research@example.com")
    url = f"https://api.unpaywall.org/v2/{quote_plus(doi)}?email={email}"
    
    try:
        response = requests.get(url, timeout=30, headers={"User-Agent": USER_AGENT})
        
        if response.status_code == 404:
            return {"status": "not_found", "message": "DOI not found in Unpaywall"}
        
        response.raise_for_status()
        data = response.json()
        
        # Check for open access version
        if data.get("is_oa"):
            oa_location = data.get("best_oa_location", {})
            pdf_url = oa_location.get("url_for_pdf") or oa_location.get("url")
            
            if pdf_url:
                # Download the PDF
                pdf_response = requests.get(
                    pdf_url, 
                    timeout=TIMEOUT, 
                    headers={"User-Agent": USER_AGENT},
                    allow_redirects=True
                )
                
                if pdf_response.status_code == 200:
                    content_type = pdf_response.headers.get("content-type", "")
                    
                    if "pdf" in content_type or pdf_url.endswith(".pdf"):
                        filename = sanitize_filename(doi.replace("/", "_")) + ".pdf"
                        output_path = output_dir / filename
                        output_dir.mkdir(parents=True, exist_ok=True)
                        
                        with open(output_path, "wb") as f:
                            f.write(pdf_response.content)
                        
                        return {
                            "status": "success",
                            "source": "unpaywall",
                            "path": str(output_path),
                            "oa_status": oa_location.get("license", "unknown")
                        }
                    else:
                        return {
                            "status": "html_only",
                            "message": "Only HTML version available",
                            "url": pdf_url
                        }
        
        return {"status": "paywalled", "message": "Paper is behind paywall"}
        
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}


def fetch_from_arxiv(arxiv_id: str, output_dir: Path) -> dict:
    """
    Download paper from arXiv.
    """
    # Clean up arxiv ID (remove version if present for consistent naming)
    clean_id = arxiv_id.split("v")[0]
    
    pdf_url = f"https://arxiv.org/pdf/{clean_id}.pdf"
    
    try:
        response = requests.get(
            pdf_url, 
            timeout=TIMEOUT, 
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True
        )
        
        if response.status_code == 200:
            filename = f"arxiv_{clean_id.replace('/', '_')}.pdf"
            output_path = output_dir / filename
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(response.content)
            
            return {
                "status": "success",
                "source": "arxiv",
                "path": str(output_path)
            }
        else:
            return {"status": "not_found", "message": f"arXiv returned {response.status_code}"}
            
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}


def fetch_from_pmc(doi: str, output_dir: Path) -> dict:
    """
    Try to get paper from PubMed Central.
    """
    # First, find PMC ID from DOI
    lookup_url = f"https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={quote_plus(doi)}&format=json"
    
    try:
        response = requests.get(lookup_url, timeout=30, headers={"User-Agent": USER_AGENT})
        response.raise_for_status()
        data = response.json()
        
        records = data.get("records", [])
        if not records:
            return {"status": "not_found", "message": "Not in PubMed Central"}
        
        pmc_id = records[0].get("pmcid")
        if not pmc_id:
            return {"status": "not_found", "message": "No PMC ID found"}
        
        # Download PDF from PMC
        pdf_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/pdf/"
        
        pdf_response = requests.get(
            pdf_url, 
            timeout=TIMEOUT, 
            headers={"User-Agent": USER_AGENT},
            allow_redirects=True
        )
        
        if pdf_response.status_code == 200 and "pdf" in pdf_response.headers.get("content-type", ""):
            filename = sanitize_filename(doi.replace("/", "_")) + ".pdf"
            output_path = output_dir / filename
            output_dir.mkdir(parents=True, exist_ok=True)
            
            with open(output_path, "wb") as f:
                f.write(pdf_response.content)
            
            return {
                "status": "success",
                "source": "pmc",
                "path": str(output_path),
                "pmc_id": pmc_id
            }
        
        return {"status": "not_available", "message": "PDF not available on PMC"}
        
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}


def fetch_from_core(doi: str, output_dir: Path) -> dict:
    """
    Try to get paper from CORE (aggregator of open access research).
    """
    api_key = os.getenv("CORE_API_KEY")
    if not api_key:
        return {"status": "skipped", "message": "CORE_API_KEY not set"}
    
    search_url = f"https://api.core.ac.uk/v3/search/works/?q=doi:{quote_plus(doi)}"
    
    try:
        response = requests.get(
            search_url, 
            timeout=30, 
            headers={
                "User-Agent": USER_AGENT,
                "Authorization": f"Bearer {api_key}"
            }
        )
        response.raise_for_status()
        data = response.json()
        
        results = data.get("results", [])
        if not results:
            return {"status": "not_found", "message": "Not found in CORE"}
        
        # Look for downloadable PDF
        for result in results:
            download_url = result.get("downloadUrl")
            if download_url and download_url.endswith(".pdf"):
                pdf_response = requests.get(
                    download_url, 
                    timeout=TIMEOUT, 
                    headers={"User-Agent": USER_AGENT}
                )
                
                if pdf_response.status_code == 200:
                    filename = sanitize_filename(doi.replace("/", "_")) + ".pdf"
                    output_path = output_dir / filename
                    output_dir.mkdir(parents=True, exist_ok=True)
                    
                    with open(output_path, "wb") as f:
                        f.write(pdf_response.content)
                    
                    return {
                        "status": "success",
                        "source": "core",
                        "path": str(output_path)
                    }
        
        return {"status": "not_available", "message": "No PDF available in CORE"}
        
    except requests.exceptions.RequestException as e:
        return {"status": "error", "message": str(e)}


def fetch_paper(doi: str = None, arxiv_id: str = None, output_dir: Path = None) -> dict:
    """
    Attempt to fetch a paper using all available methods.
    """
    output_dir = output_dir or Path(".tmp/papers")
    
    result = {
        "doi": doi,
        "arxiv_id": arxiv_id,
        "status": "not_found",
        "attempts": []
    }
    
    # If we have an arXiv ID, try that first (always open access)
    if arxiv_id:
        print(f"  Trying arXiv: {arxiv_id}")
        attempt = fetch_from_arxiv(arxiv_id, output_dir)
        result["attempts"].append({"source": "arxiv", **attempt})
        
        if attempt["status"] == "success":
            result["status"] = "success"
            result["path"] = attempt["path"]
            result["source"] = "arxiv"
            return result
    
    if doi:
        # Try Unpaywall
        print(f"  Trying Unpaywall: {doi}")
        attempt = fetch_from_unpaywall(doi, output_dir)
        result["attempts"].append({"source": "unpaywall", **attempt})
        
        if attempt["status"] == "success":
            result["status"] = "success"
            result["path"] = attempt["path"]
            result["source"] = "unpaywall"
            return result
        
        # Try PubMed Central
        time.sleep(0.5)  # Be polite
        print(f"  Trying PubMed Central: {doi}")
        attempt = fetch_from_pmc(doi, output_dir)
        result["attempts"].append({"source": "pmc", **attempt})
        
        if attempt["status"] == "success":
            result["status"] = "success"
            result["path"] = attempt["path"]
            result["source"] = "pmc"
            return result
        
        # Try CORE
        time.sleep(0.5)
        print(f"  Trying CORE: {doi}")
        attempt = fetch_from_core(doi, output_dir)
        result["attempts"].append({"source": "core", **attempt})
        
        if attempt["status"] == "success":
            result["status"] = "success"
            result["path"] = attempt["path"]
            result["source"] = "core"
            return result
    
    # If all failed, check if it's paywalled
    for attempt in result["attempts"]:
        if attempt.get("status") == "paywalled":
            result["status"] = "paywalled"
            break
    
    return result


def fetch_from_json(json_path: Path, output_dir: Path, max_papers: int = None) -> dict:
    """
    Fetch papers from a discovered_papers.json file.
    """
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    papers = data.get("papers", [])
    if max_papers:
        papers = papers[:max_papers]
    
    results = {
        "total": len(papers),
        "fetched": 0,
        "paywalled": 0,
        "failed": 0,
        "papers": []
    }
    
    paywalled_papers = []
    
    for i, paper in enumerate(papers, 1):
        print(f"\n[{i}/{len(papers)}] {paper.get('title', 'Unknown')[:60]}...")
        
        result = fetch_paper(
            doi=paper.get("doi"),
            arxiv_id=paper.get("arxiv_id"),
            output_dir=output_dir
        )
        
        result["title"] = paper.get("title")
        result["authors"] = paper.get("authors", [])
        result["year"] = paper.get("year")
        results["papers"].append(result)
        
        if result["status"] == "success":
            results["fetched"] += 1
            print(f"  ✓ Downloaded from {result.get('source')}")
        elif result["status"] == "paywalled":
            results["paywalled"] += 1
            paywalled_papers.append(paper)
            print(f"  ⚠ Paywalled")
        else:
            results["failed"] += 1
            print(f"  ✗ Not available")
        
        # Rate limiting
        time.sleep(1)
    
    # Report paywalled papers
    if paywalled_papers:
        print("\n" + "=" * 60)
        print("PAYWALLED PAPERS - User action required")
        print("=" * 60)
        print("\nThe following papers are behind paywalls.")
        print("Please download them manually and place in:")
        print(f"  {output_dir.parent / 'user_papers'}\n")
        
        for paper in paywalled_papers:
            print(f"Title: {paper.get('title')}")
            print(f"DOI: {paper.get('doi')}")
            if paper.get("url"):
                print(f"URL: {paper.get('url')}")
            print()
        
        # Save paywalled list
        paywalled_path = output_dir.parent / "paywalled_papers.json"
        with open(paywalled_path, "w", encoding="utf-8") as f:
            json.dump(paywalled_papers, f, indent=2)
        print(f"List saved to: {paywalled_path}")
    
    return results


def main():
    parser = argparse.ArgumentParser(description="Fetch academic papers from open access sources")
    parser.add_argument("--doi", help="DOI of the paper to fetch")
    parser.add_argument("--arxiv", help="arXiv ID of the paper to fetch")
    parser.add_argument("--json", help="Path to discovered_papers.json for batch fetching")
    parser.add_argument("--output", default=".tmp/papers/", help="Output directory for PDFs")
    parser.add_argument("--max", type=int, help="Maximum papers to fetch (batch mode)")
    
    args = parser.parse_args()
    
    output_dir = Path(args.output)
    
    if args.json:
        print(f"Batch fetching from: {args.json}")
        results = fetch_from_json(Path(args.json), output_dir, args.max)
        
        print("\n" + "=" * 60)
        print("FETCH SUMMARY")
        print("=" * 60)
        print(f"Total papers: {results['total']}")
        print(f"Successfully fetched: {results['fetched']}")
        print(f"Paywalled: {results['paywalled']}")
        print(f"Failed/Not found: {results['failed']}")
        
        # Save results
        results_path = output_dir.parent / "fetch_results.json"
        with open(results_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        print(f"\nDetailed results saved to: {results_path}")
        
    elif args.doi or args.arxiv:
        print(f"Fetching paper...")
        result = fetch_paper(doi=args.doi, arxiv_id=args.arxiv, output_dir=output_dir)
        
        if result["status"] == "success":
            print(f"\n✓ Downloaded: {result['path']}")
        elif result["status"] == "paywalled":
            print(f"\n⚠ Paper is behind a paywall")
            print(f"DOI: {args.doi}")
            print("\nPlease download manually and place in .tmp/user_papers/")
        else:
            print(f"\n✗ Could not fetch paper")
            for attempt in result.get("attempts", []):
                print(f"  {attempt.get('source')}: {attempt.get('message', attempt.get('status'))}")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
