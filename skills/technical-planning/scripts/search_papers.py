#!/usr/bin/env python3
"""
Academic Paper Search Tool

Searches multiple academic databases for research papers.
Supports: Semantic Scholar, CrossRef, arXiv, Google Scholar (via SerpAPI)

Usage:
    python search_papers.py --topic "machine learning" --source semantic_scholar --limit 20
    python search_papers.py --topic "neural networks" --source all --limit 50 --years 2020-2024
"""

import os
import sys
import json
import time
import argparse
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

import requests
from dotenv import load_dotenv

load_dotenv()

# Rate limiting settings
RATE_LIMITS = {
    "semantic_scholar": {"requests": 100, "period": 300, "delay": 0.5},
    "crossref": {"requests": 50, "period": 60, "delay": 1.0},
    "arxiv": {"requests": 1, "period": 3, "delay": 3.0},
    "google_scholar": {"requests": 100, "period": 3600, "delay": 2.0},
}

# Cache directory
CACHE_DIR = Path(".tmp/search_cache")


def get_cache_path(query: str, source: str) -> Path:
    """Generate cache file path for a query."""
    hash_str = hashlib.md5(f"{source}:{query}".encode()).hexdigest()[:12]
    return CACHE_DIR / f"{source}_{hash_str}.json"


def load_cache(cache_path: Path, max_age_hours: int = 24) -> Optional[dict]:
    """Load cached results if fresh enough."""
    if not cache_path.exists():
        return None
    
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        cached_time = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        age_hours = (datetime.now() - cached_time).total_seconds() / 3600
        
        if age_hours < max_age_hours:
            return data.get("results", [])
    except Exception:
        pass
    
    return None


