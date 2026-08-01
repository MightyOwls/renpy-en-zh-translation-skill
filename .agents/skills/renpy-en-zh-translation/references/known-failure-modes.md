# Known Failure Modes

| Failure | Consequence | Detection | Response |
|---|---|---|---|
| Remove a speaker | Dialogue becomes narration | Statement-role comparison | Block completion |
| Add a speaker | Narration becomes dialogue | Statement-role comparison | Block completion |
| Change a block identifier | Translation lookup fails | Identifier comparison | Block completion |
| Change statement indentation | A statement leaves or changes its block | Source/target indentation comparison | Block completion |
| Lose, duplicate, or normalize a tag | Display or runtime defect | Source-relative token sequence | Block completion |
| Alter interpolation | Runtime error or wrong value | Exact token comparison | Block completion |
| Alter a percent-format token | Runtime error or wrong substituted value | Exact percent-format token comparison | Block completion |
| Reorder a control tag | Timing or flow changes | Ordered token comparison | Review or block |
| Pair quotation marks inside every `extend` fragment | A cross-statement speech channel is split or changed | Source-relative visible-quote edge comparison | Restore opening and closing marks to their corresponding fragments |
| Skip a short string | Visible untranslated text | Residual-English review | Translate or report |
| Require every target to contain Han characters | False positives on punctuation, symbols, names, or sound-only lines | Compare source/target change plus residual text | Review no-Han targets instead of failing them automatically |
| Translate a proper name ad hoc | Terminology drift | Glossary/profile review | Revert or approve |
| Force one phrase to one translation | Character and context flattening | Scene review | Translate by intent |
| Infer voice from font alone | False characterization | Evidence review | Sample repeated usage |
| Treat fallback, UI, or redaction fonts as voices | False characterization | Marker-role classification | Exclude from voice profile |
| Treat a speaker abbreviation or filename as a confirmed display name | Wrong character mapping | Profile evidence review | Confirm definitions and project mapping |
| Auto-approve a generated voice profile | Unsupported style becomes project policy | Profile status validation | Generate `review` entries and require confirmation |
| Remove a source font without a policy | Unreviewed visual drift | Typography-exception review | Preserve or seek approval |
| Apply a regional dialect by stereotype | Adds unsupported setting | Voice-profile review | Use neutral register cues |
| Load a whole large corpus into context | Excessive token use | Workflow audit | Index locally and sample |
| Reprofile every game update | Repeated cost and drift | Index/profile version review | Analyze deltas only |
| Treat every whole-file hash change as a stale index | Valid target edits cannot be checked | Immutable source-evidence signature | Block only when source evidence changes |
| Invent source text in a report | Invalid QA evidence | Re-open cited line | Remove unsupported claim |
| Repair unrelated code | Scope and regression risk | Final diff review | Revert unrelated change |
