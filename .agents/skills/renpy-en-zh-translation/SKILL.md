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
2. Run `summary` to inspect compact counts without emitting dialogue text.
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
python scripts/index_rpy_project.py samples --index <index.json> --speaker <id> --source comments --limit 12 --context 2
```

Prefer one source-evidence corpus. Scan original scripts while excluding
generated `tl/` trees, or scan only the localization tree and sample its source
comments. Do not count original, comment, and active target copies as three
independent voice samples.

Treat this lightweight index as a discovery and sampling aid, not as a Ren'Py
AST or syntax validator. Inspect multiline definitions, custom statements, and
other forms the index does not classify.

Treat an initial budget near 100,000 total profiling tokens and a hard review
point near 150,000 as guidance for a million-word project, not as a guarantee.
Report when deeper sampling would cross the agreed budget.

## Establish voice before batch translation

When no approved project profile exists:

1. Inventory speaker identifiers, narrators, fonts, colors, styles, and unusual
   text channels.
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

## Translate by scene

Use a Ren'Py statement as the write unit, a dialogue turn or scene as the
understanding unit, and the route or game as the consistency unit.

For each batch:

1. Load only the profiles and glossary entries relevant to the current scene.
2. Reconstruct complete utterances split by `extend`, `{w}`, `{nw}`, or
   neighboring continuation statements before translating their parts.
3. Classify every string as dialogue, narration, internal monologue, menu, UI,
   or non-translatable code.
4. Record protected tokens before changing natural-language text.
5. Translate the speech act, facts, emotional force, ambiguity, and character
   relationship rather than following English word order.
6. Restore each protected token with exact spelling, count, and parameters.
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
