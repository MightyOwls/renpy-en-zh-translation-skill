# Ren'Py English-to-Chinese translation Skill

English | [简体中文](README.zh-CN.md)

This repository contains a Codex Skill for translating or revising English
Ren'Py localization files as natural Simplified Chinese. It treats executable
structure as a hard constraint, then handles character voice, narrative
register, forms of address, menu intent, and readable Chinese prose.

> Status: [v0.1.0](https://github.com/MightyOwls/renpy-en-zh-translation-skill/releases/tag/v0.1.0)
> is the first complete public release. Use version control, inspect the final
> diff, and run the available Ren'Py checks before distributing a translated
> game.

## What it does

- Translates or revises dialogue, narration, internal monologue, menus, UI
  strings, and `old`/`new` pairs.
- Preserves speakers, translation blocks, interpolation, text tags, escapes,
  indentation, and executable code.
- Builds project-approved terminology, character voices, narrator registers,
  and special text-channel profiles before bulk translation.
- Indexes large projects locally and gives the model only compact summaries
  and bounded samples.
- Creates small local calibration pilots from source comments without copying
  existing translations.
- Reports post-translation statistics and bounded line locations, separating
  technical failures, manual review items, and informational findings.
- Compares commented source statements with active targets and reports pairing
  coverage and structural differences.
- Distinguishes missing or added protected tokens from ordering changes caused
  by natural Chinese word order.
- Summarizes encoding, newline conventions, and BOM usage, including mixed
  newlines that may damage a file.

The main entry point is
[SKILL.md](.agents/skills/renpy-en-zh-translation/SKILL.md). Detailed rules are
under [references/](.agents/skills/renpy-en-zh-translation/references/).

## Out of scope

This Skill does not handle:

- `.rpa` extraction or `.rpyc` decompilation;
- font installation, engine debugging, or code repair;
- Ren'Py builds, Android ports, or deployment;
- unattended one-click translation of an entire game.

The indexer is a lightweight discovery and sampling tool. It is not a complete
Ren'Py AST or syntax validator. Multiline definitions, custom statements, and
project-specific syntax still require manual inspection.

## Installation

Copy this directory into the same location in the target repository:

```text
.agents/skills/renpy-en-zh-translation/
```

Open the target repository in Codex and make a request such as:

```text
Use $renpy-en-zh-translation to translate game/tl/schinese/chapter1.rpy.
```

Or ask Codex to establish voices before editing files:

```text
Use renpy-en-zh-translation to analyze how these characters speak and propose
a voice plan. Do not modify any files until I approve it.
```

## Token-efficient workflow for large projects

The indexer reads `.rpy` files locally. `scan` and `summary` emit statistics
and bounded difference locations rather than full dialogue. Only `samples`
returns source evidence, with explicit limits.

```text
python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py scan "PATH_TO_PROJECT" --index .renpy-translation/project-index.json

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py summary --index .renpy-translation/project-index.json

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py samples --index .renpy-translation/project-index.json --speaker SPEAKER_ID --source evidence --limit 12 --context 0

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py samples --index .renpy-translation/project-index.json --speaker SPEAKER_ID --file "routes/ROUTE_NAME*.rpy" --source evidence --limit 12 --context 0

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py samples --index .renpy-translation/project-index.json --font FONT_MARKER --source evidence --limit 5 --context 0

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py samples --index .renpy-translation/project-index.json --color COLOR_MARKER --source evidence --limit 5 --context 0

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py profile-draft --index .renpy-translation/project-index.json --output .renpy-translation/project-profile.json --speaker SPEAKER_ID

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py profile-check .renpy-translation/project-profile.json --index .renpy-translation/project-index.json

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py pilot --index .renpy-translation/project-index.json --file "routes/ROUTE_NAME.rpy" --start-line 100 --limit 40 --output .renpy-translation/pilot/scene.rpy

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py check .renpy-translation/pilot/scene.rpy --index .renpy-translation/project-index.json --source-file "routes/ROUTE_NAME.rpy" --expected-targets 40

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py check "routes/ROUTE_NAME.rpy" --index .renpy-translation/project-index.json --source-file "routes/ROUTE_NAME.rpy"
```

The scan path determines the relative file names stored in the index. If
`scan` receives one `.rpy` file, that file's parent becomes the index root.
Later `pilot --file` and `check --source-file` commands must use the reported
index-relative name, usually the basename, rather than the longer path passed
to `scan`.

`summary` reports commented-source/active-target pairs separately from
`old`/`new` pairs. Do not treat the combined evidence count as the target count
for a calibration pilot. Select the pilot by its indexed file name, source
line, and an explicit `--limit`, then pass the actual target count to
`check --expected-targets`.

`--file` accepts repeatable, project-relative POSIX globs. Use it to keep one
speaker's samples from separate routes apart, so unrelated scenes do not blur
the voice evidence.

If a project uses visible quotation marks around a whole passage to distinguish
speech from another text channel, group samples with `--outer-quotes present`,
`absent`, or `partial`. `partial` means that only one visible quote edge is
present, which is common in interrupted speech or statements that continue
across lines. `absent` means neither edge is present after ignoring text tags at
the string boundaries. These options classify syntax only. Scene context must
still establish whether the text is speech, internal thought, or another mode.
Likewise, `kind=narration` only means that the scanner found no speaker token.
It may include narration, internal thought, anonymous speech, or a custom
project channel.

If the existing translation has not been approved as style evidence, use
`--source evidence --context 0`. This mode prefers commented source statements
and `old` strings. If the project has no localization source evidence, it uses
active statements from the original scripts. Context lines are raw neighboring
lines and may still contain active translations or code. Increase the context
only when those lines are acceptable evidence.

`--max-chars` limits both each sampled statement and each context line. A
truncated statement retains its original `text_length` and reports
`text_truncated=true`. Raise the limit only when a specific sample needs closer
inspection.

`profile-draft` creates a local JSON draft containing speakers, fonts, colors,
counts, and bounded file/line locations. It does not contain dialogue. Repeat
`--speaker` to prioritize specific characters, or omit it to select speakers
with the most source evidence. All defaults, characters, and special channels
start with `status=review`; font and color channels start with
`classification=unknown`. A speaker abbreviation, display name, route name,
and character filename must not be treated as the same identity without
project evidence.

Use bounded `samples` output to record observable voice traits. Change a
profile entry to `approved` only after user confirmation. `profile-check`
detects unsupported approvals, unclassified channels, and source-evidence
changes relative to the current index. With `--strict`, any unresolved item
blocks automation. Profiles may contain proprietary identifiers and evidence
locations, so keep them in a local ignored directory unless publication is
explicitly authorized.

After choosing a representative scene, `pilot` copies a limited number of
statements from generated source comments and places English copies in active
targets for translation. It never copies existing targets. The command refuses
stale indexes, sources with mixed newlines, outputs that overwrite an indexed
source file, and existing outputs unless `--overwrite` is explicit. The pilot
still contains game text. Keep it in a local ignored directory and do not
commit it to a public repository.

After translating the pilot, `check` confirms that its source comments still
match the index. It validates counts, pairing, speakers, attributes,
indentation, tags, interpolation, percent-format tokens, visible quote edges,
empty targets, and file format. `status=fail` is a technical blocker.
`status=review` means unchanged English, possible Latin residuals, or token
ordering still needs manual review. Review items do not return a failing exit
code by default; add `--strict` for automated gates. Lines containing only
punctuation, symbols, or proper names without Han characters are informational.

If a complete target such as a resource path must remain identical to its
source, pass `--allowed-unchanged "EXACT_TEXT"` once for each approved value.
Only source-identical targets that exactly match the full argument are removed
from unchanged-target and Latin-residual review, and the result reports them
separately. Do not use this option to hide unreviewed English sentences. For
approved proper names, use exact `--allowed-latin` values or the project
glossary.

For a real batch file, build the index before editing its active Chinese
targets. `check` then derives the expected count for the full indexed file and
validates both commented-source/active-target pairs and `old`/`new` pairs. A
changed whole-file hash is normal after target edits. Only changed English
source evidence makes the index stale. Source evidence includes the translation
language and header, block, statement type, speaker, attributes, indentation,
and source text. For a separate or partial file, keep `--expected-targets`
explicit so a missing pair cannot pass unnoticed.

When scanning original scripts, exclude generated localization trees to avoid
counting duplicates:

```text
python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py scan "PATH_TO_PROJECT" --index .renpy-translation/project-index.json --exclude "**/tl/**"
```

This repository excludes `.renpy-translation/` through `.gitignore` because
the index may contain complete game text. Do not commit local indexes,
commercial game text, unauthorized scripts, or unpublished translation corpora
to a public repository.

## Development and validation

Run the regression tests:

```text
python -m unittest discover -s tests -v
```

Validate the Skill structure:

```text
python <path-to-skill-creator>/scripts/quick_validate.py .agents/skills/renpy-en-zh-translation
```

All test fixtures contain anonymous synthetic material. This repository does
not contain commercial game files or real dialogue used for calibration.

## Repository layout

```text
.agents/skills/renpy-en-zh-translation/
├── SKILL.md
├── agents/openai.yaml
├── references/
└── scripts/index_rpy_project.py

tests/
└── skill_fixtures/
```

## Contributing

Contributions should use the smallest anonymous fixture and regression test
that reproduces a real failure mode. Do not submit game distributions,
unauthorized scripts, complete translation corpora, credentials, or local
indexes.

## License

[MIT](LICENSE)
