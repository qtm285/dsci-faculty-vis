"""
Build the faculty research-interest graph from collected OpenAlex data.
Outputs: data/graph.json (nodes + edges for visualization)
"""

import json
from collections import Counter, defaultdict
from itertools import combinations

# Bad OpenAlex matches to exclude (wrong person entirely)
BAD_MATCHES = {
    "Ho Jin Kim",       # matched to Keunchil Park (oncologist)
    "Kevin McAlister",  # matched to Y. Musienko (physicist)
    "Alexander Tolbert",  # matched to Avrim Blum
}

# Suspicious matches to flag but keep with reduced confidence
SUSPECT = {
    "Adam Glynn",       # 341 works seems high — could be merged profiles
    "Zhiyun Gong",      # 94 works, 2361 citations — verify
    "Benjamin J. Miller",  # 139 works — might be wrong Ben Miller
    "Megan Reed",       # could be wrong Megan Reed
    "Nathan Hoffmann",  # 23 works, 1272 citations — check
}


def load_faculty():
    with open("data/faculty.json") as f:
        data = json.load(f)
    # Filter out bad matches
    clean = []
    for fac in data:
        if fac["name"] in BAD_MATCHES:
            fac["openalex_id"] = None
            fac["works"] = []
            fac["works_count"] = 0
            fac["topics"] = []
        clean.append(fac)
    return clean


def build_author_index(faculty):
    """Map OpenAlex author IDs to faculty names."""
    idx = {}
    for fac in faculty:
        if fac["openalex_id"]:
            idx[fac["openalex_id"]] = fac["name"]
    return idx


def find_coauthor_edges(faculty, author_index):
    """Find edges where two faculty members co-authored a paper."""
    edges = defaultdict(lambda: {"coauthor": 0, "papers": []})

    for fac in faculty:
        if not fac["openalex_id"]:
            continue
        for work in fac["works"]:
            # Check if any co-author is also in our faculty list
            work_author_ids = [a["id"] for a in work["authors"]]
            faculty_coauthors = [
                author_index[aid]
                for aid in work_author_ids
                if aid in author_index and author_index[aid] != fac["name"]
            ]
            for coauthor_name in faculty_coauthors:
                key = tuple(sorted([fac["name"], coauthor_name]))
                edges[key]["coauthor"] += 1
                if work["title"] not in edges[key]["papers"]:
                    edges[key]["papers"].append(work["title"])

    # Deduplicate (each paper counted from both sides)
    for key in edges:
        edges[key]["coauthor"] = (edges[key]["coauthor"] + 1) // 2
        seen = set()
        deduped = []
        for p in edges[key]["papers"]:
            if p not in seen:
                seen.add(p)
                deduped.append(p)
        edges[key]["papers"] = deduped

    return edges


def find_shared_reference_edges(faculty):
    """Find edges based on shared cited references."""
    # Build: faculty_name -> set of referenced work IDs
    ref_sets = {}
    for fac in faculty:
        if not fac["works"]:
            continue
        refs = set()
        for work in fac["works"]:
            refs.update(work.get("referenced_works", []))
        if refs:
            ref_sets[fac["name"]] = refs

    edges = {}
    names = list(ref_sets.keys())
    for i, n1 in enumerate(names):
        for n2 in names[i + 1:]:
            overlap = ref_sets[n1] & ref_sets[n2]
            if len(overlap) >= 3:  # threshold: at least 3 shared refs
                key = tuple(sorted([n1, n2]))
                edges[key] = len(overlap)

    return edges


def find_shared_topic_edges(faculty):
    """Find edges based on shared OpenAlex topics."""
    # Build: faculty_name -> set of topic names
    topic_sets = {}
    for fac in faculty:
        topics = set()
        for t in fac.get("topics", []):
            topics.add(t["name"])
        for work in fac.get("works", []):
            if work.get("primary_topic"):
                topics.add(work["primary_topic"])
        if topics:
            topic_sets[fac["name"]] = topics

    edges = {}
    names = list(topic_sets.keys())
    for i, n1 in enumerate(names):
        for n2 in names[i + 1:]:
            overlap = topic_sets[n1] & topic_sets[n2]
            if len(overlap) >= 2:  # threshold: at least 2 shared topics
                key = tuple(sorted([n1, n2]))
                edges[key] = {
                    "count": len(overlap),
                    "topics": list(overlap)[:10],
                }

    return edges


def find_shared_journal_edges(faculty):
    """Find edges based on publishing in the same journals."""
    journal_sets = {}
    for fac in faculty:
        journals = set()
        for work in fac.get("works", []):
            if work.get("journal"):
                journals.add(work["journal"])
        if journals:
            journal_sets[fac["name"]] = journals

    edges = {}
    names = list(journal_sets.keys())
    for i, n1 in enumerate(names):
        for n2 in names[i + 1:]:
            overlap = journal_sets[n1] & journal_sets[n2]
            if len(overlap) >= 2:
                key = tuple(sorted([n1, n2]))
                edges[key] = {
                    "count": len(overlap),
                    "journals": list(overlap)[:10],
                }

    return edges


