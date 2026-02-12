"""
Resolve shared reference IDs to titles via OpenAlex API.
Reads graph.json, batch-resolves the shared_ref_ids on each edge,
writes resolved titles back as shared_ref_papers.
Run after build_graph2.py.
"""

import json
import time
import urllib.request
import urllib.parse


def batch_resolve(work_ids, batch_size=50):
    """Resolve OpenAlex work IDs to {id, title, year, authors} in batches."""
    resolved = {}
    batches = [work_ids[i:i+batch_size] for i in range(0, len(work_ids), batch_size)]
    print(f"Resolving {len(work_ids)} refs in {len(batches)} batches...")

    for i, batch in enumerate(batches):
        # Strip URL prefix to get bare IDs for the filter
        bare_ids = [wid.replace("https://openalex.org/", "") for wid in batch]
        filter_val = "|".join(bare_ids)
        url = (
            f"https://api.openalex.org/works?"
            f"filter=openalex:{urllib.parse.quote(filter_val)}"
            f"&select=id,title,publication_year,authorships"
            f"&per_page={batch_size}"
        )

        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "DSCIFacultyVis/1.0 (mailto:skip@emory.edu)"
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode())

            for work in data.get("results", []):
                wid = work["id"]
                authors = []
                for auth in work.get("authorships", [])[:3]:
                    name = auth.get("author", {}).get("display_name")
                    if name:
                        authors.append(name)
                if len(work.get("authorships", [])) > 3:
                    authors.append("et al.")

                resolved[wid] = {
                    "title": work.get("title", ""),
                    "year": work.get("publication_year"),
                    "authors": authors,
                }

            print(f"  Batch {i+1}/{len(batches)}: got {len(data.get('results', []))} results")
        except Exception as e:
            print(f"  Batch {i+1}/{len(batches)}: ERROR {e}")

        if i < len(batches) - 1:
            time.sleep(0.2)  # polite rate limiting

    return resolved


def main():
    with open("data/graph.json") as f:
        graph = json.load(f)

    # Collect all unique ref IDs
    all_ids = set()
    for edge in graph["edges"]:
        for rid in edge.get("shared_ref_ids", []):
            all_ids.add(rid)

    if not all_ids:
        print("No shared_ref_ids to resolve.")
        return

    # Batch resolve
    resolved = batch_resolve(sorted(all_ids))
    print(f"\nResolved {len(resolved)} / {len(all_ids)} refs")

    # Write resolved titles back to edges
    for edge in graph["edges"]:
        ref_ids = edge.get("shared_ref_ids", [])
        if not ref_ids:
            continue

        papers = []
        for rid in ref_ids:
            if rid in resolved:
                papers.append(resolved[rid])

        if papers:
            edge["shared_ref_papers"] = papers

        # Remove raw IDs — no longer needed in the output
        if "shared_ref_ids" in edge:
            del edge["shared_ref_ids"]

    with open("data/graph.json", "w") as f:
        json.dump(graph, f, indent=2)

    # Stats
    edges_with = sum(1 for e in graph["edges"] if e.get("shared_ref_papers"))
    total_papers = sum(len(e.get("shared_ref_papers", [])) for e in graph["edges"])
    print(f"Wrote {total_papers} resolved papers across {edges_with} edges")


if __name__ == "__main__":
    main()
