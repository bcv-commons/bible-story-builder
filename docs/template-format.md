# Template format — developer reference

This is the technical schema reference for `templates/{ID}/`. The
[README](../README.md) is the "how do I add a story" walkthrough; this doc
is "what does every field actually mean and how does the generator process
it," for anyone extending the format itself or building a client reader.

Four templates exist today — `OBS`, `John`, `TGS`, `DBS` — and this doc
uses real excerpts from all of them, not invented examples.

## Directory layout

```
templates/{ID}/
  index.toml           # collection-level metadata
  manifest.json         # flat file listing with sizes (hand-regenerated, see below)
  source/                # optional — human-authored input, not read by clients
    story.txt
    icon_overrides.toml
  {CAT}/                 # one directory per category, e.g. 01/, 02/
    index.toml            # category-level metadata
    {STORY}.md             # one file per story, e.g. 01.md, 02-1.md
  locales/
    eng.toml              # required — one file per language
    {iso}.toml
```

`OBS` deviates from this shape deliberately — see [§7](#7-the-produced-annex-obs-only).

## 1. Top-level `index.toml`

```toml
level = "collection"

[images]
base_url = "https://cdn.door43.org/obs/jpg/2160px"
thumbs_url = "https://cdn.door43.org/obs/jpg/360px"

[audio]
base_url = "https://cdn.bibel.wiki/audio"

categories = ["01", "02", "03", ...]   # OBS's shape — see below for TGS's [[categories]]
```

Two equivalent shapes exist for declaring categories — `OBS` uses a flat
`categories = [...]` array of ids; `TGS`/`DBS` use a list of tables, one
per category, each carrying its own representative `image`:

```toml
[[categories]]
id = "01"
image = "Bible_OT.png"

[[categories]]
id = "02"
image = "Bible_NT.png"
```

`[images]` fields vary per template depending on the image source's URL
scheme:

- `base_url` + `thumbs_url` (OBS) — two fixed sizes.
- `base_url` + `path_pattern`/`thumbs_pattern`/`medium_pattern` (TGS) — the
  image source groups files by book, so the pattern has a `{book}`
  placeholder alongside `{filename}` (book = first two characters of the
  filename, e.g. `01` from `01_Ge_01_02_RG.jpg`).

`[image]` (singular) — a top-level default/cover image, `filename` only
(resolved against `[images].base_url`).

## 2. Category-level `index.toml`

```toml
level = "chapter"
id = "01"
canon = "ot"

[image]
filename = "Bible_OT.png"

[[stories]]
id = "01"
image = "01_Ge_01_02_RG.jpg"

[[stories]]
id = "02-1"
image = "01_Ge_03_01_RG.jpg"
```

- `level` — `"chapter"` in TGS/DBS/John's category files; OBS's category
  files say `level = "category"` instead. Cosmetic naming difference only
  — both mean the same thing: a folder of stories.
- `canon` — `"ot"`, `"nt"`, or `"mixed"` (DBS uses `"mixed"` for the three
  of its ten series that span both testaments — Series 1, Series 3,
  Discover Christmas). **This field is display metadata only** — a
  client's own logic should derive the real canon per book directly from
  each `[[ref:BOOK...]]` tag in the `.md` content, not from this field.
  A mixed-canon category is not a special case for anything except UI
  labeling.
- OBS additionally carries `beg`/`count` per category (e.g. `beg = 1,
  count = 3` for category `01`) — the global OBS-TLF story number range
  (1-50) that category covers. Story `id`s under OBS categories are
  already the *global* number (e.g. category `02`'s stories are ids
  `04`-`08`, not `01`-`05`), unlike TGS/DBS where each category restarts
  its story numbering at `01`.
- `[[stories]]` `id` — matches a `.md` filename (`{id}.md`). A `-N` suffix
  (`02-1`, `05-3`) marks one of several stories that share a single
  numbered outline entry with multiple bullet passages — see
  [§5](#5-sourcestorytxt-format).

## 3. Story `.md` format

Real excerpt, `templates/John/01/01.md`:

```markdown
# [[t:title]]

## [[t:01.01.title]]

[[t:01.01.description]]

[[chapter:01]]

![Image](VB-John1v1.jpg)

### [[t:01.01.1.p_hd]]

[[ref:JHN 1:1]]

![Image](VB-John1v1alt.jpg)

[[ref:JHN 1:2]]
```

Markers:

- `# [[t:title]]` — the collection's top-level title. Emitted only in the
  *first* story of each category (the `is_first`/`seen_numbered` logic in
  `generate_stories.py`'s `parse_story_txt` — a bare bullet before any
  numbered story marks a prologue and also gets this heading; otherwise
  only the first numbered story per category gets it).
- `## [[t:{cat}.{story}.title]]` / `[[t:{cat}.{story}.description]]` — the
  story's own title/description, resolved from `locales/{iso}.toml`.
- `[[chapter:NN]]` / `[[story:NN]]` — marks a chapter or story boundary.
  Template-specific (John's Bible-chapter-driven content uses
  `[[chapter:...]]`; OBS uses `[[story:...]]`; TGS/DBS use neither — they
  have no single-book chapter structure to mark).
- `### [[t:{cat}.{story}.{ch}_{v}.p_hd]]` — a subheading within a story,
  keyed by the first chapter/verse of the passage it introduces.
- `[[ref:BOOK CH:V]]` — the actual Bible passage. **One book per tag** —
  this is a hard constraint, not a style choice (`format_ref()` in
  `generate_stories.py` only ever emits one `BOOK_REF` prefix per tag).
  A story whose outline crosses two books (e.g. "Matthew 3; John 1:29-34")
  becomes **two separate `### [[t:...]]` subheadings**, each with its own
  single-book `[[ref:...]]` — never one tag spanning two books. See DBS's
  `01/13.md` ("Redemption: Jesus' baptism") for a real example.
  - Same-book multi-chapter ranges *do* work in one tag:
    `[[ref:GEN 6:5-8;7:17-24;9:8-13]]`, comma-separated verse lists within
    one chapter: `[[ref:EXO 16:4-5,14-15]]`.
  - A whole-chapter reference with no verse range (`Isaiah 53`) resolves to
    the chapter's full `1..N` verse span via
    `pythonbible.get_number_of_verses()` — this used to crash before a
    2026-09 fix; if you're extending `parse_ref_string`, keep that
    resolution in place.
- `![Image](filename.jpg)` — resolved against `[images].base_url` (+
  book-specific pattern, if the template has one).

## 4. `locales/{iso}.toml`

```toml
title = "The Grand Story"
longTitle = "The Grand Story of the Bible"
description = "A journey through key moments in the Bible — from start to finish."

[01]
title = "Scenes from the Old Testament"
description = "The story of God's people..."

[01.01]
title = "In the beginning"
description = "God creates the heavens and the earth..."

[01.01.26_3]
p_hd = "God creates the heavens and the earth"
```

Every `[[t:KEY...]]` reference in the `.md` files must resolve to an entry
here, per language. There's no fallback to English text baked into the
`.md` markers themselves — a client missing a locale key would need its own
fallback behavior. `eng.toml` is the source-of-truth English content and
should always be complete for a template before it ships.

**DBS's `eng.toml` has empty `description = ""` throughout** — its source
data (`example/scripture-sets.tsv`) only had a title and a Bible reference
per story, no narrative description. That's a known, deliberate gap (real
data, not fabricated placeholder prose), not a bug to silently "fix" by
inventing text.

## 5. `source/story.txt` format

Parsed by `parse_story_txt()` in `generate_stories.py`. Two category-header
styles:

```
Part One — Scenes from the Old Testament
```
Hardcoded two-way split: "One" → category `01`, "Two" → category `02`.
Used by TGS (OT/NT).

```
== Series 1: Creation to Christ
```
General N-category form, added for DBS: each `==` header starts a new
category, numbered sequentially (`01`, `02`, ... in the order they appear).
Prefer this for any new source that isn't a strict two-way split.

Within a category:

```
1. From Eden to Babel
    • The Fall — Genesis 3:1–24
    • The Flood — Genesis 6:5–8; 7:17–24; 9:8–13

• Prologue: In the beginning
    • Genesis 1:1–5; 1:26–31; 2:7
```

- `N. Title` — a numbered story. Story ids are assigned sequentially within
  the category (`01`, `02`, ...), restarting at each new category/`==`
  header (except OBS's global-numbering convention, which isn't produced
  by this generator).
- `• Title: ...` *before any numbered story* — a prologue, gets the
  top-level `# [[t:title]]` heading (see §3).
- Indented `    • ` lines are the story's passages. Two forms:
  - `Title — Genesis 3:1–24` — title becomes the subheading's *source*
    text (though the actual rendered text still comes from
    `locales/eng.toml` — the title here is just what a human transcribing
    into the locale file would use).
  - Bare `Genesis 1:1–5; 1:26–31; 2:7` (no `—`) — subheading key derives
    from the first chapter:verse instead of a title.
  - **One bullet per book.** If a story's outline crosses two books, write
    two bullets, not one bulleted line with two book names — the parser
    (and the `[[ref:...]]` format itself) has no way to represent a
    cross-book reference in a single line/tag. `scripts/build_dbs_source.py`
    does this split automatically when converting a TSV where one row's
    reference names two books (see its `split_into_book_runs()`).

Run `python generate_stories.py {ID}` to regenerate `.md` files from
`story.txt`. It reads `data/iconsSyncData.json` (verse → image lookup) and
`source/icon_overrides.toml` if present (manual overrides merged in before
generation — see TGS's for the format: `[[icons]] book = ...  chapter = ...
start = ... end = ...  ids = [...]`). It does **not** write `index.toml` or
`manifest.json` — those stay hand-authored (or scripted separately, as DBS's
category `index.toml` files were built by a one-off script during that
template's creation, not by `generate_stories.py` itself).

## 6. `manifest.json`

```json
{
  "files": [{"path": "01/01.md", "size": 2583}, ...],
  "total_files": N,
  "total_size": N
}
```

A flat listing of every file under the template directory except itself,
with byte sizes. Regenerate after any content change:

```python
import json
from pathlib import Path

top = Path("templates/{ID}")
entries = [
    {"path": str(f.relative_to(top)), "size": f.stat().st_size}
    for f in sorted(top.rglob("*")) if f.is_file() and f.name != "manifest.json"
]
data = {"files": entries, "total_files": len(entries), "total_size": sum(e["size"] for e in entries)}
(top / "manifest.json").write_text(json.dumps(data, indent=2, ensure_ascii=False))
```

## 7. The `[produced]` annex (OBS only)

`OBS`'s content is DBT-verse-reconstructed like every other template (see
§1-§6 above — nothing about its `.md`/`index.toml`/`locales` differs
structurally). But real, purpose-made OBS-TLF/unfoldingWord narration
(authored text and/or recorded audio) also exists for many languages, and
should be preferred over the reconstruction wherever it exists. Rather than
a second template, this lives as one extra section in `templates/OBS/index.toml`:

```toml
[produced]
catalog_index_url = "https://cdn.bibel.wiki/catalog/obs-index.json"
media_url_pattern = "https://cdn.bibel.wiki/obs/{iso}/media.json"
timing_base_url = "https://cdn.bibel.wiki/align/obs"
```

The render rule: check `catalog_index_url` for whether `<iso>` is listed at
all; if so, fetch `media_url_pattern` for that language and check its
fields for produced text/audio **independently** — a language can have one
without the other, and a client should use whichever part is actually
present, falling back to the reconstructed `[[ref:...]]` content for
whichever part isn't. None of this is staged locally in this repo — no
`languages.json`, no per-language titles committed here — because the
per-language content (segment/image layout) is inherently per-translator,
not a fixed universal set the way the reconstruction's verse references
and canonical artwork are. `cdn.bibel.wiki` resolves it live.

If you're building a client reader: this is the one place in the whole
template format where "check a field in `index.toml`" isn't the end of the
story — `[produced]`'s presence means keep going to the CDN before
rendering.
