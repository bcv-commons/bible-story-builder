#!/usr/bin/env python3
"""Generate story .md files from source/story.txt, iconsSyncData.json and icon_overrides.toml.

Usage:
    python generate_stories.py [template_name]

If no template name is given, processes all templates that have a source/story.txt.
"""

import json
import os
import re
import sys

import pythonbible as bible

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib  # Python < 3.11

# ─── Icon ID → Sweet Publishing filename mapping ───
BOOK_ABBR = {
    1: "Ge", 2: "Ex", 3: "Le", 4: "Nu", 5: "De",
    6: "Jo", 7: "Ju", 8: "Ru", 9: "1Sa", 10: "2Sa",
    11: "1Ki", 12: "2Ki", 13: "1Ch", 14: "2Ch", 15: "Ezr",
    16: "Ne", 17: "Es", 18: "Job", 19: "Ps", 20: "Pr",
    21: "Ec", 22: "So", 23: "Is", 24: "Je", 25: "La",
    26: "Eze", 27: "Da", 28: "Ho", 29: "Joe", 30: "Am",
    31: "Ob", 32: "Jon", 33: "Mic", 34: "Na", 35: "Hab",
    36: "Zep", 37: "Hag", 38: "Zec", 39: "Mal",
    40: "Mt", 41: "Mk", 42: "Lk", 43: "Jn", 44: "Ac",
    45: "Ro", 46: "1Co", 47: "2Co", 48: "Ga", 49: "Eph",
    50: "Php", 51: "Col", 52: "1Th", 53: "2Th", 54: "1Ti",
    55: "2Ti", 56: "Tit", 57: "Phm", 58: "Heb", 59: "Jam",
    60: "1Pe", 61: "2Pe", 62: "1Jn", 63: "2Jn", 64: "3Jn",
    65: "Jud", 66: "Re",
}

# USFM 3-letter book codes used in [[ref:XXX ch:v]] output
BOOK_REF = {
    1: "GEN", 2: "EXO", 3: "LEV", 4: "NUM", 5: "DEU",
    6: "JOS", 7: "JDG", 8: "RUT", 9: "1SA", 10: "2SA",
    11: "1KI", 12: "2KI", 13: "1CH", 14: "2CH", 15: "EZR",
    16: "NEH", 17: "EST", 18: "JOB", 19: "PSA", 20: "PRO",
    21: "ECC", 22: "SNG", 23: "ISA", 24: "JER", 25: "LAM",
    26: "EZK", 27: "DAN", 28: "HOS", 29: "JOL", 30: "AMO",
    31: "OBA", 32: "JON", 33: "MIC", 34: "NAM", 35: "HAB",
    36: "ZEP", 37: "HAG", 38: "ZEC", 39: "MAL",
    40: "MAT", 41: "MRK", 42: "LUK", 43: "JHN", 44: "ACT",
    45: "ROM", 46: "1CO", 47: "2CO", 48: "GAL", 49: "EPH",
    50: "PHP", 51: "COL", 52: "1TH", 53: "2TH", 54: "1TI",
    55: "2TI", 56: "TIT", 57: "PHM", 58: "HEB", 59: "JAS",
    60: "1PE", 61: "2PE", 62: "1JN", 63: "2JN", 64: "3JN",
    65: "JUD", 66: "REV",
}


# ─── story.txt parser ───

