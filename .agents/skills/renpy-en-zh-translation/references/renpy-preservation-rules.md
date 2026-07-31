# Ren'Py Preservation Rules

Treat structural preservation as a hard gate. Change only the
natural-language payload of player-visible statements.

## Preserve exactly

- `translate` block identifiers and label names
- speaker and Character identifiers
- statement roles, including narration, dialogue, `extend`, `old`, and `new`
- Python identifiers, expressions, blocks, and control flow
- image, audio, screen, style, file, and font identifiers
- quote and escape syntax required by the statement
- indentation and block structure
- source comments in generated localization files
- newline convention and established encoding

## Preserve inline tokens

Preserve the spelling, count, parameters, and valid nesting of:

- interpolation such as `[player_name]`, `[count!q]`, and format expressions
- percent-format expressions
- emphasis tags such as `{i}`, `{/i}`, `{b}`, and `{/b}`
- parameterized tags such as `{color=#fff}`, `{font=...}`, and `{size=+5}`
- links and custom text tags
- control tags such as `{w}`, `{p}`, `{nw}`, and `{fast}`

Move interpolation or emphasis tags only when Chinese syntax requires it and
the tag remains attached to the same meaning. Preserve the relative order and
timing semantics of control tags.

Compare protected-token sequences as well as sets. A set comparison alone
misses duplicates and invalid nesting.

## Generated dialogue and narration

```renpy
# carl "I don't know."
carl "我不知道。"

# "The room was empty."
"房间里空无一人。"
```

Do not remove `carl` from the first statement or add a narrator identifier to
the second.

## `old` and `new`

```renpy
old "Save"
new "保存"
```

Keep `old` as source evidence. Translate or revise only `new` unless the user
explicitly requests a technical repair.

## Split speech

Read `extend` and control-tag fragments as one utterance for meaning, then
write each translated fragment back to its original structural statement.

## Never repair silently

If the source contains malformed syntax, conflicting tags, or an apparent
code defect, report it separately. Do not mix an unrequested technical repair
into a translation diff.
