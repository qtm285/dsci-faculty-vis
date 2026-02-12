"""
Build faculty graph v2 — merges Google Scholar + OpenAlex data.
Scholar: accurate citations, co-authors, interests.
OpenAlex: shared references, topics, journals.
Outputs: data/graph.json
"""

import json
from collections import Counter, defaultdict
from itertools import combinations

# Area detection keywords — order matters (first match wins per keyword)
AREA_KEYWORDS = {
    "Political Science": [
        "political", "politic", "election", "voting", "legislative",
        "congress", "democrat", "governance", "public policy",
        "political economy", "political theory", "legislature",
        "redistricting", "gerrymander", "accountability",
    ],
    "NLP / Computational": [
        "natural language", "nlp", "computational linguist",
        "text mining", "sentiment", "machine learning",
        "artificial intelligence", "deep learning",
        "information retrieval", "language model", "narratolog",
        "conversational", "dialogue", "named entity",
    ],
    "Statistics / Causal Inference": [
        "causal", "statistic", "bayesian", "econometric",
        "regression", "inference", "estimation", "semiparametric",
        "high dimensional", "time series", "actuarial",
        "functional data", "clustering", "survey",
        "measurement", "methodology", "propensity",
    ],
    "Digital Humanities": [
        "digital humanit", "humanities", "literary",
        "cultural", "history", "text as data",
        "data feminism", "rhetoric", "writing",
        "publishing", "visualization", "archive",
    ],
    "Biology / Neuroscience": [
        "biolog", "neuro", "animal", "behavio",
        "ecolog", "brain", "genome", "evolution",
        "cognitive", "species", "phenotyp",
    ],
    "Sociology / Public Health": [
        "sociolog", "health", "epidemiol",
        "inequality", "immigra", "food",
        "nutrition", "anthropol", "demograph",
        "family", "gender", "marriage", "migration",
        "stratification", "sport", "injur",
    ],
    "Computer Vision": [
        "computer vision", "image", "3d", "body scan",
        "mesh", "reconstruction", "rendering", "visual",
        "object detection", "segmentation", "pose",
    ],
}

# Manual area distributions for people where auto-detection is poor or absent
# Format: {name: {area: weight, ...}} — weights are relative, get normalized
MANUAL_AREAS = {
    "Weihua An": {"Statistics / Causal Inference": 3, "Sociology / Public Health": 2},
    "Adam Glynn": {"Statistics / Causal Inference": 3, "Political Science": 2},
    "Kevin Quinn": {"Statistics / Causal Inference": 3, "Political Science": 2},
    "Clifford Carrubba": {"Political Science": 4, "Statistics / Causal Inference": 1},
    "John W. Patty": {"Political Science": 3, "Statistics / Causal Inference": 1},
    "Maggie Penn": {"Political Science": 3, "Statistics / Causal Inference": 1},
    "Hun Chung": {"Political Science": 3, "Statistics / Causal Inference": 1},
    "Lauren Klein": {"Digital Humanities": 3, "NLP / Computational": 1},
    "Sandeep Soni": {"NLP / Computational": 3, "Digital Humanities": 1},
    "Alexander Tolbert": {"NLP / Computational": 2, "Digital Humanities": 2},
    "Benjamin J. Miller": {"Digital Humanities": 2, "NLP / Computational": 2},
    "Jo Guldi": {"Digital Humanities": 3, "Political Science": 1},
    "Craig Hadley": {"Sociology / Public Health": 4},
    "David Hirshberg": {"Statistics / Causal Inference": 3, "Computer Vision": 1},
    "Ruoxuan Xiong": {"Statistics / Causal Inference": 4},
    "Allison Stashko": {"Political Science": 2, "Statistics / Causal Inference": 2},
    "Luis Martinez": {"Political Science": 3, "Statistics / Causal Inference": 1},
    "Pablo Montagnes": {"Political Science": 3, "Statistics / Causal Inference": 1},
    "Zachary Peskowitz": {"Political Science": 4, "Statistics / Causal Inference": 1},
    "Zachary Binney": {"Sociology / Public Health": 3, "Statistics / Causal Inference": 1},
    "Gordon Berman": {"Biology / Neuroscience": 3, "NLP / Computational": 1},
    "Michal Arbilly": {"Biology / Neuroscience": 4},
    "Jinho Choi": {"NLP / Computational": 4},
    "Danilo Freire": {"Political Science": 3, "Statistics / Causal Inference": 1},
    "Alejandro Sanchez Becerra": {"Statistics / Causal Inference": 3, "Political Science": 1},
    "Gregory Palermo": {"Digital Humanities": 4},
    "Dan Sinykin": {"Digital Humanities": 3, "NLP / Computational": 1},
    "Nathan Hoffmann": {"Sociology / Public Health": 3, "Statistics / Causal Inference": 1},
    "Heeju Sohn": {"Sociology / Public Health": 4},
    "Megan Reed": {"Sociology / Public Health": 4},
    "Ho Jin Kim": {"Biology / Neuroscience": 3, "Statistics / Causal Inference": 1},
    "Zhiyun Gong": {"Statistics / Causal Inference": 4},
    "Abhishek Ananth": {"Statistics / Causal Inference": 3, "Sociology / Public Health": 1},
    "Kevin McAlister": {"Political Science": 3, "Statistics / Causal Inference": 1},
    "Jacopo Di Iorio": {"Statistics / Causal Inference": 4},
}