def parse_ref_string(ref_str):
    """Parse a Bible reference string into (book_num, [(chapter, start_v, end_v), ...]).

    Uses pythonbible for book name resolution. Handles en-dashes and semicolons.
    Examples:
        "Genesis 3:1-24" -> (1, [(3, 1, 24)])
        "Genesis 6:5-8; 7:17-24; 9:8-13" -> (1, [(6, 5, 8), (7, 17, 24), (9, 8, 13)])
        "Exodus 16:4-5, 14-15" -> (2, [(16, 4, 5), (16, 14, 15)])
    """
    # Normalize en-dash to hyphen
    ref_str = ref_str.replace("–", "-")

    # pythonbible doesn't handle semicolons well for multi-chapter refs.
    # Split on semicolons, keep the book name from the first part.
    parts = [p.strip() for p in ref_str.split(";")]

    # Parse first part to get the book
    first_refs = bible.get_references(parts[0])
    if not first_refs:
        raise ValueError(f"Could not parse reference: {ref_str!r}")

    book = first_refs[0].book
    book_num = book.value

    def resolve_verses(chapter, start_v, end_v):
        # Whole-chapter refs (e.g. "Isaiah 53", no colon) parse with
        # start_verse/end_verse both None — resolve to the full 1..N range.
        if start_v is None and end_v is None:
            return 1, bible.get_number_of_verses(book, chapter)
        return start_v, end_v

    ranges = []
    for ref in first_refs:
        sv, ev = resolve_verses(ref.start_chapter, ref.start_verse, ref.end_verse)
        ranges.append((ref.start_chapter, sv, ev))

    # Parse remaining semicolon-separated parts (chapter:verse only)
    for part in parts[1:]:
        # These are like "7:17-24" — prepend book name so pythonbible can parse
        book_name = book.title
        sub_refs = bible.get_references(f"{book_name} {part}")
        for ref in sub_refs:
            sv, ev = resolve_verses(ref.start_chapter, ref.start_verse, ref.end_verse)
            ranges.append((ref.start_chapter, sv, ev))

    return book_num, ranges


def parse_story_txt(story_txt_path):
    """Parse a story.txt file into a list of story definitions.

    Returns list of (category, story_id, title_key, is_first, sections) tuples,
    where sections is [(subheader_key, book_num, [(chapter, start_v, end_v), ...])].
    """
    with open(story_txt_path, encoding="utf-8") as f:
        lines = f.readlines()

    stories = []
    current_cat = None
    story_counter = 0
    cat_counter = 0
    # Track the last numbered story to detect prologues vs epilogues
    seen_numbered = False

    for line in lines:
        line = line.rstrip()

        # Detect part headers: "Part One ..." or "Part Two ..." (used by
        # two-part OT/NT sources like TGS)
        if re.match(r"Part\s+(One|Two)\b", line, re.IGNORECASE):
            if "one" in line.lower():
                current_cat = "01"
            else:
                current_cat = "02"
            story_counter = 0
            seen_numbered = False
            continue

        # Generalized category header: "== Category Name" — supports any
        # number of named categories (not just a two-part OT/NT split).
        cat_header_match = re.match(r"==\s+(.+)", line)
        if cat_header_match:
            cat_counter += 1
            current_cat = f"{cat_counter:02d}"
            story_counter = 0
            seen_numbered = False
            continue

        if current_cat is None:
            continue

        # Detect story headers
        # Numbered: "1. From Eden to Babel"
        # Prologue/Epilogue: "• Prologue: ..." or "• Epilogue: ..."
        numbered_match = re.match(r"(\d+)\.\s+(.+)", line)
        bullet_match = re.match(r"•\s+(.+)", line)

        if numbered_match or bullet_match:
            story_counter += 1
            story_id = f"{story_counter:02d}"
            title_key = f"{current_cat}.{story_id}"

            if bullet_match and not seen_numbered:
                is_first = True  # Prologue
            elif numbered_match and not seen_numbered:
                is_first = False
                seen_numbered = True
            else:
                is_first = numbered_match is not None and not seen_numbered
                if numbered_match:
                    seen_numbered = True

            stories.append((current_cat, story_id, title_key, is_first, []))
            continue

        # Detect section references (indented bullet with reference)
        # With title: "    • The Fall — Genesis 3:1–24"
        # Without title: "    • Genesis 1:1–5; 1:26–31; 2:7"
        section_match = re.match(r"\s+•\s+(.+?)\s*—\s*(.+)", line)
        bare_ref_match = None
        if not section_match:
            bare_ref_match = re.match(r"\s+•\s+(.+)", line)
        if (section_match or bare_ref_match) and stories:
            if section_match:
                ref_str = section_match.group(2).strip()
            else:
                ref_str = bare_ref_match.group(1).strip()
            # Strip common book name prefixes (keep the core book name)
            ref_str = re.sub(r"^Book of\s+", "", ref_str)
            ref_str = re.sub(r"^Gospel of\s+", "", ref_str)
            ref_str = re.sub(r"^Acts of the Apostles\s+", "Acts ", ref_str)

            try:
                book_num, verse_ranges = parse_ref_string(ref_str)
            except (ValueError, IndexError) as e:
                print(f"  Warning: could not parse reference {ref_str!r}: {e}")
                continue

            # Build subheader key from first chapter:verse
            first_ch, first_v, _ = verse_ranges[0]
            subheader_key = f"{stories[-1][2]}.{first_ch}_{first_v}"

            stories[-1][4].append((subheader_key, book_num, verse_ranges))

    return stories


