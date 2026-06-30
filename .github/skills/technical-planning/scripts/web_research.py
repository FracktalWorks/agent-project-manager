#!/usr/bin/env python3
"""
Web Research Tool for Technical Project Planning

Searches the web for industry practices, prior art, standards, technology comparisons,
and recent developments. Uses SerpAPI for Google Search, Google News, and Google Scholar.

Usage:
    python web_research.py --mode search --query "embedded system architecture" --num-results 15
    python web_research.py --mode prior-art --query "autonomous drone inspection" --num-results 15
    python web_research.py --mode standards --query "IEC 61508 functional safety" --num-results 10
    python web_research.py --mode news --query "robotics latest 2025" --num-results 10
    python web_research.py --mode tech-compare --query "ROS2 vs custom RTOS for robotics" --num-results 10
    python web_research.py --mode multi --queries-file ".tmp/queries.json" --output ".tmp/research/"
"""

import os
import sys
import json
import time
import hashlib
import argparse
from datetime import datetime
from pathlib import Path
from typing import Optional

# Ensure .tmp/scripts/ is importable (for load_env)
REPO_ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO_ROOT / ".tmp" / "scripts"))
from load_env import load_env; load_env()

import requests

# Cache settings
CACHE_DIR = Path(".tmp/web_cache")
CACHE_MAX_AGE_HOURS = 48

# Rate limiting
RATE_LIMIT_DELAY = 2.0  # seconds between SerpAPI requests


def get_cache_path(query: str, mode: str) -> Path:
    """Generate cache file path for a query."""
    hash_str = hashlib.md5(f"{mode}:{query}".encode()).hexdigest()[:12]
    return CACHE_DIR / f"{mode}_{hash_str}.json"


def load_cache(cache_path: Path) -> Optional[dict]:
    """Load cached results if fresh enough."""
    if not cache_path.exists():
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        cached_time = datetime.fromisoformat(data.get("cached_at", "2000-01-01"))
        age_hours = (datetime.now() - cached_time).total_seconds() / 3600
        if age_hours < CACHE_MAX_AGE_HOURS:
            return data
    except Exception:
        pass
    return None


