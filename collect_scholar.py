"""
Collect Google Scholar profile data for Emory DSCI faculty.
Uses scholarly library with known Scholar IDs.
Outputs: data/scholar.json
"""

import json
import time
from scholarly import scholarly

# Google Scholar IDs found via web search
SCHOLAR_IDS = {
    "Maggie Penn": "89dfQFsAAAAJ",
    "John W. Patty": "zEq533oAAAAJ",
    "Jinho Choi": "xdddblAAAAAJ",
    "Kevin Quinn": "XD8LHcgAAAAJ",
    "Ruoxuan Xiong": "lg_0u-0AAAAJ",
    "Gordon Berman": "rPGn0XYAAAAJ",
    "Craig Hadley": "lTDtAqoAAAAJ",
    "Sandeep Soni": "_OzUlMkAAAAJ",
    "Jo Guldi": "JnRNZccAAAAJ",
    "Zachary Peskowitz": "WyrU5sUAAAAJ",
    "Heeju Sohn": "ahSqKzIAAAAJ",
    "Lauren Klein": "Xc9Sco0AAAAJ",
    "Clifford Carrubba": "o-L0yxsAAAAJ",
    "Adam Glynn": "30u0V1EAAAAJ",
    "Weihua An": "zvOPm8gAAAAJ",
    "Pablo Montagnes": "dk_JiwgAAAAJ",
    "Danilo Freire": "9s1slLcAAAAJ",
    "Luis Martinez": "OBUGAFgAAAAJ",
    "Hun Chung": "9zsMl5kAAAAJ",
    "Michal Arbilly": "U_xI7eAAAAAJ",
    "Zachary Binney": "96zZFSMAAAAJ",
    "Nathan Hoffmann": "ZmjDUAMAAAAJ",
    "Dan Sinykin": "zfFwj6sAAAAJ",
    "Allison Stashko": "J4NQQIEAAAAJ",
    "Gregory Palermo": "rhSQ6egAAAAJ",
    "Jacopo Di Iorio": "LB9hecMAAAAJ",
    "Alejandro Sanchez Becerra": "yFPu-mkAAAAJ",
    "Zhiyun Gong": "DZPv_WIAAAAJ",
    "Alexander Tolbert": "OGjoFXcAAAAJ",
}

# Faculty without Scholar profiles found
NO_PROFILE = [
    "David Hirshberg",
    "Ho Jin Kim",
    "Kevin McAlister",
    "Benjamin J. Miller",
    "Megan Reed",
    "Abhishek Ananth",
]


def fetch_profile(name, scholar_id):
    """Fetch a Google Scholar profile by ID."""
    try:
        author = scholarly.search_author_id(scholar_id)
        # Fill in details (co-authors, etc.)
        author = scholarly.fill(author, sections=["basics", "indices", "counts",
                                                   "coauthors", "interests"])
        return {
            "name": name,
            "scholar_id": scholar_id,
            "scholar_name": author.get("name", ""),
            "affiliation": author.get("affiliation", ""),
            "interests": author.get("interests", []),
            "citedby": author.get("citedby", 0),
            "hindex": author.get("hindex", 0),
            "i10index": author.get("i10index", 0),
            "coauthors": [
                {
                    "name": ca.get("name", ""),
                    "scholar_id": ca.get("scholar_id", ""),
                    "affiliation": ca.get("affiliation", ""),
                }
                for ca in author.get("coauthors", [])
            ],
            "cites_per_year": author.get("cites_per_year", {}),
        }
    except Exception as e:
        print(f"  ERROR: {e}")
        return {
            "name": name,
            "scholar_id": scholar_id,
            "error": str(e),
        }


def main():
    results = []
    total = len(SCHOLAR_IDS)

    for i, (name, sid) in enumerate(SCHOLAR_IDS.items()):
        print(f"[{i+1}/{total}] Fetching {name} ({sid})...")
        profile = fetch_profile(name, sid)
        if "error" not in profile:
            print(f"  {profile['scholar_name']} — "
                  f"{profile['citedby']} citations, "
                  f"h={profile['hindex']}, "
                  f"{len(profile['coauthors'])} coauthors")
        results.append(profile)
        time.sleep(2)  # Be respectful

    # Add entries for faculty without profiles
    for name in NO_PROFILE:
        results.append({
            "name": name,
            "scholar_id": None,
            "no_profile": True,
        })

    with open("data/scholar.json", "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nSaved {len(results)} records to data/scholar.json")
    found = sum(1 for r in results if "error" not in r and not r.get("no_profile"))
    print(f"Successfully fetched: {found}/{total}")


if __name__ == "__main__":
    main()