# ─── Icon data loading ───

def icon_id_to_filename(icon_id: str) -> str:
    """Convert icon ID to filename.

    Handles both 3-part numeric IDs ('01_03_07' → '01_Ge_03_07_RG.jpg')
    and 4-part IDs with abbreviation ('23_Is_07_01' → '23_Is_07_01_RG.jpg').
    """
    parts = icon_id.split("_")
    if len(parts) >= 4:
        # Already has abbreviation: booknum_abbr_chapter_seq
        return f"{parts[0]}_{parts[1]}_{parts[2]}_{parts[3]}_RG.jpg"
    book_num = int(parts[0])
    abbr = BOOK_ABBR.get(book_num, parts[0])
    return f"{parts[0]}_{abbr}_{parts[1]}_{parts[2]}_RG.jpg"


def load_icons_data(json_path: str) -> dict:
    """Load iconsSyncData.json into {book_int: {chapter_int: {verse_int: {e, id}}}}."""
    with open(json_path) as f:
        data = json.load(f)

    result = {}
    for book_s, chapters in data.items():
        book = int(book_s)
        result[book] = {}
        for ch_s, verses in chapters.items():
            ch = int(ch_s)
            result[book][ch] = {}
            for v_s, entry in verses.items():
                v = int(v_s)
                result[book][ch][v] = {
                    "e": int(entry["e"]),
                    "id": entry["id"],
                }
    return result


def load_overrides(toml_path: str, icons_data: dict) -> int:
    """Load icon_overrides.toml and merge into icons_data. Returns count of overrides."""
    if not os.path.exists(toml_path):
        return 0

    with open(toml_path, "rb") as f:
        overrides = tomllib.load(f)

    count = 0
    for entry in overrides.get("icons", []):
        book = entry["book"]
        ch = entry["chapter"]
        sv = entry["start"]
        ev = entry["end"]
        ids = entry["ids"]

        if book not in icons_data:
            icons_data[book] = {}
        if ch not in icons_data[book]:
            icons_data[book][ch] = {}

        icons_data[book][ch][sv] = {"e": ev, "id": ids}
        count += 1

    return count


# ─── Markdown generation ───

def format_ref(book_num: int, segments: list) -> str:
    """Format a list of (chapter, start_v, end_v) segments into a [[ref:...]] string.

    Segments are grouped: same chapter with gaps use commas,
    different chapters use semicolons.

    Example: [(6,5,8),(7,17,24)] -> "[[ref:GEN 6:5-8;7:17-24]]"
    Example: [(16,4,5),(16,14,15)] -> "[[ref:EXO 16:4-5,14-15]]"
    """
    if not segments:
        return ""

    ref_code = BOOK_REF[book_num]
    parts = []
    prev_ch = None

    for ch, sv, ev in segments:
        if sv == ev:
            vrange = str(sv)
        else:
            vrange = f"{sv}-{ev}"

        if prev_ch is None:
            parts.append(f"{ref_code} {ch}:{vrange}")
        elif ch == prev_ch:
            parts[-1] += f",{vrange}"
        else:
            parts.append(f"{ch}:{vrange}")

        prev_ch = ch

    return "[[ref:" + ";".join(parts) + "]]"


def process_section(icons_data, book_num, verse_ranges, output_lines):
    """Process a list of (chapter, start_verse, end_verse) ranges.

    Buffer verses. When an icon is found, flush buffer as a ref,
    output the icon(s), then start new buffer from the icon's verse range.
    At the end, flush remaining buffer.
    """
    buffer = []  # list of (ch, v)

    for ch, range_start, range_end in verse_ranges:
        v = range_start
        while v <= range_end:
            entry = None
            if book_num in icons_data and ch in icons_data[book_num]:
                entry = icons_data[book_num][ch].get(v)

            if entry is not None:
                if buffer:
                    segments = buffer_to_segments(buffer)
                    ref = format_ref(book_num, segments)
                    output_lines.append("")
                    output_lines.append(ref)

                for icon_id in entry["id"]:
                    fname = icon_id_to_filename(icon_id)
                    output_lines.append("")
                    output_lines.append(f"![Image]({fname})")

                icon_end = min(entry["e"], range_end)
                buffer = [(ch, vv) for vv in range(v, icon_end + 1)]
                v = icon_end + 1
            else:
                buffer.append((ch, v))
                v += 1

    if buffer:
        segments = buffer_to_segments(buffer)
        ref = format_ref(book_num, segments)
        output_lines.append("")
        output_lines.append(ref)