FACULTY_WEBSITES = {
    "Weihua An": "https://www.weihuaan.net/",
    "Adam Glynn": "https://www.adamnglynn.com/",
    "John W. Patty": "https://www.johnwpatty.net/",
    "Maggie Penn": "https://www.elizabethmpenn.com/",
    "Hun Chung": "http://hunchung.com/",
    "Lauren Klein": "https://lklein.com/",
    "Sandeep Soni": "https://sandeepsoni.github.io/",
    "Alexander Tolbert": "https://www.alexanderwilliamstolbert.com/",
    "Benjamin J. Miller": "https://benmiller.mit.edu/",
    "Jo Guldi": "https://www.joguldi.com/",
    "David Hirshberg": "https://davidahirshberg.bitbucket.io/",
    "Ruoxuan Xiong": "https://www.ruoxuanxiong.com/",
    "Allison Stashko": "https://sites.google.com/view/allisonstashko/home",
    "Luis Martinez": "https://sites.google.com/site/lrmartineza",
    "Pablo Montagnes": "https://www.pablomontagnes.com/",
    "Zachary Peskowitz": "https://www.zacharypeskowitz.com/",
    "Zachary Binney": "https://zachbinney.com/",
    "Gordon Berman": "https://faculty.college.emory.edu/sites/berman/",
    "Michal Arbilly": "https://michalarbilly.com/",
    "Jinho Choi": "https://www.emorynlp.org/",
    "Danilo Freire": "https://danilofreire.github.io/",
    "Alejandro Sanchez Becerra": "https://sites.google.com/site/sanchezbecerraalejandro/home",
    "Gregory Palermo": "http://gregorypalermo.org/",
    "Dan Sinykin": "http://www.dansinykin.com/",
    "Nathan Hoffmann": "https://nathanhoffmann.com/",
    "Heeju Sohn": "https://www.heejusohn.com/",
    "Megan Reed": "https://sites.google.com/view/meganreed/",
    "Abhishek Ananth": "https://abhiananthecon.github.io/",
    "Kevin McAlister": "http://www.kevinmcalister.org/",
}


def compute_area_distribution(name, openalex_fac, scholar_fac):
    """Compute research area distribution from topics, concepts, and interests."""
    # If we have a manual override, use it
    if name in MANUAL_AREAS:
        raw = MANUAL_AREAS[name]
        total = sum(raw.values())
        return [{"area": a, "share": round(w / total, 3)}
                for a, w in sorted(raw.items(), key=lambda x: -x[1])]

    # Build text corpus from all available sources
    text_parts = []
    if scholar_fac and scholar_fac.get("interests"):
        text_parts.extend(scholar_fac["interests"])
    if openalex_fac:
        for t in openalex_fac.get("topics", []):
            text_parts.append(t["name"])
        for w in openalex_fac.get("works", [])[:30]:
            if w.get("primary_topic"):
                text_parts.append(w["primary_topic"])
            for c in w.get("concepts", [])[:5]:
                text_parts.append(c["name"])

    text = " ".join(text_parts).lower()
    if not text:
        return [{"area": "Statistics / Causal Inference", "share": 1.0}]

    # Score each area by keyword hits
    scores = {}
    for area, keywords in AREA_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[area] = score

    if not scores:
        return [{"area": "Statistics / Causal Inference", "share": 1.0}]

    total = sum(scores.values())
    dist = [{"area": a, "share": round(s / total, 3)}
            for a, s in sorted(scores.items(), key=lambda x: -x[1])]

    # Filter out tiny slices (< 8%)
    dist = [d for d in dist if d["share"] >= 0.08]
    # Re-normalize
    total = sum(d["share"] for d in dist)
    for d in dist:
        d["share"] = round(d["share"] / total, 3)

    return dist