def save_cache(cache_path: Path, data: dict) -> None:
    """Save results to cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    data["cached_at"] = datetime.now().isoformat()
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _serpapi_search(params: dict) -> dict:
    """Execute a SerpAPI search with shared logic."""
    api_key = os.getenv("SERPAPI_API_KEY")
    if not api_key:
        raise ValueError(
            "SERPAPI_API_KEY not set. Get one at https://serpapi.com/ "
            "(free tier: 100 searches/month)"
        )
    params["api_key"] = api_key
    time.sleep(RATE_LIMIT_DELAY)
    resp = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


#  Search Modes 


def search_web(query: str, num_results: int = 15, location: str = "United States") -> dict:
    """General web search for industry practices, architecture patterns, etc."""
    print(f"  [web] Searching: {query}")

    cache_path = get_cache_path(query, "web")
    cached = load_cache(cache_path)
    if cached:
        print(f"    Using cached results ({len(cached.get('results', []))} items)")
        return cached

    raw = _serpapi_search({
        "engine": "google",
        "q": query,
        "num": num_results,
        "location": location,
        "hl": "en",
    })

    results = []
    for item in raw.get("organic_results", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("link"),
            "snippet": item.get("snippet"),
            "position": item.get("position"),
            "source": item.get("displayed_link"),
        })

    related_questions = [
        {"question": q.get("question"), "snippet": q.get("snippet")}
        for q in raw.get("related_questions", [])
    ]

    knowledge_graph = None
    if "knowledge_graph" in raw:
        kg = raw["knowledge_graph"]
        knowledge_graph = {
            "title": kg.get("title"),
            "description": kg.get("description"),
            "source": kg.get("source", {}).get("link"),
        }

    data = {
        "query": query,
        "mode": "search",
        "total_results": raw.get("search_information", {}).get("total_results"),
        "results": results,
        "related_questions": related_questions,
        "knowledge_graph": knowledge_graph,
        "timestamp": datetime.now().isoformat(),
    }
    save_cache(cache_path, data)
    print(f"    Found {len(results)} results")
    return data


def search_prior_art(query: str, num_results: int = 15) -> dict:
    """Search for prior art, reference designs, existing implementations."""
    print(f"  [prior-art] Searching: {query}")

    # Combine multiple targeted searches
    queries = [
        f"{query} reference architecture design",
        f"{query} system implementation case study",
        f"{query} open source project github",
    ]

    all_results = []
    seen_urls = set()

    for q in queries:
        cache_path = get_cache_path(q, "prior_art")
        cached = load_cache(cache_path)
        if cached:
            for r in cached.get("results", []):
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)
            continue

        try:
            raw = _serpapi_search({
                "engine": "google",
                "q": q,
                "num": min(num_results, 10),
                "hl": "en",
            })
            results = []
            for item in raw.get("organic_results", []):
                entry = {
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "snippet": item.get("snippet"),
                    "source": item.get("displayed_link"),
                    "search_query": q,
                }
                results.append(entry)
                if entry["url"] not in seen_urls:
                    seen_urls.add(entry["url"])
                    all_results.append(entry)

            save_cache(cache_path, {"query": q, "results": results})
        except Exception as e:
            print(f"    Warning: search failed for '{q}': {e}")

    data = {
        "query": query,
        "mode": "prior-art",
        "results": all_results[:num_results],
        "timestamp": datetime.now().isoformat(),
    }
    print(f"    Found {len(data['results'])} prior-art results")
    return data


def search_standards(query: str, num_results: int = 10) -> dict:
    """Search for engineering standards, compliance requirements, regulations."""
    print(f"  [standards] Searching: {query}")

    cache_path = get_cache_path(query, "standards")
    cached = load_cache(cache_path)
    if cached:
        print(f"    Using cached results")
        return cached

    raw = _serpapi_search({
        "engine": "google",
        "q": f"{query} standard specification regulation",
        "num": num_results,
        "hl": "en",
    })

    results = []
    for item in raw.get("organic_results", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("link"),
            "snippet": item.get("snippet"),
            "source": item.get("displayed_link"),
        })

    data = {
        "query": query,
        "mode": "standards",
        "results": results,
        "timestamp": datetime.now().isoformat(),
    }
    save_cache(cache_path, data)
    print(f"    Found {len(results)} results")
    return data


def search_news(query: str, num_results: int = 10) -> dict:
    """Search for recent news and developments."""
    print(f"  [news] Searching: {query}")

    cache_path = get_cache_path(query, "news")
    cached = load_cache(cache_path)
    if cached:
        print(f"    Using cached results")
        return cached

    raw = _serpapi_search({
        "engine": "google_news",
        "q": query,
        "gl": "us",
        "hl": "en",
    })

    results = []
    for item in raw.get("news_results", []):
        results.append({
            "title": item.get("title"),
            "url": item.get("link"),
            "source": item.get("source", {}).get("name") if isinstance(item.get("source"), dict) else item.get("source"),
            "date": item.get("date"),
            "snippet": item.get("snippet"),
        })

    data = {
        "query": query,
        "mode": "news",
        "results": results[:num_results],
        "timestamp": datetime.now().isoformat(),
    }
    save_cache(cache_path, data)
    print(f"    Found {len(data['results'])} news articles")
    return data


def search_tech_compare(query: str, num_results: int = 10) -> dict:
    """Search for technology comparisons and trade-off analyses."""
    print(f"  [tech-compare] Searching: {query}")

    queries = [
        f"{query} comparison",
        f"{query} pros cons trade-offs",
        f"{query} benchmark performance",
    ]

    all_results = []
    seen_urls = set()

    for q in queries:
        cache_path = get_cache_path(q, "tech_compare")
        cached = load_cache(cache_path)
        if cached:
            for r in cached.get("results", []):
                if r["url"] not in seen_urls:
                    seen_urls.add(r["url"])
                    all_results.append(r)
            continue

        try:
            raw = _serpapi_search({
                "engine": "google",
                "q": q,
                "num": min(num_results, 10),
                "hl": "en",
            })
            results = []
            for item in raw.get("organic_results", []):
                entry = {
                    "title": item.get("title"),
                    "url": item.get("link"),
                    "snippet": item.get("snippet"),
                    "source": item.get("displayed_link"),
                    "search_query": q,
                }
                results.append(entry)
                if entry["url"] not in seen_urls:
                    seen_urls.add(entry["url"])
                    all_results.append(entry)

            save_cache(cache_path, {"query": q, "results": results})
        except Exception as e:
            print(f"    Warning: search failed for '{q}': {e}")

    data = {
        "query": query,
        "mode": "tech-compare",
        "results": all_results[:num_results],
        "timestamp": datetime.now().isoformat(),
    }
    print(f"    Found {len(data['results'])} comparison results")
    return data


def run_multi_search(queries_file: str, output_dir: str) -> dict:
    """Run multiple searches from a JSON file of queries."""
    print(f"  [multi] Loading queries from: {queries_file}")

    with open(queries_file, "r", encoding="utf-8") as f:
        queries = json.load(f)

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_results = {}
    for entry in queries:
        mode = entry.get("mode", "search")
        query = entry["query"]
        num = entry.get("num_results", 10)
        label = entry.get("label", query[:40])

        try:
            if mode == "search":
                result = search_web(query, num)
            elif mode == "prior-art":
                result = search_prior_art(query, num)
            elif mode == "standards":
                result = search_standards(query, num)
            elif mode == "news":
                result = search_news(query, num)
            elif mode == "tech-compare":
                result = search_tech_compare(query, num)
            else:
                print(f"    Unknown mode '{mode}', defaulting to web search")
                result = search_web(query, num)

            safe_label = "".join(c if c.isalnum() or c in "-_ " else "_" for c in label)[:60]
            fname = f"{mode}_{safe_label.strip().replace(' ', '_')}.json"
            with open(output_path / fname, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)

            all_results[label] = {
                "mode": mode,
                "file": fname,
                "result_count": len(result.get("results", [])),
            }
        except Exception as e:
            print(f"    ERROR for '{label}': {e}")
            all_results[label] = {"mode": mode, "error": str(e)}

    summary = {
        "total_searches": len(queries),
        "successful": sum(1 for v in all_results.values() if "error" not in v),
        "results": all_results,
        "timestamp": datetime.now().isoformat(),
    }

    with open(output_path / "_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)

    print(f"\n  Multi-search complete: {summary['successful']}/{summary['total_searches']} succeeded")
    return summary


#  CLI 


def main():
    parser = argparse.ArgumentParser(
        description="Web research for technical project planning"
    )
    parser.add_argument(
        "--mode",
        required=True,
        choices=["search", "prior-art", "standards", "news", "tech-compare", "multi"],
        help="Research mode",
    )
    parser.add_argument("--query", help="Search query")
    parser.add_argument("--num-results", type=int, default=15, help="Max results")
    parser.add_argument("--location", default="United States", help="Location for search")
    parser.add_argument("--queries-file", help="JSON file with multiple queries (for multi mode)")
    parser.add_argument("--output", help="Output file or directory path")

    args = parser.parse_args()

    if args.mode == "multi":
        if not args.queries_file:
            print("ERROR: --queries-file required for multi mode")
            sys.exit(1)
        result = run_multi_search(args.queries_file, args.output or ".tmp/web_research/")
    else:
        if not args.query:
            print("ERROR: --query required")
            sys.exit(1)

        if args.mode == "search":
            result = search_web(args.query, args.num_results, args.location)
        elif args.mode == "prior-art":
            result = search_prior_art(args.query, args.num_results)
        elif args.mode == "standards":
            result = search_standards(args.query, args.num_results)
        elif args.mode == "news":
            result = search_news(args.query, args.num_results)
        elif args.mode == "tech-compare":
            result = search_tech_compare(args.query, args.num_results)

        # Print summary
        print(json.dumps(result, indent=2, ensure_ascii=False))

        # Save to file
        if args.output:
            out = Path(args.output)
            out.parent.mkdir(parents=True, exist_ok=True)
            with open(out, "w", encoding="utf-8") as f:
                json.dump(result, f, indent=2, ensure_ascii=False)
            print(f"\nSaved to: {args.output}")


if __name__ == "__main__":
    main()
