---
name: renpy-en-zh-translation
description: Translate or revise English Ren'Py localization files as natural Simplified Chinese while preserving statement roles, speaker identifiers, translation blocks, interpolation, text tags, escapes, indentation, and executable code. Use for player-visible dialogue, narration, internal monologue, menu choices, UI strings, and old/new pairs in .rpy files, especially generated files under tl/schinese. Also use to establish project terminology, character voices, narrator registers, and font- or style-signaled voices before translation. Do not use for archive extraction, .rpyc decompilation, font installation, engine debugging, builds, deployment, or unrelated code changes.
---

# Ren'Py English-to-Chinese Translation

## Contract

Translate player-visible English into natural Simplified Chinese without
changing the executable or dramatic structure of the Ren'Py statements.

Treat technical integrity as a pass/fail gate. Within that gate, prioritize:

1. Narrative meaning, intent, relationships, clues, and choice consequences.
2. Character voice and scene-level continuity.
3. Natural Chinese expression and appropriate text-box rhythm.

Do not sanitize, embellish, summarize, or invent source content.

## Load the right guidance

Before translating:

- Read [references/renpy-preservation-rules.md](references/renpy-preservation-rules.md).
- Read [references/translation-style-guide.md](references/translation-style-guide.md).
- Read [references/voice-and-register-guidance.md](references/voice-and-register-guidance.md)
  when named speakers, narrators, typography, supernatural voices, or other
  distinct registers occur.
- Read [references/project-profile-schema.md](references/project-profile-schema.md)
  before proposing or updating a persistent project translation profile.
- Read [references/glossary-schema.md](references/glossary-schema.md) before
  creating, interpreting, or merging a glossary.
- Read [references/examples.md](references/examples.md) and
  [references/known-failure-modes.md](references/known-failure-modes.md) when
  resolving an unfamiliar form, testing the skill, or investigating a failure.

Prefer project-provided profiles, glossaries, character notes, and approved
translations over bundled examples.

## Inspect scope

1. Resolve the exact requested files and output location.
2. Inspect neighboring statements and relevant project definitions read-only.
3. Identify the localization forms used: commented source plus active target,
   `old`/`new`, dialogue, narration, menu, UI, or a custom statement.
4. Detect encoding and newline convention before writing.
5. Find project terminology, no-translation lists, character notes, and an
   existing translation profile.
6. Do not modify source scripts or executable logic outside the requested
   localization scope.

## Control large-project context

Never print or load a large project corpus into model context merely to learn
its speakers. For a project that exceeds practical direct inspection, has many
voices, or receives continuing updates:

1. Run `scripts/index_rpy_project.py scan` to build a local read-only index.
2. Run `summary` to inspect compact source/target counts, pairing coverage,
   structural-difference counts, file-format conventions, and bounded
   file/line locations without emitting dialogue text.
3. Run `samples` with explicit limits to retrieve representative evidence for
   one speaker or voice channel at a time.
4. Cap the first profiling pass before requesting more evidence. Prefer major,
   unusual, conflicting, or high-risk voices.
5. Reuse the saved index and profile. On later game versions, analyze only new
   or changed files and newly observed voice signals.

```text
python scripts/index_rpy_project.py scan <project> --index <index.json>
python scripts/index_rpy_project.py scan <project> --index <index.json> --exclude "**/tl/**"
python scripts/index_rpy_project.py summary --index <index.json>
python scripts/index_rpy_project.py samples --index <index.json> --speaker <id> --source evidence --limit 12 --context 0
python scripts/index_rpy_project.py samples --index <index.json> --speaker <id> --file "routes/<route>*.rpy" --source evidence --limit 12 --context 0
python scripts/index_rpy_project.py samples --index <index.json> --font <marker> --source evidence --limit 5 --context 0
python scripts/index_rpy_project.py samples --index <index.json> --color <marker> --source evidence --limit 5 --context 0
python scripts/index_rpy_project.py profile-draft --index <index.json> --output .renpy-translation/project-profile.json --speaker <id> --speaker <id>
python scripts/index_rpy_project.py profile-check .renpy-translation/project-profile.json --index <index.json>
python scripts/index_rpy_project.py pilot --index <index.json> --file "routes/<route>.rpy" --start-line <line> --limit 40 --output .renpy-translation/pilot/<scene>.rpy
python scripts/index_rpy_project.py check .renpy-translation/pilot/<scene>.rpy --index <index.json> --source-file "routes/<route>.rpy" --expected-targets 40
python scripts/index_rpy_project.py check "routes/<route>.rpy" --index <index.json> --source-file "routes/<route>.rpy"
```

