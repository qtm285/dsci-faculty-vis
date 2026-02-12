"""
Scrape faculty research pages for intra-department working papers.
Looks for papers where co-authors include other DSCI faculty.
Outputs data/website_papers.json.
"""

import json
import re
import time
import urllib.request
from html.parser import HTMLParser

# Faculty name -> research page URL
RESEARCH_PAGES = {}  # filled in after agent results come back

# All DSCI faculty names (for matching co-authors)
ALL_NAMES = set()


class TextExtractor(HTMLParser):
    """Extract visible text from HTML."""
    def __init__(self):
        super().__init__()
        self.text_parts = []
        self._skip = False
        self._skip_tags = {"script", "style", "noscript"}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.text_parts.append(data)

    def get_text(self):
        return " ".join(self.text_parts)


def fetch_page(url):
    """Fetch a URL and return the text content."""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                          "AppleWebKit/537.36 (KHTML, like Gecko) "
                          "Chrome/120.0.0.0 Safari/537.36"
        })
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode("utf-8", errors="replace")
        extractor = TextExtractor()
        extractor.feed(html)
        return extractor.get_text()
    except Exception as e:
        print(f"  Error fetching {url}: {e}")
        return ""


def name_variants(name):
    """Generate plausible variants of a name for matching."""
    parts = name.split()
    variants = {name}  # full name

    if len(parts) == 2:
        first, last = parts
        variants.add(f"{first} {last}")
        variants.add(f"{first[0]}. {last}")
        # Handle "J." style initials
        if len(first) > 1:
            variants.add(f"{first[0]}. {last}")
    elif len(parts) == 3:
        # e.g. "John W. Patty", "Alejandro Sanchez Becerra", "Benjamin J. Miller"
        variants.add(f"{parts[0]} {parts[2]}")  # first + last
        variants.add(f"{parts[0][0]}. {parts[2]}")  # F. Last
        variants.add(f"{parts[0]} {parts[1]} {parts[2]}")
        # "Sanchez Becerra" as a unit
        variants.add(f"{parts[1]} {parts[2]}")

    return variants


def find_coauthors_in_text(text, page_owner):
    """Find other DSCI faculty names mentioned in the page text."""
    found = {}
    for name in ALL_NAMES:
        if name == page_owner:
            continue
        for variant in name_variants(name):
            if variant in text:
                found[name] = True
                break
    return list(found.keys())


def extract_papers_near_name(text, coauthor_name):
    """Try to find paper titles near where a coauthor name appears.

    Heuristic: look for text that looks like a paper title
    in the vicinity of the coauthor's name.
    """
    papers = []
    for variant in name_variants(coauthor_name):
        for match in re.finditer(re.escape(variant), text):
            # Get a window of ~500 chars before and after
            start = max(0, match.start() - 500)
            end = min(len(text), match.end() + 500)
            window = text[start:end]

            # Look for things in quotes or bold-like patterns
            # Also look for lines that seem like titles (capitalized, 5+ words)
            for line in window.split("\n"):
                line = line.strip()
                # Skip very short or very long lines
                if len(line) < 20 or len(line) > 300:
                    continue
                # Skip lines that are clearly not titles
                if line.startswith("http") or line.startswith("@"):
                    continue
                # Heuristic: title-like if it has several capitalized words
                words = line.split()
                if len(words) >= 4:
                    papers.append(line)

    return papers


def main():
    global ALL_NAMES, RESEARCH_PAGES

    # Load faculty names
    with open("data/graph.json") as f:
        graph = json.load(f)
    ALL_NAMES = {n["id"] for n in graph["nodes"]}

    # Research page URLs — manually curated
    RESEARCH_PAGES = {
        "Weihua An": "https://www.weihuaan.net/research",
        "Adam Glynn": "https://www.adamnglynn.com/publications",
        "John W. Patty": "https://www.johnwpatty.net/research/",
        "Maggie Penn": "https://www.elizabethmpenn.com/?page_id=22",
        "Hun Chung": "https://sites.google.com/site/hunchung1980/research",
        "Lauren Klein": "https://lklein.com/research/",
        "Sandeep Soni": "https://sandeepsoni.github.io/publications",
        "Alexander Tolbert": "https://www.alexanderwilliamstolbert.com/",
        "Benjamin J. Miller": "https://benmiller.mit.edu/about/publications/",
        "Jo Guldi": "https://www.joguldi.com/articles",
        "David Hirshberg": "https://davidahirshberg.bitbucket.io/",
        "Ruoxuan Xiong": "https://www.ruoxuanxiong.com/",
        "Allison Stashko": "https://sites.google.com/view/allisonstashko/research",
        "Luis Martinez": "https://sites.google.com/site/lrmartineza",
        "Pablo Montagnes": "https://www.pablomontagnes.com/",
        "Zachary Peskowitz": "https://www.zacharypeskowitz.com/",
        "Zachary Binney": "https://zachbinney.com/research.html",
        "Gordon Berman": "https://faculty.college.emory.edu/sites/berman/publications.html",
        "Michal Arbilly": "https://michalarbilly.com/publications/",
        "Jinho Choi": "https://www.emorynlp.org/publications-1",
        "Danilo Freire": "https://danilofreire.github.io/dist/index.html",
        "Alejandro Sanchez Becerra": "https://sites.google.com/site/sanchezbecerraalejandro/research",
        "Gregory Palermo": "http://gregorypalermo.org/research/",
        "Dan Sinykin": "http://www.dansinykin.com/publications.html",
        "Nathan Hoffmann": "https://nathanhoffmann.com/research-2/",
        "Heeju Sohn": "https://www.heejusohn.com/publications/",
        "Megan Reed": "https://sites.google.com/view/meganreed/research",
        "Abhishek Ananth": "https://abhiananthecon.github.io/research/",
        "Kevin McAlister": "http://www.kevinmcalister.org/research.html",
    }

    # Scrape and find co-authorships
    edges = {}  # (name1, name2) -> [paper_titles]

    for name, url in RESEARCH_PAGES.items():
        print(f"Fetching {name}...")
        text = fetch_page(url)
        if not text:
            continue

        coauthors = find_coauthors_in_text(text, name)
        if coauthors:
            print(f"  Found department co-authors: {', '.join(coauthors)}")
            for ca in coauthors:
                key = tuple(sorted([name, ca]))
                if key not in edges:
                    edges[key] = {"source": key[0], "target": key[1], "found_on": []}
                edges[key]["found_on"].append(name)

        time.sleep(0.3)

    # Output
    results = list(edges.values())
    results.sort(key=lambda x: (x["source"], x["target"]))

    with open("data/website_papers.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nFound {len(results)} intra-department collaborations from websites:")
    for r in results:
        print(f"  {r['source']} <-> {r['target']}  (found on: {', '.join(r['found_on'])})")


if __name__ == "__main__":
    main()