def load_data():
    with open("data/scholar.json") as f:
        scholar = json.load(f)
    with open("data/faculty.json") as f:
        openalex = json.load(f)
    return scholar, openalex


def build_scholar_coauthor_edges(scholar_data):
    """Find edges where two DSCI faculty are listed as co-authors on Scholar."""
    # Build scholar_id -> faculty_name mapping
    sid_to_name = {}
    for fac in scholar_data:
        if fac.get("scholar_id"):
            sid_to_name[fac["scholar_id"]] = fac["name"]

    edges = defaultdict(lambda: {"scholar_coauthor": True})
    for fac in scholar_data:
        if not fac.get("coauthors"):
            continue
        for ca in fac["coauthors"]:
            ca_sid = ca.get("scholar_id", "")
            if ca_sid in sid_to_name and sid_to_name[ca_sid] != fac["name"]:
                key = tuple(sorted([fac["name"], sid_to_name[ca_sid]]))
                edges[key]["scholar_coauthor"] = True

    return edges


def build_openalex_edges(openalex_data):
    """Build edges from OpenAlex: co-authorship, shared refs, topics, journals."""
    # Bad matches to skip
    BAD = {"Ho Jin Kim", "Kevin McAlister"}

    # Build author index
    author_index = {}
    for fac in openalex_data:
        if fac["openalex_id"] and fac["name"] not in BAD:
            author_index[fac["openalex_id"]] = fac["name"]

    # Co-author edges from actual papers
    coauthor_edges = defaultdict(lambda: {"count": 0, "papers": []})
    for fac in openalex_data:
        if not fac["openalex_id"] or fac["name"] in BAD:
            continue
        for work in fac["works"]:
            work_aids = [a["id"] for a in work["authors"]]
            faculty_coauthors = [
                author_index[aid]
                for aid in work_aids
                if aid in author_index and author_index[aid] != fac["name"]
            ]
            for ca_name in faculty_coauthors:
                key = tuple(sorted([fac["name"], ca_name]))
                coauthor_edges[key]["count"] += 1
                if work["title"] and work["title"] not in coauthor_edges[key]["papers"]:
                    coauthor_edges[key]["papers"].append(work["title"])
    # Dedupe (counted from both sides)
    for key in coauthor_edges:
        coauthor_edges[key]["count"] = (coauthor_edges[key]["count"] + 1) // 2
        seen = set()
        coauthor_edges[key]["papers"] = [
            p for p in coauthor_edges[key]["papers"]
            if p not in seen and not seen.add(p)
        ]

    # Shared references — store actual IDs ranked by department-wide frequency
    ref_sets = {}
    ref_frequency = Counter()  # how many faculty cite each ref
    for fac in openalex_data:
        if not fac["works"] or fac["name"] in BAD:
            continue
        refs = set()
        for w in fac["works"]:
            refs.update(w.get("referenced_works", []))
        if refs:
            ref_sets[fac["name"]] = refs
            ref_frequency.update(refs)

    shared_ref_edges = {}
    names = list(ref_sets.keys())
    for i, n1 in enumerate(names):
        for n2 in names[i+1:]:
            overlap = ref_sets[n1] & ref_sets[n2]
            if len(overlap) >= 3:
                # Top 15 shared refs ranked by how many dept faculty cite them
                top_ids = sorted(overlap, key=lambda r: ref_frequency[r], reverse=True)[:15]
                shared_ref_edges[tuple(sorted([n1, n2]))] = {
                    "count": len(overlap),
                    "top_ids": top_ids,
                }

    # Shared topics
    topic_sets = {}
    for fac in openalex_data:
        if fac["name"] in BAD:
            continue
        topics = set()
        for t in fac.get("topics", []):
            topics.add(t["name"])
        for w in fac.get("works", [])[:30]:
            if w.get("primary_topic"):
                topics.add(w["primary_topic"])
        if topics:
            topic_sets[fac["name"]] = topics

    shared_topic_edges = {}
    names = list(topic_sets.keys())
    for i, n1 in enumerate(names):
        for n2 in names[i+1:]:
            overlap = topic_sets[n1] & topic_sets[n2]
            if len(overlap) >= 2:
                shared_topic_edges[tuple(sorted([n1, n2]))] = {
                    "count": len(overlap),
                    "names": list(overlap)[:10],
                }

    # Shared journals (excluding preprint servers and repositories)
    NOT_JOURNALS = {
        # Preprint servers / repositories
        "SSRN Electronic Journal",
        "arXiv (Cornell University)",
        "Harvard Dataverse",
        "Figshare",
        "PubMed",
        "Europe PMC (PubMed Central)",
        "RePEc: Research Papers in Economics",
        "ICPSR Data Holdings",
        "Zenodo (CERN European Organization for Nuclear Research)",
        "Deep Blue (University of Michigan)",
        "eCommons (Cornell University)",
        "HAL (Le Centre pour la Communication Scientifique Directe)",
        "Research Square (Research Square)",
        # Generic publisher imprints / series
        "Oxford University Press eBooks",
        "Cambridge University Press eBooks",
        "Lecture notes in computer science",
        "DH",
    }
    journal_sets = {}
    for fac in openalex_data:
        if fac["name"] in BAD:
            continue
        journals = set()
        for w in fac.get("works", []):
            if w.get("journal") and w["journal"] not in NOT_JOURNALS:
                journals.add(w["journal"])
        if journals:
            journal_sets[fac["name"]] = journals

    shared_journal_edges = {}
    names = list(journal_sets.keys())
    for i, n1 in enumerate(names):
        for n2 in names[i+1:]:
            overlap = journal_sets[n1] & journal_sets[n2]
            if len(overlap) >= 2:
                shared_journal_edges[tuple(sorted([n1, n2]))] = {
                    "count": len(overlap),
                    "names": list(overlap)[:10],
                }

    return coauthor_edges, shared_ref_edges, shared_topic_edges, shared_journal_edges


