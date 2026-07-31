# Glossary Schema and Precedence

Prefer a project-local CSV glossary with these fields:

```csv
source,translation,type,status,context,case_sensitive,do_not_translate,notes
```

Suggested `type` values include `character`, `location`, `organization`,
`title`, `setting`, `item`, `ui`, and `other`.

Suggested `status` values:

- `approved`: apply unless a more specific approved entry overrides it
- `preferred`: use by default but allow a justified contextual variant
- `provisional`: apply cautiously and flag conflicts
- `review`: do not treat as settled

Apply precedence in this order:

1. User instruction for the current task.
2. More specific approved project entry for the current route, character, or
   file.
3. General approved project entry.
4. Established translation consistently supported by project files.
5. Preserve the source proper name and flag uncertainty.

Treat `do_not_translate=true` as a protected project decision. Do not use the
glossary to replace substrings inside identifiers, file paths, interpolation,
or text-tag parameters.
