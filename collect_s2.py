"""
Match faculty into Semantic Scholar via paper DOIs/titles + author search.
For each faculty member, find their S2 author ID by:
  1. Looking up a known paper by DOI/title, then matching the author
  2. Falling back to S2 author search by name
  3. Verifying matches by checking the author's other papers
Outputs data/s2_matches.json with seed paper info for verification.
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error

S2_BASE = "https://api.semanticscholar.org/graph/v1"
HEADERS = {"User-Agent": "dsci-faculty-vis"}

# Faculty whose OpenAlex works are wrong people — skip paper-based matching,
# go straight to author search
BAD_OA = {"Ho Jin Kim", "Kevin McAlister"}

# Manual S2 author ID overrides (verified correct)
S2_OVERRIDES = {
    "Jinho Choi": "4724587",              # Jinho D. Choi — NLP, Emory
    "Maggie Penn": "2503531",              # E. M. Penn — political science, Emory
    "Luis Martinez": "49275958",           # L. Martínez — political economy
    "Michal Arbilly": "6541258",           # M. Arbilly — behavioral ecology, 15 papers
    "Alejandro Sanchez Becerra": "2051323257",  # causal inference, 7 papers
    # "Benjamin J. Miller": no correct S2 profile found (145113184 is an IR scholar, not him)
    # "Zhiyun Gong": no correct S2 profile found (36011651 is a rice geneticist, not her)
    "Lauren Klein": "3458698",              # Lauren F. Klein — DH, Emory+GT (main profile, 55 papers)
    "Kevin McAlister": "46187839",         # political science, election models, Michigan PhD
    "Ho Jin Kim": "46695922",              # Hojin I. Kim — developmental psych, teaches stats at QTM
    "Nathan Hoffmann": "2061194652",       # Nathan I. Hoffmann — migration, demography
    "Gregory Palermo": "153264950",        # Gregory J. Palermo — digital humanities (sparse S2 profile)
}


def api_get(url, retries=4):
    """GET with retry on 429."""
    req = urllib.request.Request(url, headers=HEADERS)
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 10 * (attempt + 1)
                print(f"    Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    HTTP {e.code}: {e.reason}")
                return None
        except Exception as e:
            print(f"    Error: {e}")
            return None
    return None


def lookup_by_doi(doi):
    """Look up a paper in S2 by DOI."""
    doi_bare = doi.replace("https://doi.org/", "")
    url = f"{S2_BASE}/paper/DOI:{urllib.parse.quote(doi_bare, safe='')}?fields=title,year,authors,externalIds"
    return api_get(url)


def lookup_by_title(title):
    """Search for a paper by title in S2."""
    url = f"{S2_BASE}/paper/search?query={urllib.parse.quote(title)}&limit=3&fields=title,year,authors,externalIds"
    data = api_get(url)
    if data and data.get("data"):
        for result in data["data"]:
            if result.get("title", "").lower().strip() == title.lower().strip():
                return result
        return data["data"][0]
    return None


def name_match_score(faculty_name, author_name):
    """Score how well an S2 author name matches the faculty name.
    Higher = better. Returns 0 if no match at all."""
    if not author_name:
        return 0

    fn = faculty_name.lower().strip()
    an = author_name.lower().strip()

    fn_parts = fn.split()
    an_parts = an.split()

    # Exact match
    if fn == an:
        return 100

    # Check last name match — handle compound last names
    # "Alejandro Sanchez Becerra" should match "A. Sanchez Becerra"
    # "Jacopo Di Iorio" should match "J. Di Iorio"
    fn_first = fn_parts[0]
    fn_last_parts = fn_parts[1:]  # everything after first name
    an_first = an_parts[0].rstrip(".")
    an_last_parts = an_parts[1:]

    # Full last name match (all parts after first)
    fn_last = " ".join(fn_last_parts)
    an_last = " ".join(an_last_parts)

    if fn_last == an_last:
        # Last names match — check first name
        if fn_first == an_first:
            return 90  # full match
        if fn_first[0] == an_first[0]:
            return 80  # first initial matches
        return 60  # last name matches, first doesn't

    # Single last name match (just the final part)
    if fn_last_parts and an_last_parts and fn_last_parts[-1] == an_last_parts[-1]:
        if fn_first[0] == an_first[0]:
            return 70  # final last name + first initial
        return 40  # just final last name

    # Initial + last name anywhere
    if fn_last_parts:
        for part in fn_last_parts:
            if part in an_parts:
                return 30

    return 0


def pick_best_author(faculty_name, authors):
    """Pick the S2 author that best matches the faculty name."""
    best = None
    best_score = 0

    for a in authors:
        score = name_match_score(faculty_name, a.get("name"))
        if score > best_score and a.get("id"):
            best = a
            best_score = score

    return best if best_score >= 30 else None


def find_via_papers(works):
    """Try to find S2 paper + author list using known works."""
    for work in works:
        doi = work.get("doi")
        title = work.get("title")

        paper = None
        if doi:
            paper = lookup_by_doi(doi)
            time.sleep(1.5)

        if not paper and title:
            paper = lookup_by_title(title)
            time.sleep(1.5)

        if not paper:
            continue

        return {
            "seed_paper": {
                "title": paper.get("title"),
                "year": paper.get("year"),
                "doi": doi,
                "s2_id": paper.get("paperId"),
            },
            "authors": [
                {"id": a.get("authorId"), "name": a.get("name")}
                for a in paper.get("authors", [])
            ],
        }

    return None


def search_author(name):
    """Search S2 for an author by name. Returns list of candidates."""
    url = (f"{S2_BASE}/author/search"
           f"?query={urllib.parse.quote(name)}"
           f"&limit=5"
           f"&fields=name,paperCount,citationCount,affiliations")
    data = api_get(url)
    if data and data.get("data"):
        return data["data"]
    return []


def get_author_papers(author_id, limit=5):
    """Get an author's top papers for verification."""
    url = (f"{S2_BASE}/author/{author_id}/papers"
           f"?limit={limit}&fields=title,year")
    data = api_get(url)
    if data and data.get("data"):
        return data["data"]
    return []