def assign_clusters(faculty):
    """Assign research area clusters based on top topics."""
    # Collect all primary topics and cluster manually based on common themes
    cluster_keywords = {
        "Political Science": ["political", "politic", "election", "voting",
                              "legislative", "congress", "democrat", "governance"],
        "NLP / Computational": ["natural language", "nlp", "computational linguist",
                                "text mining", "sentiment", "machine learning",
                                "artificial intelligence", "deep learning",
                                "information retrieval"],
        "Statistics / Causal Inference": ["causal", "statistic", "bayesian",
                                          "econometric", "regression",
                                          "inference", "estimation"],
        "Digital Humanities": ["digital humanit", "humanities", "literary",
                               "cultural", "history"],
        "Biology / Neuroscience": ["biolog", "neuro", "animal", "behavio",
                                   "ecolog", "brain", "genome"],
        "Sociology / Public Health": ["sociolog", "health", "epidemiol",
                                      "inequality", "immigra", "food",
                                      "nutrition", "anthropol"],
    }

    assignments = {}
    for fac in faculty:
        topic_text = " ".join(
            t["name"].lower() for t in fac.get("topics", [])
        )
        # Also include concepts from works
        for work in fac.get("works", [])[:20]:
            topic_text += " " + " ".join(
                c["name"].lower() for c in work.get("concepts", [])
            )

        best_cluster = "Other"
        best_score = 0
        for cluster, keywords in cluster_keywords.items():
            score = sum(1 for kw in keywords if kw in topic_text)
            if score > best_score:
                best_score = score
                best_cluster = cluster

        assignments[fac["name"]] = best_cluster

    return assignments


def main():
    faculty = load_faculty()
    author_index = build_author_index(faculty)

    print("Building edges...")
    coauthor_edges = find_coauthor_edges(faculty, author_index)
    shared_ref_edges = find_shared_reference_edges(faculty)
    shared_topic_edges = find_shared_topic_edges(faculty)
    shared_journal_edges = find_shared_journal_edges(faculty)

    print(f"  Co-author edges: {len(coauthor_edges)}")
    print(f"  Shared reference edges (>=3): {len(shared_ref_edges)}")
    print(f"  Shared topic edges (>=2): {len(shared_topic_edges)}")
    print(f"  Shared journal edges (>=2): {len(shared_journal_edges)}")

    # Assign clusters
    clusters = assign_clusters(faculty)

    # Build combined graph
    nodes = []
    for fac in faculty:
        nodes.append({
            "id": fac["name"],
            "openalex_id": fac["openalex_id"],
            "works_count": fac["works_count"],
            "cited_by_count": fac["cited_by_count"],
            "cluster": clusters.get(fac["name"], "Other"),
            "top_topics": [t["name"] for t in fac.get("topics", [])[:5]],
            "suspect_match": fac["name"] in SUSPECT,
        })

    # Combine all edge types
    all_edge_keys = set()
    all_edge_keys.update(coauthor_edges.keys())
    all_edge_keys.update(shared_ref_edges.keys())
    all_edge_keys.update(shared_topic_edges.keys())
    all_edge_keys.update(shared_journal_edges.keys())

    edges = []
    for key in all_edge_keys:
        n1, n2 = key
        edge = {"source": n1, "target": n2}

        # Co-author weight (strongest signal)
        if key in coauthor_edges:
            edge["coauthor_count"] = coauthor_edges[key]["coauthor"]
            edge["coauthor_papers"] = coauthor_edges[key]["papers"]

        # Shared references
        if key in shared_ref_edges:
            edge["shared_refs"] = shared_ref_edges[key]

        # Shared topics
        if key in shared_topic_edges:
            edge["shared_topics"] = shared_topic_edges[key]["count"]
            edge["shared_topic_names"] = shared_topic_edges[key]["topics"]

        # Shared journals
        if key in shared_journal_edges:
            edge["shared_journals"] = shared_journal_edges[key]["count"]
            edge["shared_journal_names"] = shared_journal_edges[key]["journals"]

        # Composite weight
        w = 0
        w += edge.get("coauthor_count", 0) * 10  # co-authorship strongest
        w += min(edge.get("shared_refs", 0), 50)  # cap refs contribution
        w += edge.get("shared_topics", 0) * 2
        w += edge.get("shared_journals", 0) * 1.5
        edge["weight"] = round(w, 1)

        edges.append(edge)

    # Sort by weight descending
    edges.sort(key=lambda e: e["weight"], reverse=True)

    graph = {"nodes": nodes, "edges": edges}

    with open("data/graph.json", "w") as f:
        json.dump(graph, f, indent=2)

    print(f"\nGraph: {len(nodes)} nodes, {len(edges)} edges")
    print(f"\nTop 20 edges by weight:")
    for e in edges[:20]:
        types = []
        if e.get("coauthor_count"):
            types.append(f"coauth={e['coauthor_count']}")
        if e.get("shared_refs"):
            types.append(f"refs={e['shared_refs']}")
        if e.get("shared_topics"):
            types.append(f"topics={e['shared_topics']}")
        if e.get("shared_journals"):
            types.append(f"journals={e['shared_journals']}")
        print(f"  {e['source']:25s} <-> {e['target']:25s}  "
              f"w={e['weight']:6.1f}  ({', '.join(types)})")

    print(f"\nCluster distribution:")
    cluster_counts = Counter(clusters.values())
    for cluster, count in cluster_counts.most_common():
        print(f"  {cluster}: {count}")
        members = [n for n, c in clusters.items() if c == cluster]
        for m in sorted(members):
            print(f"    - {m}")


if __name__ == "__main__":
    main()
