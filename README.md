# Bible Story Builder

This repo builds curated Bible **story templates** — themed collections of
Bible passages, paired with images and per-language titles/descriptions —
distributed for use in Bible reading/listening apps.

Four templates exist today:

| Template | Description | Books |
|----------|-------------|-------|
| John | Gospel of John | JHN (21 chapters) |
| OBS | Open Bible Stories | 11 books (selections from the whole Bible); prefers real OBS-TLF/unfoldingWord-produced text/audio where it exists (see `[produced]` in `templates/OBS/index.toml`), falling back to verse-matched content otherwise |
| TGS | The Greatest Story | 19 books (the whole Bible, Genesis to Revelation) |
| DBS | Discover App: Scripture Sets | 18 books across 10 topical/discipleship series |

No programming experience is required beyond editing text files.

## Role of this repo

This repo owns exactly one thing: the `templates/` content itself — which
Bible passages and images make up each story, in a format any client can
render. It's one of a small set of sibling repos that split up a larger
pipeline: two others, `audio-sync` (runs speech-to-text alignment) and
`bibles` (fetches Bible text/audio and publishes a catalog to a CDN),
handle everything upstream of the templates themselves. This repo used to
also fetch Bible content, decide what needed aligning, and download/bundle
timing data — that all turned out to be redundant with what those two
repos already do, so it was retired.

See [docs/template-format.md](docs/template-format.md) for the full
technical reference on the `index.toml`/`.md`/`locales` format this section
only introduces.

## What a template looks like

A template is a directory under `templates/{ID}/`:

```
templates/TGS/
  index.toml           # collection metadata: image/audio sources, category list
  source/
    story.txt           # human-authored outline (see below) — optional, John/OBS don't have one
  01/
    index.toml          # category metadata: which stories, which images
    01.md                # story content: references + images
    02.md
    ...
  locales/
    eng.toml             # per-language titles & descriptions
    swe.toml
    ...
```

## The easy way: writing a `story.txt` outline

The fastest way to draft a new template (or add stories to one) is a plain
text outline. `templates/TGS/source/story.txt` is a real example:

```
Part One — Scenes from the Tanakh

• Prologue: In the beginning
    • Genesis 1:1–5; 1:26–31; 2:7

1. From Eden to Babel
    • The Fall — Genesis 3:1–24
    • The Flood — Genesis 6:5–8; 7:17–24; 9:8–13
    • Tower of Babel — Genesis 11:1–9

2. Abraham, Isaac and Jacob
    • Call of Abraham — Genesis 12:1–3
    • God's covenant — Genesis 15:5–6
```

- `Part One` / `Part Two` headers split the collection into its two parts (Tanakh and Apostolic Writings).
  `== Category Name` also works, for any number of named categories (not
  just a two-part split) — see `templates/DBS/source/story.txt`.
- Numbered lines (`1.`, `2.`, ...) start a new story; bullet-only lines
  (`• Prologue: ...`) mark prologue/epilogue stories.
- Indented bullets are the passages that make up that story, as
  `Title — Book Chapter:Verse` (semicolons separate multiple ranges within
  the same book). A passage spanning two different books needs two
  separate bullet lines, one per book — see DBS's "Commands of Christ"
  series for real examples.

Once your outline is ready, generate the `.md` files and image assignments:

```bash
pip install -r requirements.txt
python generate_stories.py TGS
```

This reads `templates/TGS/source/story.txt` plus `data/iconsSyncData.json`
(the shared image library) and writes out the `.md` files under
`templates/TGS/`. Existing stories are regenerated, so it's safe to re-run
after editing `story.txt`. It does **not** write `index.toml` or
`manifest.json` — those are hand-authored (see DBS's `index.toml`/category
`index.toml` files for a worked example of building them from a
`story.txt` outline) and `manifest.json` is a plain file listing you
regenerate yourself (see `scripts/build_dbs_source.py` for a full
ingestion example, or just list `templates/{ID}/**` with sizes).

DBS's `templates/DBS/source/story.txt` was itself generated from a TSV
(`example/scripture-sets.tsv`) by `scripts/build_dbs_source.py` — a useful
reference if your source content starts out as a spreadsheet rather than a
hand-written outline.

## Editing content directly

You don't need `story.txt` — John and OBS were authored directly as `.md`
files, and you can edit any template the same way. Each story file uses a
small set of markers:

```markdown
## [[t:01.08.title]]

[[t:01.08.description]]

[[chapter:08]]

### [[t:01.08.1.p_hd]]

![Image](VB-John8v2a.jpg)

[[ref:JHN 8:1-2]]
```

- `[[ref:BOOK CHAPTER:VERSES]]` — pulls in the Bible text for that passage,
  in whatever language the reader has selected (e.g. `JHN 8:1-2`,
  `GEN 6:5-8;7:17-24`).
- `[[chapter:NN]]` / `[[story:NN]]` — marks the start of a chapter or story
  section (matches the `id` in the category's `index.toml`).
- `[[t:KEY.title]]`, `[[t:KEY.description]]`, `[[t:KEY.p_hd]]` — placeholders
  resolved from `locales/{iso}.toml`; the actual text lives there, not in
  the `.md` file, so one story file works for every language.
- `![Image](filename.jpg)` — an image from the collection's configured
  image source (see `[images] base_url` in `index.toml`).

## Adding language text

Titles and descriptions are per-language, in `templates/{ID}/locales/{iso}.toml`:

```toml
title = "The Gospel of John"
longTitle = "The Good News according to John"
description = "Jesus' beloved disciple John tells us about the One who was from the beginning."

[01]
title = "The Word Among Us"
description = "Chapters 1–12: From the incarnation of the Word to Jesus' entry into Jerusalem"

[01.01]
title = "The Living Word of God"
description = "The Word of God became flesh and dwelt with us."
```

The top-level keys are the collection title/description; `[01]` is a
category, `[01.01]` is a story within it — matching the `[[t:...]]` keys
used in the `.md` files. To add a new language, copy an existing
`locales/eng.toml` and translate it. The Bible passage text itself (via
`[[ref:...]]`) is resolved separately and doesn't need translating here.

## Adding a whole new template

1. Create `templates/{NEWID}/index.toml` — copy an existing template's as a
   starting point and adjust `[images]`/`[audio]` base URLs.
2. Either write `source/story.txt` and run `generate_stories.py {NEWID}`,
   or hand-author category folders and `.md` files directly.
3. Add at least `locales/eng.toml`.
4. Hand-write the category `index.toml` files and top-level `index.toml`
   (see DBS for a from-scratch example), and a `manifest.json` file listing.
5. Open a PR.

## Contributing

- **New templates or stories** — see above.
- **New language locales** — add `templates/{ID}/locales/{iso}.toml` for an
  existing template.
- **Report content issues** — wrong reference, missing image, mistranslation
  — open an issue with the template ID and story/category.

No fork required for small changes — clone, edit, and open a PR.

## Credits

Open Bible Stories from [unfoldingWord](https://www.unfoldingword.org/).
TGS/DBS images from [Sweet Publishing](https://sweetpublishing.com/). Bible
text/audio for produced OBS content is not rehosted here — see
`templates/OBS/index.toml`'s `[produced]` section.

## License

MIT License — See [LICENSE](LICENSE) file.
