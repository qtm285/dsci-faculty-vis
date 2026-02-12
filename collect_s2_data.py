"""
Collect Semantic Scholar data for all matched faculty.
Fetches papers, co-authors, and references for each S2 author.

Designed to run overnight:
  - Saves progress after each author (resumable)
  - Generous sleeps between API calls
  - Exponential backoff on rate limits

Usage:
  python3 -u collect_s2_data.py          # full run
  python3 -u collect_s2_data.py --force   # re-collect all (ignore cache)

Outputs: data/s2_faculty.json
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error
import os
import sys

S2_BASE = "https://api.semanticscholar.org/graph/v1"
HEADERS = {"User-Agent": "dsci-faculty-vis (emory.edu research project)"}
OUTPUT = "data/s2_faculty.json"
MATCHES = "data/s2_matches.json"
SLEEP = 3  # base seconds between API calls


def api_get(url, retries=8):
    """GET with retry on 429, generous backoff."""
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = min(10 * (attempt + 1), 120)
                print(f"    429 rate limited, waiting {wait}s...")
                time.sleep(wait)
            elif e.code == 404:
                print(f"    404 not found")
                return None
            else:
                print(f"    HTTP {e.code}: {e.reason}")
                if attempt < retries - 1:
                    time.sleep(5)
                else:
                    return None
        except Exception as e:
            print(f"    Error: {e}")
            if attempt < retries - 1:
                time.sleep(5)
            else:
                return None
    return None


def get_author_info(author_id):
    """Get author profile."""
    url = (f"{S2_BASE}/author/{author_id}"
           f"?fields=name,paperCount,citationCount,hIndex,affiliations")
    data = api_get(url)
    time.sleep(SLEEP)
    return data


def get_author_papers(author_id):
    """Get all papers for an author, paginated. Includes co-authors and references."""
    all_papers = []
    offset = 0
    limit = 100
    fields = ",".join([
        "title", "year", "venue", "citationCount",
        "externalIds",
        "authors.authorId", "authors.name",
        "references.paperId",
    ])

    while True:
        url = (f"{S2_BASE}/author/{author_id}/papers"
               f"?offset={offset}&limit={limit}&fields={fields}")

        print(f"    Fetching papers {offset}-{offset+limit}...")
        data = api_get(url)
        time.sleep(SLEEP)

        if not data or not data.get("data"):
            break

        all_papers.extend(data["data"])

        if len(data["data"]) < limit:
            break
        offset += limit

    return all_papers


def summarize_papers(papers):
    """Extract the data we need from raw S2 paper responses."""
    result = []
    for p in papers:
        result.append({
            "paperId": p.get("paperId"),
            "title": p.get("title"),
            "year": p.get("year"),
            "venue": p.get("venue"),
            "citationCount": p.get("citationCount"),
            "doi": (p.get("externalIds") or {}).get("DOI"),
            "authors": [
                {"id": a.get("authorId"), "name": a.get("name")}
                for a in (p.get("authors") or [])
            ],
            "references": [
                r.get("paperId")
                for r in (p.get("references") or [])
                if r.get("paperId")
            ],
        })
    return result


def main():
    force = "--force" in sys.argv

    with open(MATCHES) as f:
        matches = json.load(f)

    # Load existing progress
    progress = {}
    if os.path.exists(OUTPUT) and not force:
        with open(OUTPUT) as f:
            existing = json.load(f)
            progress = {e["name"]: e for e in existing}

    results = []
    total = len(matches)

    for i, match in enumerate(matches):
        name = match["name"]
        s2_id = match.get("s2_author_id")

        if not s2_id:
            print(f"[{i+1}/{total}] {name} — no S2 ID, skipping")
            results.append({"name": name, "s2_author_id": None})
            continue

        # Resume from cache
        if name in progress and progress[name].get("papers") is not None:
            n = len(progress[name].get("papers", []))
            print(f"[{i+1}/{total}] {name} — cached ({n} papers)")
            results.append(progress[name])
            continue

        print(f"[{i+1}/{total}] {name} (S2 ID: {s2_id})...")

        # Get author profile
        info = get_author_info(s2_id)
        if not info:
            print(f"  Could not fetch author profile")
            results.append({"name": name, "s2_author_id": s2_id, "papers": []})
            save(results)
            continue

        print(f"  {info.get('name')}: {info.get('paperCount')} papers, "
              f"{info.get('citationCount')} citations, h={info.get('hIndex')}")

        # Get all papers with co-authors and references
        raw_papers = get_author_papers(s2_id)
        papers = summarize_papers(raw_papers)

        entry = {
            "name": name,
            "s2_author_id": s2_id,
            "s2_name": info.get("name"),
            "s2_paper_count": info.get("paperCount"),
            "s2_citation_count": info.get("citationCount"),
            "s2_hindex": info.get("hIndex"),
            "s2_affiliations": info.get("affiliations"),
            "papers": papers,
        }
        results.append(entry)

        # Save after each author
        save(results)

        n_refs = sum(len(p.get("references", [])) for p in papers)
        print(f"  Collected {len(papers)} papers, {n_refs} total references")

        # Extra sleep between authors
        time.sleep(SLEEP * 2)

    print(f"\nDone. {total} faculty processed.")
    print(f"Saved to {OUTPUT}")

    # Summary
    for r in results:
        n = len(r.get("papers", []))
        print(f"  {r['name']}: {n} papers")


def save(results):
    with open(OUTPUT, "w") as f:
        json.dump(results, f, indent=2)


if __name__ == "__main__":
    main()