def buffer_to_segments(buffer):
    """Convert a buffer of (ch, v) tuples into consolidated segments."""
    if not buffer:
        return []

    segments = []
    seg_ch, seg_start = buffer[0]
    seg_end = seg_start

    for ch, v in buffer[1:]:
        if ch == seg_ch and v == seg_end + 1:
            seg_end = v
        else:
            segments.append((seg_ch, seg_start, seg_end))
            seg_ch = ch
            seg_start = v
            seg_end = v

    segments.append((seg_ch, seg_start, seg_end))
    return segments


def generate_story(icons_data, story_def):
    """Generate the .md content for one story."""
    cat, story_id, title_key, is_first, sections = story_def
    lines = []

    if is_first:
        lines.append("# [[t:title]]")
        lines.append("")

    lines.append(f"## [[t:{title_key}.title]]")
    lines.append("")
    lines.append(f"[[t:{title_key}.description]]")

    for subheader_key, book_num, verse_ranges in sections:
        lines.append("")
        lines.append(f"### [[t:{subheader_key}.p_hd]]")
        process_section(icons_data, book_num, verse_ranges, lines)

    lines.append("")
    return "\n".join(lines)


def process_template(template_dir, icons_data):
    """Process a single template directory."""
    template_name = os.path.basename(template_dir)
    story_txt = os.path.join(template_dir, "source", "story.txt")

    if not os.path.exists(story_txt):
        return False

    print(f"\n--- {template_name} ---")
    print(f"  Parsing source/story.txt...")

    stories = parse_story_txt(story_txt)
    print(f"  Found {len(stories)} stories")

    # Load icon overrides if present
    overrides_path = os.path.join(template_dir, "source", "icon_overrides.toml")
    overrides_count = load_overrides(overrides_path, icons_data)
    if overrides_count:
        print(f"  Merged {overrides_count} icon overrides")

    total_icons = 0
    for story_def in stories:
        cat, story_id, title_key, is_first, sections = story_def
        out_dir = os.path.join(template_dir, cat)
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, f"{story_id}.md")

        content = generate_story(icons_data, story_def)

        with open(out_path, "w") as f:
            f.write(content)

        icon_count = content.count("![Image]")
        total_icons += icon_count
        print(f"  {cat}/{story_id}.md — {icon_count} icons")

    print(f"  Done: {len(stories)} stories, {total_icons} icons total")
    return True


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    icons_json_path = os.path.join(script_dir, "data", "iconsSyncData.json")
    templates_dir = os.path.join(script_dir, "templates")

    print("Loading iconsSyncData.json...")
    icons_data = load_icons_data(icons_json_path)
    print(f"  Loaded {sum(len(chs) for chs in icons_data.values())} chapters across {len(icons_data)} books")

    # Determine which templates to process
    if len(sys.argv) > 1:
        # Process specific template
        template_name = sys.argv[1]
        template_dir = os.path.join(templates_dir, template_name)
        if not os.path.isdir(template_dir):
            print(f"Error: template directory not found: {template_dir}")
            sys.exit(1)
        if not process_template(template_dir, icons_data):
            print(f"Error: no source/story.txt found in {template_dir}")
            sys.exit(1)
    else:
        # Process all templates with source/story.txt
        count = 0
        for entry in sorted(os.listdir(templates_dir)):
            template_dir = os.path.join(templates_dir, entry)
            if os.path.isdir(template_dir):
                if process_template(template_dir, icons_data):
                    count += 1
        if count == 0:
            print("No templates with source/story.txt found.")
        else:
            print(f"\nProcessed {count} template(s).")


if __name__ == "__main__":
    main()