Prefer one source-evidence corpus. Scan original scripts while excluding
generated `tl/` trees, or scan only the localization tree and sample its source
comments. Do not count original, comment, and active target copies as three
independent voice samples.

When an existing target translation is not approved style evidence, use
`--source evidence --context 0`. This selects commented source plus `old`
strings when available, or active original statements when no localization
source evidence exists. Context lines are raw neighboring file lines and can
still include active targets or code. Increase context only when those
neighboring lines are acceptable evidence.

`--max-chars` bounds both each selected statement and each context line. A
truncated statement reports its original `text_length` and
`text_truncated=true`; raise the limit only for a specific sample that needs
closer reading.

Use `--outer-quotes present`, `absent`, and `partial` when a project uses
escaped visible quotation marks to distinguish text channels. `partial`
captures one-sided quote edges across interrupted or continued statements;
`absent` requires neither edge, ignoring leading or trailing text tags. Treat
these only as syntactic splits until surrounding scenes confirm what each form
means. Likewise, `kind=narration` means only that the scanner found no speaker
token; it may include narration, internal thought, anonymous speech, or custom
modes.

Treat this lightweight index as a discovery and sampling aid, not as a Ren'Py
AST or syntax validator. Inspect multiline definitions, custom statements, and
other forms the index does not classify.

After selecting a representative scene, use `pilot` to create a bounded local
calibration file from generated source comments. It preserves each original
`translate` header and duplicates the English source into the active statement;
it never copies existing targets. Keep the output under an ignored local
directory because it contains source text. The command refuses stale indexes,
mixed-newline sources, indexed source-file outputs, and existing outputs unless
`--overwrite` is explicit.

After translating the pilot, run `check` against the same project index and
source file. Treat `status=fail` as a technical blocker. Treat `status=review`
as a bounded manual queue for unchanged targets, likely Latin residuals, or
token-order changes; use `--strict` when those review items must also fail an
automated gate. Lines without Han characters are informational and require
contextual review rather than automatic failure. Use repeated `--allowed-latin`
only for exact project-approved words.

To validate a complete indexed batch file, build the index before editing and
run `check` on that same file after translation. The command infers the expected
count and validates both commented-source/active-target pairs and `old`/`new`
pairs. A changed whole-file hash is informational because target edits are
expected; changed source evidence remains a hard failure. Source evidence
includes the translation language and header, block, statement role, speaker,
attributes, indentation, and source text. Keep `--expected-targets` explicit
for a separate or partial file because the index cannot infer omitted pairs.

Treat an initial budget near 100,000 total profiling tokens and a hard review
point near 150,000 as guidance for a million-word project, not as a guarantee.
Report when deeper sampling would cross the agreed budget.

## Establish voice before batch translation

When no approved project profile exists:

1. Inventory speaker identifiers, dialogue attributes such as pose or delivery
   markers, narrators, fonts, colors, styles, and unusual text channels.
2. Sample each important voice across chapters, interlocutors, emotions, and
   style variants rather than taking only its first lines.
3. Infer observable register features. Do not map class, species, or typography
   directly to stereotyped Chinese speech.