def main():
    scholar_data, openalex_data = load_data()

    # Index Scholar data by name
    scholar_by_name = {s["name"]: s for s in scholar_data}

    # Build edges
    print("Building edges...")
    scholar_coauth = build_scholar_coauthor_edges(scholar_data)
    oa_coauth, shared_refs, shared_topics, shared_journals = build_openalex_edges(openalex_data)

    # Website co-authorships (from scrape_websites.py)
    import os
    website_coauth = {}
    if os.path.exists("data/website_papers.json"):
        with open("data/website_papers.json") as f:
            for entry in json.load(f):
                key = tuple(sorted([entry["source"], entry["target"]]))
                website_coauth[key] = True

    print(f"  Scholar co-author edges: {len(scholar_coauth)}")
    print(f"  OpenAlex co-author edges: {len(oa_coauth)}")
    print(f"  Website co-author edges: {len(website_coauth)}")
    print(f"  Shared reference edges: {len(shared_refs)}")
    print(f"  Shared topic edges: {len(shared_topics)}")
    print(f"  Shared journal edges: {len(shared_journals)}")

    # Build nodes from all faculty
    all_names = set(MANUAL_AREAS.keys())
    oa_by_name = {f["name"]: f for f in openalex_data}
    nodes = []
    for name in sorted(all_names):
        s = scholar_by_name.get(name, {})
        oa = oa_by_name.get(name, {})
        areas = compute_area_distribution(name, oa, s)

        # Recent publications (sorted by year, newest first, deduplicated)
        top_pubs = []
        seen_titles = set()
        if oa and oa.get("works"):
            sorted_works = sorted(oa["works"], key=lambda w: w.get("year") or 0, reverse=True)
            for w in sorted_works:
                if w.get("title") and w["title"] not in seen_titles:
                    seen_titles.add(w["title"])
                    top_pubs.append({
                        "title": w["title"],
                        "year": w.get("year"),
                    })
                    if len(top_pubs) >= 10:
                        break

        nodes.append({
            "id": name,
            "scholar_id": s.get("scholar_id"),
            "website": FACULTY_WEBSITES.get(name),
            "citedby": s.get("citedby", 0),
            "hindex": s.get("hindex", 0),
            "interests": s.get("interests", []),
            "areas": areas,
            "primary_area": areas[0]["area"] if areas else "Other",
            "has_profile": bool(s.get("scholar_id") and "error" not in s),
            "top_pubs": top_pubs,
        })

    # Combine all edge keys
    all_keys = set()
    all_keys.update(scholar_coauth.keys())
    all_keys.update(oa_coauth.keys())
    all_keys.update(website_coauth.keys())
    all_keys.update(shared_refs.keys())
    all_keys.update(shared_topics.keys())
    all_keys.update(shared_journals.keys())

    edges = []
    for key in all_keys:
        n1, n2 = key
        if n1 not in all_names or n2 not in all_names:
            continue

        edge = {"source": n1, "target": n2}

        # Scholar co-author (listed on profile)
        if key in scholar_coauth:
            edge["scholar_coauthor"] = True

        # Website co-author (found on personal research pages)
        if key in website_coauth:
            edge["website_coauthor"] = True

        # OpenAlex co-author (found in paper data)
        if key in oa_coauth:
            edge["coauthor_count"] = oa_coauth[key]["count"]
            edge["coauthor_papers"] = oa_coauth[key]["papers"]

        if key in shared_refs:
            edge["shared_refs"] = shared_refs[key]["count"]
            edge["shared_ref_ids"] = shared_refs[key]["top_ids"]

        if key in shared_topics:
            edge["shared_topics"] = shared_topics[key]["count"]
            edge["shared_topic_names"] = shared_topics[key]["names"]

        if key in shared_journals:
            edge["shared_journals"] = shared_journals[key]["count"]
            edge["shared_journal_names"] = shared_journals[key]["names"]

        # Composite weight
        w = 0
        if edge.get("coauthor_count"):
            w += edge["coauthor_count"] * 10
        if edge.get("scholar_coauthor") and not edge.get("coauthor_count"):
            w += 15  # Listed as co-author on Scholar but no papers found in OA
        if edge.get("website_coauthor") and not edge.get("coauthor_count"):
            w += 15  # Listed as co-author on personal website
        w += min(edge.get("shared_refs", 0), 50)
        w += edge.get("shared_topics", 0) * 2
        w += edge.get("shared_journals", 0) * 1.5
        edge["weight"] = round(w, 1)

        if edge["weight"] > 0:
            edges.append(edge)

    edges.sort(key=lambda e: e["weight"], reverse=True)

    graph = {"nodes": nodes, "edges": edges}
    with open("data/graph.json", "w") as f:
        json.dump(graph, f, indent=2)

    print(f"\nGraph: {len(nodes)} nodes, {len(edges)} edges")

    print(f"\nTop 20 edges:")
    for e in edges[:20]:
        types = []
        if e.get("scholar_coauthor"): types.append("scholar-coauth")
        if e.get("coauthor_count"): types.append(f"papers={e['coauthor_count']}")
        if e.get("shared_refs"): types.append(f"refs={e['shared_refs']}")
        if e.get("shared_topics"): types.append(f"topics={e['shared_topics']}")
        if e.get("shared_journals"): types.append(f"journals={e['shared_journals']}")
        print(f"  {e['source']:28s} <-> {e['target']:28s}  "
              f"w={e['weight']:6.1f}  ({', '.join(types)})")

    print(f"\nArea distributions:")
    for n in sorted(nodes, key=lambda x: x["primary_area"]):
        areas_str = " + ".join(f"{a['area']}({a['share']:.0%})" for a in n["areas"])
        print(f"  {n['id']:28s}  {areas_str}")

    # Show Scholar vs OpenAlex citation comparison
    print(f"\nCitation comparison (Scholar vs OpenAlex):")
    for n in sorted(nodes, key=lambda x: x["citedby"], reverse=True):
        oa = oa_by_name.get(n["id"], {})
        oa_cite = oa.get("cited_by_count", 0)
        sc_cite = n["citedby"]
        ratio = f"{sc_cite/oa_cite:.1f}x" if oa_cite > 0 else "N/A"
        print(f"  {n['id']:28s}  Scholar={sc_cite:>6d}  OA={oa_cite:>6d}  ({ratio})")


if __name__ == "__main__":
    main()
