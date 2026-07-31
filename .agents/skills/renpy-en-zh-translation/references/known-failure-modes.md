# Known Failure Modes

| Failure | Consequence | Detection | Response |
|---|---|---|---|
| Remove a speaker | Dialogue becomes narration | Statement-role comparison | Block completion |
| Add a speaker | Narration becomes dialogue | Statement-role comparison | Block completion |
| Change a block identifier | Translation lookup fails | Identifier comparison | Block completion |
| Lose, duplicate, or normalize a tag | Display or runtime defect | Source-relative token sequence | Block completion |
| Alter interpolation | Runtime error or wrong value | Exact token comparison | Block completion |
| Reorder a control tag | Timing or flow changes | Ordered token comparison | Review or block |
| Skip a short string | Visible untranslated text | Residual-English review | Translate or report |
| Translate a proper name ad hoc | Terminology drift | Glossary/profile review | Revert or approve |
| Force one phrase to one translation | Character and context flattening | Scene review | Translate by intent |
| Infer voice from font alone | False characterization | Evidence review | Sample repeated usage |
| Treat fallback, UI, or redaction fonts as voices | False characterization | Marker-role classification | Exclude from voice profile |
| Remove a source font without a policy | Unreviewed visual drift | Typography-exception review | Preserve or seek approval |
| Apply a regional dialect by stereotype | Adds unsupported setting | Voice-profile review | Use neutral register cues |
| Load a whole large corpus into context | Excessive token use | Workflow audit | Index locally and sample |
| Reprofile every game update | Repeated cost and drift | Index/profile version review | Analyze deltas only |
| Invent source text in a report | Invalid QA evidence | Re-open cited line | Remove unsupported claim |
| Repair unrelated code | Scope and regression risk | Final diff review | Revert unrelated change |
