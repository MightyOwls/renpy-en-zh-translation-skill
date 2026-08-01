# Project Translation Profile

Use a project profile to persist approved translation decisions outside the
generic skill. Keep it near the game project only with user approval.

Recommended YAML shape:

```yaml
version: 1
language:
  source: en
  target: zh-Hans
defaults:
  register: natural-contemporary
  dialect_policy: no-regional-dialect
  archaic_language: restricted
  font_tag_policy: preserve-source

typography_exceptions:
  - marker: font/source-display.ttf
    target_action: remove-font-tag
    reason: target glyphs are unsupported
    scope: ui-strings-only
    status: approved

characters:
  duke:
    display_name: Duke
    markers:
      speakers: [duke]
      fonts: []
    register: formal-controlled
    rhythm: complete-sentences
    address_terms:
      protagonist: 阁下
    preferred_features:
      - 克制表达情绪
    avoid:
      - 过度文言化
    evidence:
      - game/chapter1.rpy:120
    status: approved

channels:
  divine_voice:
    markers:
      speakers: [god]
      fonts: [fonts/divine.ttf]
      colors: ["#d8c8ff"]
    register: ritual-detached
    preferred_features:
      - 少用日常口语
      - 保留异常重复和停顿
    evidence:
      - game/vision.rpy:42
    status: provisional
```

Use stable speaker or channel identifiers as keys. Keep evidence locations and
status so later updates can distinguish approved decisions from inference.

Do not store entire dialogue corpora in the profile. Store concise rules,
approved examples only when necessary, and links to source evidence.

Keep `font_tag_policy: preserve-source` unless the project demonstrates a
target-glyph problem. Record any font replacement or removal as a scoped,
approved exception; do not infer it from a single translated string.

## Automated JSON draft

Use JSON for dependency-free generation and validation. It represents the same
project decisions as the YAML example while adding source-index metadata and
bounded evidence locations:

```text
python scripts/index_rpy_project.py profile-draft --index <index.json> --output .renpy-translation/project-profile.json --speaker <id>
python scripts/index_rpy_project.py profile-check .renpy-translation/project-profile.json --index <index.json>
```

The draft records an evidence digest, evidence mode, statement counts, and
evenly spaced file/line locations. It never stores dialogue text. Every
generated default, character, and marker channel has `status: review`; the
generator cannot grant approval. Fill evidence-backed fields and change status
only after the required human confirmation. An approved character must state
its register and rhythm rather than approving an empty generated shell.

Generated channel classifications use `unknown`, `voice-bearing`, `layout-ui`,
`glyph-fallback`, `redaction`, `decorative`, or `mixed`. An approved
channel cannot remain `unknown`. Speaker identifiers, display names, route
names, and character filenames are separate evidence fields until their mapping
is confirmed.

Run `profile-check` with the current index before a translation batch. A changed
profile evidence digest is a review item: inspect only new or changed evidence
instead of rebuilding approved decisions from scratch. Use `--strict` when
unresolved `review` or `provisional` items must stop automation.