def verify_author(author_id, faculty_name, expected_works):
    """Check if an S2 author's papers overlap with the faculty's known works.
    Returns number of title matches found."""
    papers = get_author_papers(author_id, limit=20)
    time.sleep(1.5)
    if not papers:
        return 0

    s2_titles = {p.get("title", "").lower().strip() for p in papers}
    expected_titles = {w.get("title", "").lower().strip() for w in expected_works if w.get("title")}

    return len(s2_titles & expected_titles)


def pick_best_author_search(faculty_name, candidates, expected_works):
    """Pick the best author from S2 author search results."""
    best = None
    best_score = -1

    for c in candidates:
        name_score = name_match_score(faculty_name, c.get("name"))
        if name_score < 30:
            continue

        # Prefer Emory affiliation
        affil_bonus = 0
        for a in (c.get("affiliations") or []):
            if "emory" in a.lower():
                affil_bonus = 50

        # Reasonable paper count (not 0, not 10000)
        pc = c.get("paperCount", 0)
        pc_score = 10 if 1 <= pc <= 500 else 0

        score = name_score + affil_bonus + pc_score

        if score > best_score:
            best = c
            best_score = score

    return best


def main():
    with open("data/faculty.json") as f:
        faculty = json.load(f)

    results = []
    total = len(faculty)

    for i, fac in enumerate(faculty):
        name = fac["name"]
        works = fac.get("works", [])

        print(f"[{i+1}/{total}] {name} ({len(works)} works)...")

        # Manual override
        if name in S2_OVERRIDES:
            s2_id = S2_OVERRIDES[name]
            print(f"  Override: S2 ID {s2_id}")
            results.append({
                "name": name,
                "s2_author_id": s2_id,
                "s2_author_name": None,
                "seed_paper": None,
                "method": "override",
            })
            continue

        # Strategy 1: Paper-based matching (skip for BAD_OA faculty)
        matched = False
        if name not in BAD_OA and works:
            match = find_via_papers(works[:5])
            if match:
                author = pick_best_author(name, match["authors"])
                if author:
                    # Verify: check if this author's papers overlap with faculty's known works
                    overlap = verify_author(author["id"], name, works)
                    if overlap > 0:
                        print(f"  Paper match: {author['name']} (S2 ID: {author['id']}, {overlap} verified)")
                        print(f"  Seed: {match['seed_paper']['title']}")
                        results.append({
                            "name": name,
                            "s2_author_id": author["id"],
                            "s2_author_name": author["name"],
                            "seed_paper": match["seed_paper"],
                            "verified_overlap": overlap,
                            "method": "paper",
                        })
                        matched = True
                    else:
                        print(f"  Paper match {author['name']} but 0 verified overlap — trying author search")

        # Strategy 2: Author search fallback
        if not matched:
            print(f"  Trying author search...")
            candidates = search_author(name)
            time.sleep(1.5)

            if candidates:
                best = pick_best_author_search(name, candidates, works)
                if best:
                    # Verify
                    overlap = verify_author(best["authorId"], name, works) if works else 0
                    affiliations = ", ".join(best.get("affiliations") or ["?"])
                    print(f"  Author search: {best['name']} (S2 ID: {best['authorId']})")
                    print(f"    Papers: {best.get('paperCount')}, Citations: {best.get('citationCount')}")
                    print(f"    Affiliations: {affiliations}")
                    print(f"    Verified overlap: {overlap}")
                    results.append({
                        "name": name,
                        "s2_author_id": best["authorId"],
                        "s2_author_name": best["name"],
                        "seed_paper": None,
                        "paper_count": best.get("paperCount"),
                        "citation_count": best.get("citationCount"),
                        "affiliations": best.get("affiliations"),
                        "verified_overlap": overlap,
                        "method": "author_search",
                    })
                    matched = True

            if not matched:
                print(f"  No match found")
                results.append({
                    "name": name,
                    "s2_author_id": None,
                    "seed_paper": None,
                    "method": "none",
                })

    # Save
    with open("data/s2_matches.json", "w") as f:
        json.dump(results, f, indent=2)

    matched_count = sum(1 for r in results if r.get("s2_author_id"))
    verified = sum(1 for r in results if r.get("verified_overlap", 0) > 0)
    print(f"\nMatched {matched_count}/{total} faculty to Semantic Scholar")
    print(f"Verified (paper overlap > 0): {verified}/{matched_count}")
    print("Saved to data/s2_matches.json")


if __name__ == "__main__":
    main()
