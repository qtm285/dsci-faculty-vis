# DSCI Faculty Research Network — Notes

## How it works

### Data sources

1. **Google Scholar** (primary for citation metrics)
   - `collect_scholar.py` uses the `scholarly` library to pull profiles
   - Scholar IDs stored in `data/scholar.json`
   - Gets: citation count, h-index, research interests, co-author lists
   - Rate-limited aggressively by Google — sometimes fails mid-run

2. **OpenAlex API** (primary for relational data)
   - `collect_data.py` pulls author profiles and full works metadata
   - Gets: publications, co-authorships, topics, journals, referenced works
   - Free, no auth needed, generous rate limits with polite pool
   - Author disambiguation is unreliable for common names — we manually override IDs for Tolbert, Hoffmann, Di Iorio in `AUTHOR_ID_OVERRIDES`
   - Known bad matches we skip entirely: Ho Jin Kim, Kevin McAlister

3. **Faculty websites** (supplementary)
   - `scrape_websites.py` scrapes personal research pages for intra-department co-authorships
   - Catches working papers and collaborations not yet in OpenAlex
   - Can't scrape JS-rendered sites (Google Sites) — those were checked manually
   - Results in `data/website_papers.json` (partially hand-curated)

### Pipeline

```
collect_scholar.py  →  data/scholar.json
collect_data.py     →  data/faculty.json
                           ↓
build_graph2.py     →  data/graph.json  (merges both + website_papers.json)
                           ↓
resolve_refs.py     →  data/graph.json  (adds resolved shared reference titles)
                           ↓
index.html / index-dept.html  (reads graph.json, renders with D3)
```

### Edge weighting

Edges between faculty are composite scores:
- Co-authored papers: `count × 10`
- Listed as co-author on Scholar profile (no papers found): `+15`
- Listed as co-author on personal website (no papers found): `+15`
- Shared references: `min(count, 50)` (capped to prevent high-volume citers from dominating)
- Shared topics: `count × 2`
- Shared journals: `count × 1.5`

Journals exclude preprint servers (SSRN, arXiv, Harvard Dataverse) and generic publisher imprints (Oxford UP eBooks, Cambridge UP eBooks, etc.) — see `NOT_JOURNALS` in `build_graph2.py`.

Shared references require a minimum overlap of 3 to create an edge.

### Visualization

- D3 force-directed graph
- Concentric ring nodes: each ring's area proportional to that research area's share
- Node size scaled by citation count
- Three versions:
  - `index.html` — dark theme, all controls
  - `index-dept.html` — light theme with Emory brand colors
  - `index-dept.html?embed` — stripped-down for iframe embedding (no header, no controls, transparent bg, scaled-down legend/tooltips, auto-fit zoom)
- Interactions: hover for tooltip, click for detail panel (node or edge), click again to close, legend filters by area (multi-select)

## Known issues

- **OpenAlex undercounts citations** by 1.3x–5.8x vs Google Scholar. We don't display per-paper citation counts for this reason — only Scholar's aggregate counts.
- **OpenAlex author disambiguation** is wrong for Ho Jin Kim (matched to an oncologist, 966 works) and Kevin McAlister (matched to a physicist, 143 works). These are in the `BAD` set and excluded from edge computation.
- **Jacopo Di Iorio** has correct OpenAlex data but his research (data mining, time series, COVID epi) doesn't overlap enough with other DSCI faculty to generate edges above the shared-refs threshold of 3.
- **Force layout is nondeterministic** — positions vary on each reload. The embed auto-fits zoom to the bounding box after 2 seconds.

## TODOs

- [ ] Get Google Scholar pages/citation counts for **Zhiyun Gong** and **Ho Jin Kim** (Skip will ask them directly)
- [ ] Get personal website URLs for **Ho Jin Kim** and **Zhiyun Gong**
- [ ] Find correct OpenAlex IDs for **Ho Jin Kim** and **Kevin McAlister** (or accept they'll use Scholar-only data)
- [ ] **Di Iorio**: lower the shared-refs threshold from 3 to 2, or add his website for co-authorship scraping, to get him connected
- [ ] Consider adding **Semantic Scholar** as a third data source (better disambiguation than OpenAlex for some names)
- [ ] Periodic data refresh — Scholar profiles and OpenAlex works go stale
- [ ] Integrate embed into actual department website (quantitative.emory.edu/research/)

## Possible improvements

- **Search/filter by name** — type to find a specific faculty member
- **Pin layout** — save node positions so the graph is deterministic across loads
- **Time dimension** — filter by publication year range to see how the network evolved
- **External collaborators** — show connections to frequent co-authors outside the department (grayed out nodes at periphery)
- **Cluster by area** — option to force nodes into area-based clusters instead of pure force layout
- **Mobile responsiveness** — the embed works but the detail panel needs work on narrow screens