4. Separate project evidence from inference and mark confidence.
5. Propose high-impact choices for approval: names, address terms, formality,
   literary level, dialect policy, archaic language, and special voices.
6. Translate a short representative scene as calibration before a large batch.
7. Reuse approved decisions and report later evidence that conflicts with them.

For a small, low-risk request, use a provisional in-memory profile and report
assumptions instead of creating persistent project metadata without permission.

For an approved persistent local profile, use `profile-draft` to create a JSON
draft containing stable identifiers, marker candidates, source-evidence counts,
and bounded file/line locations without dialogue text. Specify repeated
`--speaker` values when the user has identified priority characters; otherwise
the command selects frequent source-evidence speakers. Treat abbreviated
speaker identifiers, display names, filenames, and route names as separate
evidence until their mapping is confirmed.

Every generated default, character, and channel starts with `status=review`.
Inspect the planned locations with bounded `samples`, write only evidence-backed
observations, and request approval for high-impact choices before changing a
status to `approved`. Classify generated font and color channels before assigning
a register; `classification=unknown` cannot be approved. Run `profile-check`
with the current index to detect invalid approvals or changed source evidence.
Use `--strict` only when the current workflow requires every profile item to be
approved. Keep the JSON draft local unless the user explicitly authorizes
sharing project-specific identifiers and evidence locations.

## Translate by scene

Use a Ren'Py statement as the write unit, a dialogue turn or scene as the
understanding unit, and the route or game as the consistency unit.

For each batch:

1. Load only the profiles and glossary entries relevant to the current scene.
2. Reconstruct complete utterances split by `extend`, `{w}`, `{nw}`, or
   neighboring continuation statements before translating their parts.
   When visible quotation marks span multiple statements, preserve which
   source-relative fragment opens and closes the quotation after applying the
   approved target punctuation.
3. Classify every string as dialogue, narration, internal monologue, menu, UI,
   or non-translatable code.
4. Record protected tokens before changing natural-language text.
5. Translate the speech act, facts, emotional force, ambiguity, and character
   relationship rather than following English word order.
6. Restore each protected token with exact spelling, count, parameters, and
   the source's explicit or implicit closing behavior.
   Reposition inline interpolation or emphasis only when Chinese syntax or
   semantic attachment requires it. Preserve control-tag order and timing.
7. Keep menu choices concise while preserving player intent and likely
   consequences.
8. Preserve deliberate ambiguity and content intensity.

## Handle localization forms

- In a generated commented-source pair, preserve the English source comment
  and translate only the corresponding active statement.
- In an `old`/`new` pair, preserve `old` and translate or revise only `new`.
- Preserve the speaker on dialogue and preserve the absence of a speaker on
  narration.
- Preserve `extend` and custom statement roles.
- Preserve visible-quotation opening and closing boundaries across dialogue
  and `extend` fragments; do not force each fragment into a self-contained
  quote pair.
- Translate short player-visible strings; do not skip greetings, reactions,
  menu labels, sound expressions, or one-word replies merely because they are
  short.
- Leave names unchanged unless an approved project term establishes a Chinese
  form.

## Validate and report

Before completion:

1. Compare the final diff with the requested scope.
2. Verify speakers, block identifiers, statement roles, tags, interpolation,
   escapes, indentation, and executable code.
3. Check for empty targets and likely untranslated English, including short
   strings.
4. Check terminology, address terms, voice consistency, and scene continuity.
5. Run available deterministic checks and Ren'Py lint when supported.
   For a generated calibration pilot, run `scripts/index_rpy_project.py check`
   with the original local index and source file. Supply the expected target
   count for a separate or partial calibration file.
6. Re-open every reported ambiguity at the cited file and line. Never invent a
   source quotation.

Report:

- files translated or revised;
- measurable statement counts;
- validation performed;
- profile or glossary decisions made;
- unresolved ambiguities with exact files and lines;
- any budget, parser, or project-context limitation.

Do not reproduce all translated text in chat after writing files successfully.
