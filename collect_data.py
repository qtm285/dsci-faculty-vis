"""
Collect publication data for Emory DSCI faculty from OpenAlex.
Outputs: data/faculty.json (profiles + works metadata)
"""

import requests
import json
import time
import os
from pathlib import Path

# OpenAlex API base
BASE = "https://api.openalex.org"
# Polite pool: include email for faster rate limits
HEADERS = {"User-Agent": "mailto:dsci-faculty-vis@emory.edu"}

FACULTY = [
    # (display_name, hint for disambiguation)
    ("Weihua An", "sociology"),
    ("Abhishek Ananth", None),
    ("Michal Arbilly", "biology"),
    ("Gordon Berman", "biology"),
    ("Clifford Carrubba", "political science"),
    ("Jinho Choi", "computer science NLP"),
    ("Hun Chung", "political"),
    ("Jacopo Di Iorio", "statistics"),
    ("Danilo Freire", "political science"),
    ("Adam Glynn", "political science"),
    ("Zhiyun Gong", None),
    ("Jo Guldi", "history digital humanities"),
    ("Craig Hadley", "anthropology"),
    ("David Hirshberg", "causal inference"),
    ("Ho Jin Kim", None),
    ("Lauren Klein", "digital humanities"),
    ("Kevin McAlister", None),
    ("Pablo Montagnes", "political science"),
    ("John W. Patty", "political science"),
    ("Maggie Penn", "political science"),
    ("Zachary Peskowitz", "political science"),
    ("Kevin Quinn", "political science statistics"),
    ("Alejandro Sanchez Becerra", None),
    ("Sandeep Soni", "NLP computational"),
    ("Allison Stashko", "political science"),
    ("Alexander Tolbert", None),
    ("Ruoxuan Xiong", "causal inference"),
    ("Zachary Binney", "epidemiology"),
    ("Nathan Hoffmann", "sociology"),
    ("Luis Martinez", "political science economics"),
    ("Heeju Sohn", "sociology"),
    ("Gregory Palermo", "English"),
    ("Dan Sinykin", "English literature"),
    ("Benjamin J. Miller", "writing"),
    ("Megan Reed", "sociology"),
]

# Override IDs for authors where search picks the wrong person
AUTHOR_ID_OVERRIDES = {
    "Alexander Tolbert": "https://openalex.org/A5009210163",
    "Nathan Hoffmann": "https://openalex.org/A5000544058",
    "Jacopo Di Iorio": "https://openalex.org/A5041921656",
}


def search_author(name, hint=None):
    """Search OpenAlex for an author affiliated with Emory."""
    params = {
        "search": name,
        "filter": "affiliations.institution.ror:https://ror.org/03czfpz43",  # Emory ROR
        "per_page": 5,
    }
    resp = requests.get(f"{BASE}/authors", params=params, headers=HEADERS)
    resp.raise_for_status()
    results = resp.json().get("results", [])

    if not results:
        # Try without institution filter
        params.pop("filter")
        resp = requests.get(f"{BASE}/authors", params=params, headers=HEADERS)
        resp.raise_for_status()
        results = resp.json().get("results", [])

    if not results:
        return None

    # If multiple results and we have a hint, try to pick the best match
    if len(results) > 1 and hint:
        for r in results:
            topics = " ".join(
                t.get("display_name", "").lower()
                for t in r.get("topics", [])[:10]
            )
            if any(h in topics for h in hint.lower().split()):
                return r
    return results[0]


def get_works(author_id, per_page=200):
    """Get an author's works from OpenAlex."""
    works = []
    cursor = "*"
    while cursor:
        params = {
            "filter": f"authorships.author.id:{author_id}",
            "per_page": min(per_page, 200),
            "cursor": cursor,
            "select": "id,doi,title,publication_year,type,cited_by_count,"
                      "authorships,topics,primary_topic,biblio,"
                      "primary_location,referenced_works,concepts",
        }
        resp = requests.get(f"{BASE}/works", params=params, headers=HEADERS)
        resp.raise_for_status()
        data = resp.json()
        works.extend(data.get("results", []))
        cursor = data.get("meta", {}).get("next_cursor")
        if not data.get("results"):
            break
        time.sleep(0.1)  # Be polite
    return works


def slim_work(w):
    """Keep only the fields we need from a work record."""
    return {
        "id": w["id"],
        "doi": w.get("doi"),
        "title": w.get("title"),
        "year": w.get("publication_year"),
        "type": w.get("type"),
        "cited_by_count": w.get("cited_by_count", 0),
        "authors": [
            {
                "id": a["author"]["id"],
                "name": a["author"].get("display_name"),
            }
            for a in w.get("authorships", [])
        ],
        "topics": [
            {"name": t["display_name"], "score": t.get("score", 0)}
            for t in (w.get("topics") or [])[:5]
        ],
        "primary_topic": (w.get("primary_topic") or {}).get("display_name"),
        "journal": (
            (w.get("primary_location") or {}).get("source") or {}
        ).get("display_name"),
        "referenced_works": w.get("referenced_works", []),
        "concepts": [
            {"name": c["display_name"], "score": c.get("score", 0)}
            for c in (w.get("concepts") or [])[:10]
        ],
    }


def main():
    os.makedirs("data", exist_ok=True)
    faculty_data = []
    total = len(FACULTY)

    for i, (name, hint) in enumerate(FACULTY):
        print(f"[{i+1}/{total}] Searching for {name}...")
        if name in AUTHOR_ID_OVERRIDES:
            override_id = AUTHOR_ID_OVERRIDES[name]
            resp = requests.get(f"{BASE}/authors/{override_id}", headers=HEADERS)
            resp.raise_for_status()
            author = resp.json()
            print(f"  Using override: {author.get('display_name')} ({override_id})")
        else:
            author = search_author(name, hint)
        if not author:
            print(f"  !! Not found: {name}")
            faculty_data.append({
                "name": name,
                "openalex_id": None,
                "works_count": 0,
                "cited_by_count": 0,
                "topics": [],
                "works": [],
            })
            continue

        author_id = author["id"]
        print(f"  Found: {author.get('display_name')} ({author_id})")
        print(f"  Works: {author.get('works_count', '?')}, "
              f"Citations: {author.get('cited_by_count', '?')}")

        # Get topics
        topics = [
            {"name": t["display_name"], "score": t.get("score", 0)}
            for t in (author.get("topics") or [])[:15]
        ]

        # Get works
        print(f"  Fetching works...")
        works = get_works(author_id)
        print(f"  Got {len(works)} works")

        faculty_data.append({
            "name": name,
            "openalex_id": author_id,
            "display_name": author.get("display_name"),
            "works_count": author.get("works_count", 0),
            "cited_by_count": author.get("cited_by_count", 0),
            "topics": topics,
            "works": [slim_work(w) for w in works],
        })
        time.sleep(0.2)  # Be polite between authors

    # Save
    outpath = Path("data/faculty.json")
    with open(outpath, "w") as f:
        json.dump(faculty_data, f, indent=2)
    print(f"\nSaved {len(faculty_data)} faculty records to {outpath}")
    print(f"Found: {sum(1 for f in faculty_data if f['openalex_id'])} / {total}")


if __name__ == "__main__":
    main()
