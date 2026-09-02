#!/usr/bin/env python3
"""Convert example/scripture-sets.tsv into templates/DBS/source/story.txt
plus templates/DBS/locales/eng.toml.

One-off/rerunnable ingestion script for the DBS template (Discover App:
Scripture sets). Run again if scripture-sets.tsv changes; it fully
regenerates both output files.

Usage:
    python scripts/build_dbs_source.py
"""

import csv
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pythonbible as bible  # noqa: E402
from generate_stories import parse_ref_string  # noqa: E402  (validates each run parses)

REPO_ROOT = Path(__file__).resolve().parent.parent
TSV_PATH = REPO_ROOT / "example" / "scripture-sets.tsv"
STORY_TXT_PATH = REPO_ROOT / "templates" / "DBS" / "source" / "story.txt"
ENG_TOML_PATH = REPO_ROOT / "templates" / "DBS" / "locales" / "eng.toml"

# Known typos in the source TSV, fixed here rather than silently guessed
# downstream. Keep this list short and explicit.
TITLE_FIXES = {}
REF_FIXES = {
    "Galations4:4-5": "Galatians 4:4-5",
}


def toml_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"')


def split_into_book_runs(ref_str: str):
    """Split a ';'-joined reference string into runs that each name one book.

    A part that starts with a letter names a new book; a part that starts
    with a digit is a chapter:verse continuation of the current book run
    (pythonbible/parse_ref_string already understands that within a run).

    "Luke 10:25-37; 15:11-32" -> ["Luke 10:25-37; 15:11-32"]              (1 run)
    "Matthew 3; John 1:29-34" -> ["Matthew 3", "John 1:29-34"]            (2 runs)
    "Matthew 18:20; Hebrews 10:24-25; Acts 2:36-47" -> 3 runs
    """
    ref_str = REF_FIXES.get(ref_str, ref_str)
    parts = [p.strip() for p in ref_str.split(";")]
    runs = []
    current = []
    for part in parts:
        starts_new_book = bool(re.match(r"^[A-Za-z]", part))
        if starts_new_book and current:
            runs.append(current)
            current = [part]
        else:
            current.append(part)
    if current:
        runs.append(current)
    return ["; ".join(r) for r in runs]


def book_full_name(ref_str: str) -> str:
    """Best-effort full English book name for a single-book reference run."""
    book_num, _ranges = parse_ref_string(ref_str)
    return bible.Book(book_num).title


def parse_tsv(path: Path):
    """Return list of {name, stories: [{title, runs: [ref_str, ...]}]}."""
    rows = []
    with open(path, encoding="utf-8") as f:
        reader = csv.reader(f, delimiter="\t")
        next(reader)  # header
        for r in reader:
            rows.append(r)

    series = []
    cur = None
    for r in rows:
        if not r:
            continue
        title = r[0].strip()
        ref = (r[1].strip() if len(r) > 1 else "")
        if not ref:
            if title:
                cur = {"name": title, "stories": []}
                series.append(cur)
            continue
        if cur is None:
            continue
        title = TITLE_FIXES.get(title, title)
        runs = split_into_book_runs(ref)
        cur["stories"].append({"title": title, "runs": runs})
    return series


def write_story_txt(series, path: Path):
    lines = []
    for cat in series:
        lines.append(f"== {cat['name']}")
        lines.append("")
        for i, story in enumerate(cat["stories"], start=1):
            lines.append(f"{i}. {story['title']}")
            for run in story["runs"]:
                lines.append(f"    • {run}")
        lines.append("")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def write_eng_toml(series, path: Path):
    lines = [
        "# Discover App: Scripture sets - English locale",
        "",
        'title = "Discover App: Scripture Sets"',
        'longTitle = "Discover App: Scripture Sets"',
        'description = ""',
        "",
    ]
    for ci, cat in enumerate(series, start=1):
        cat_id = f"{ci:02d}"
        lines.append(f"[{cat_id}]")
        lines.append(f'title = "{toml_escape(cat["name"])}"')
        lines.append('description = ""')
        lines.append("")

        for si, story in enumerate(cat["stories"], start=1):
            story_id = f"{si:02d}"
            key = f"{cat_id}.{story_id}"
            lines.append(f"[{key}]")
            lines.append(f'title = "{toml_escape(story["title"])}"')
            lines.append('description = ""')
            lines.append("")

            for run in story["runs"]:
                _book_num, ranges = parse_ref_string(run)
                first_ch, first_v, _ = ranges[0]
                subheader_key = f"{key}.{first_ch}_{first_v}"
                if len(story["runs"]) == 1:
                    p_hd = story["title"]
                else:
                    p_hd = book_full_name(run)
                lines.append(f"[{subheader_key}]")
                lines.append(f'p_hd = "{toml_escape(p_hd)}"')
                lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")


def main():
    series = parse_tsv(TSV_PATH)
    n_stories = sum(len(c["stories"]) for c in series)
    n_runs = sum(len(s["runs"]) for c in series for s in c["stories"])
    print(f"Parsed {len(series)} categories, {n_stories} stories, {n_runs} ref runs")

    write_story_txt(series, STORY_TXT_PATH)
    print(f"Wrote {STORY_TXT_PATH}")

    write_eng_toml(series, ENG_TOML_PATH)
    print(f"Wrote {ENG_TOML_PATH}")


if __name__ == "__main__":
    main()
