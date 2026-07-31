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