def save_cache(cache_path: Path, results: list) -> None:
    """Save results to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump({
            "cached_at": datetime.now().isoformat(),
            "results": results
        }, f, indent=2)


def search_semantic_scholar(topic: str, limit: int = 50, year_range: Optional[tuple] = None) -> list:
    """
    Search Semantic Scholar API.
    Free tier: 100 requests per 5 minutes.
    """
    print(f"  Searching Semantic Scholar for: {topic}")
    
    # Check cache
    cache_path = get_cache_path(topic, "semantic_scholar")
    cached = load_cache(cache_path)
    if cached:
        print(f"    Using cached results ({len(cached)} papers)")
        return cached[:limit]
    
    base_url = "https://api.semanticscholar.org/graph/v1/paper/search"
    
    params = {
        "query": topic,
        "limit": min(limit, 100),  # API max is 100
        "fields": "paperId,title,authors,year,citationCount,abstract,externalIds,url,venue,publicationDate"
    }
    
    if year_range:
        params["year"] = f"{year_range[0]}-{year_range[1]}"
    
    headers = {"Accept": "application/json"}
    
    # Check for API key
    api_key = os.getenv("SEMANTIC_SCHOLAR_API_KEY")
    if api_key:
        headers["x-api-key"] = api_key
    
    papers = []
    offset = 0
    
    while len(papers) < limit:
        params["offset"] = offset
        
        try:
            time.sleep(RATE_LIMITS["semantic_scholar"]["delay"])
            response = requests.get(base_url, params=params, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            batch = data.get("data", [])
            if not batch:
                break
            
            for paper in batch:
                doi = paper.get("externalIds", {}).get("DOI")
                arxiv_id = paper.get("externalIds", {}).get("ArXiv")
                
                papers.append({
                    "source": "semantic_scholar",
                    "id": paper.get("paperId"),
                    "title": paper.get("title"),
                    "authors": [a.get("name") for a in paper.get("authors", [])],
                    "year": paper.get("year"),
                    "doi": doi,
                    "arxiv_id": arxiv_id,
                    "abstract": paper.get("abstract"),
                    "citation_count": paper.get("citationCount", 0),
                    "venue": paper.get("venue"),
                    "url": paper.get("url"),
                    "publication_date": paper.get("publicationDate")
                })
            
            offset += len(batch)
            
            if len(batch) < params["limit"]:
                break
                
        except requests.exceptions.RequestException as e:
            print(f"    Error searching Semantic Scholar: {e}")
            break
    
    print(f"    Found {len(papers)} papers")
    save_cache(cache_path, papers)
    return papers[:limit]


def search_crossref(topic: str, limit: int = 50, year_range: Optional[tuple] = None) -> list:
    """
    Search CrossRef API.
    Free with polite usage (include email in header).
    """
    print(f"  Searching CrossRef for: {topic}")
    
    # Check cache
    cache_path = get_cache_path(topic, "crossref")
    cached = load_cache(cache_path)
    if cached:
        print(f"    Using cached results ({len(cached)} papers)")
        return cached[:limit]
    
    base_url = "https://api.crossref.org/works"
    
    email = os.getenv("CROSSREF_EMAIL", "research-agent@example.com")
    
    params = {
        "query": topic,
        "rows": min(limit, 100),
        "sort": "relevance"
    }
    
    if year_range:
        params["filter"] = f"from-pub-date:{year_range[0]},until-pub-date:{year_range[1]}"
    
    headers = {
        "User-Agent": f"ResearchAgent/1.0 (mailto:{email})"
    }
    
    papers = []
    
    try:
        time.sleep(RATE_LIMITS["crossref"]["delay"])
        response = requests.get(base_url, params=params, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        items = data.get("message", {}).get("items", [])
        
        for item in items:
            authors = []
            for author in item.get("author", []):
                name = f"{author.get('given', '')} {author.get('family', '')}".strip()
                if name:
                    authors.append(name)
            
            year = None
            pub_date = item.get("published-print", item.get("published-online", {}))
            if "date-parts" in pub_date and pub_date["date-parts"]:
                year = pub_date["date-parts"][0][0] if pub_date["date-parts"][0] else None
            
            papers.append({
                "source": "crossref",
                "id": item.get("DOI"),
                "title": item.get("title", [""])[0] if item.get("title") else "",
                "authors": authors,
                "year": year,
                "doi": item.get("DOI"),
                "arxiv_id": None,
                "abstract": item.get("abstract", "").replace("<jats:p>", "").replace("</jats:p>", ""),
                "citation_count": item.get("is-referenced-by-count", 0),
                "venue": item.get("container-title", [""])[0] if item.get("container-title") else "",
                "url": item.get("URL"),
                "publication_date": None
            })
    
    except requests.exceptions.RequestException as e:
        print(f"    Error searching CrossRef: {e}")
    
    print(f"    Found {len(papers)} papers")
    save_cache(cache_path, papers)
    return papers[:limit]


def search_arxiv(topic: str, limit: int = 50, year_range: Optional[tuple] = None) -> list:
    """
    Search arXiv API.
    Rate limit: 1 request per 3 seconds.
    """
    print(f"  Searching arXiv for: {topic}")
    
    # Check cache
    cache_path = get_cache_path(topic, "arxiv")
    cached = load_cache(cache_path)
    if cached:
        print(f"    Using cached results ({len(cached)} papers)")
        return cached[:limit]
    
    import xml.etree.ElementTree as ET
    
    base_url = "http://export.arxiv.org/api/query"
    
    # arXiv uses different query syntax
    search_query = f"all:{quote_plus(topic)}"
    
    params = {
        "search_query": search_query,
        "start": 0,
        "max_results": min(limit, 100),
        "sortBy": "relevance",
        "sortOrder": "descending"
    }
    
    papers = []
    
    try:
        time.sleep(RATE_LIMITS["arxiv"]["delay"])
        response = requests.get(base_url, params=params, timeout=30)
        response.raise_for_status()
        
        # Parse XML response
        root = ET.fromstring(response.content)
        ns = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
        
        for entry in root.findall("atom:entry", ns):
            arxiv_id_full = entry.find("atom:id", ns).text if entry.find("atom:id", ns) is not None else ""
            arxiv_id = arxiv_id_full.split("/")[-1] if arxiv_id_full else None
            
            title = entry.find("atom:title", ns)
            title_text = title.text.replace("\n", " ").strip() if title is not None else ""
            
            abstract = entry.find("atom:summary", ns)
            abstract_text = abstract.text.strip() if abstract is not None else ""
            
            authors = []
            for author in entry.findall("atom:author", ns):
                name = author.find("atom:name", ns)
                if name is not None:
                    authors.append(name.text)
            
            published = entry.find("atom:published", ns)
            pub_date = published.text if published is not None else None
            year = int(pub_date[:4]) if pub_date else None
            
            # Filter by year if specified
            if year_range and year:
                if year < year_range[0] or year > year_range[1]:
                    continue
            
            # Try to get DOI from links
            doi = None
            for link in entry.findall("atom:link", ns):
                if link.get("title") == "doi":
                    doi = link.get("href", "").replace("http://dx.doi.org/", "")
            
            papers.append({
                "source": "arxiv",
                "id": arxiv_id,
                "title": title_text,
                "authors": authors,
                "year": year,
                "doi": doi,
                "arxiv_id": arxiv_id,
                "abstract": abstract_text,
                "citation_count": 0,  # arXiv doesn't provide citation counts
                "venue": "arXiv",
                "url": f"https://arxiv.org/abs/{arxiv_id}",
                "publication_date": pub_date
            })
    
    except requests.exceptions.RequestException as e:
        print(f"    Error searching arXiv: {e}")
    except ET.ParseError as e:
        print(f"    Error parsing arXiv response: {e}")
    
    print(f"    Found {len(papers)} papers")
    save_cache(cache_path, papers)
    return papers[:limit]


def search_google_scholar(topic: str, limit: int = 50, year_range: Optional[tuple] = None) -> list:
    """
    Search Google Scholar via SerpAPI.
    Requires SERPAPI_API_KEY environment variable.
    """
    print(f"  Searching Google Scholar for: {topic}")
    
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        print("    Skipping: SERPAPI_API_KEY not set")
        return []
    
    # Check cache
    cache_path = get_cache_path(topic, "google_scholar")
    cached = load_cache(cache_path)
    if cached:
        print(f"    Using cached results ({len(cached)} papers)")
        return cached[:limit]
    
    base_url = "https://serpapi.com/search.json"
    
    params = {
        "engine": "google_scholar",
        "q": topic,
        "api_key": api_key,
        "num": min(limit, 20)  # Google Scholar returns max ~20 per page
    }
    
    if year_range:
        params["as_ylo"] = year_range[0]
        params["as_yhi"] = year_range[1]
    
    papers = []
    start = 0
    
    while len(papers) < limit:
        params["start"] = start
        
        try:
            time.sleep(RATE_LIMITS["google_scholar"]["delay"])
            response = requests.get(base_url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            results = data.get("organic_results", [])
            if not results:
                break
            
            for result in results:
                # Extract year from publication info
                year = None
                pub_info = result.get("publication_info", {}).get("summary", "")
                import re
                year_match = re.search(r"\b(19|20)\d{2}\b", pub_info)
                if year_match:
                    year = int(year_match.group())
                
                authors = []
                authors_info = result.get("publication_info", {}).get("authors", [])
                for author in authors_info:
                    authors.append(author.get("name", ""))
                
                papers.append({
                    "source": "google_scholar",
                    "id": result.get("result_id"),
                    "title": result.get("title", ""),
                    "authors": authors,
                    "year": year,
                    "doi": None,  # Google Scholar doesn't directly provide DOIs
                    "arxiv_id": None,
                    "abstract": result.get("snippet", ""),
                    "citation_count": result.get("inline_links", {}).get("cited_by", {}).get("total", 0),
                    "venue": result.get("publication_info", {}).get("summary", ""),
                    "url": result.get("link"),
                    "publication_date": None
                })
            
            start += len(results)
            
            if not data.get("serpapi_pagination", {}).get("next"):
                break
                
        except requests.exceptions.RequestException as e:
            print(f"    Error searching Google Scholar: {e}")
            break
    
    print(f"    Found {len(papers)} papers")
    save_cache(cache_path, papers)
    return papers[:limit]


def deduplicate_papers(papers: list) -> list:
    """
    Remove duplicate papers based on DOI or title similarity.
    """
    seen_dois = set()
    seen_titles = set()
    unique_papers = []
    
    for paper in papers:
        doi = paper.get("doi")
        title = paper.get("title", "").lower().strip()
        
        # Skip if we've seen this DOI
        if doi and doi in seen_dois:
            continue
        
        # Skip if we've seen a very similar title
        title_key = "".join(c for c in title if c.isalnum())[:50]
        if title_key and title_key in seen_titles:
            continue
        
        if doi:
            seen_dois.add(doi)
        if title_key:
            seen_titles.add(title_key)
        
        unique_papers.append(paper)
    
    return unique_papers


def rank_papers(papers: list) -> list:
    """
    Rank papers by relevance score combining citation count and recency.
    """
    current_year = datetime.now().year
    
    for paper in papers:
        citations = paper.get("citation_count", 0) or 0
        year = paper.get("year") or current_year
        
        # Recency bonus: newer papers get higher scores
        recency_score = max(0, 10 - (current_year - year))
        
        # Citation score: logarithmic to prevent outliers dominating
        import math
        citation_score = math.log10(citations + 1) * 10
        
        paper["relevance_score"] = citation_score + recency_score
    
    return sorted(papers, key=lambda p: p.get("relevance_score", 0), reverse=True)


def main():
    parser = argparse.ArgumentParser(description="Search academic papers")
    parser.add_argument("--topic", required=True, help="Research topic to search for")
    parser.add_argument("--source", default="all", 
                       choices=["semantic_scholar", "crossref", "arxiv", "google_scholar", "all"],
                       help="Which source to search")
    parser.add_argument("--limit", type=int, default=50, help="Maximum papers to return")
    parser.add_argument("--years", help="Year range (e.g., 2020-2024)")
    parser.add_argument("--output", default=".tmp/discovered_papers.json", help="Output file path")
    
    args = parser.parse_args()
    
    # Parse year range
    year_range = None
    if args.years:
        try:
            start, end = args.years.split("-")
            year_range = (int(start), int(end))
        except ValueError:
            print(f"Invalid year range: {args.years}. Use format: 2020-2024")
            sys.exit(1)
    
    print(f"\nSearching for papers on: {args.topic}")
    print("=" * 50)
    
    all_papers = []
    
    # Search selected sources
    if args.source in ["semantic_scholar", "all"]:
        papers = search_semantic_scholar(args.topic, args.limit, year_range)
        all_papers.extend(papers)
    
    if args.source in ["crossref", "all"]:
        papers = search_crossref(args.topic, args.limit, year_range)
        all_papers.extend(papers)
    
    if args.source in ["arxiv", "all"]:
        papers = search_arxiv(args.topic, args.limit, year_range)
        all_papers.extend(papers)
    
    if args.source in ["google_scholar", "all"]:
        papers = search_google_scholar(args.topic, args.limit, year_range)
        all_papers.extend(papers)
    
    # Deduplicate and rank
    print("\nProcessing results...")
    unique_papers = deduplicate_papers(all_papers)
    print(f"  Removed {len(all_papers) - len(unique_papers)} duplicates")
    
    ranked_papers = rank_papers(unique_papers)
    print(f"  Ranked {len(ranked_papers)} unique papers")
    
    # Limit results
    final_papers = ranked_papers[:args.limit]
    
    # Save results
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "topic": args.topic,
            "searched_at": datetime.now().isoformat(),
            "year_range": args.years,
            "sources": args.source,
            "total_found": len(all_papers),
            "unique_papers": len(unique_papers),
            "papers": final_papers
        }, f, indent=2)
    
    print(f"\nSaved {len(final_papers)} papers to {args.output}")
    
    # Print summary
    print("\nTop 5 papers:")
    for i, paper in enumerate(final_papers[:5], 1):
        title = paper.get("title", "Unknown")[:60]
        year = paper.get("year", "?")
        citations = paper.get("citation_count", 0)
        doi = paper.get("doi", "No DOI")
        print(f"  {i}. [{year}] {title}...")
        print(f"     Citations: {citations}, DOI: {doi}")


if __name__ == "__main__":
    main()
