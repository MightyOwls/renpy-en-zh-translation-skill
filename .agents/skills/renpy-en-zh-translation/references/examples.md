# Translation Examples

## Preserve dialogue and narration roles

```renpy
# carl "I don't know."
carl "我不知道。"

# "The room was empty."
"房间里空无一人。"
```

Invalid changes include deleting `carl` or adding a speaker to the narration.

## Move emphasis with meaning

```renpy
# e "I said {i}your{/i} name."
e "我念的是{i}你的{/i}名字。"
```

Preserve tag identity and balance while attaching emphasis to the equivalent
Chinese meaning.

## Preserve interpolation

```renpy
# e "I gave the key to [player_name]."
e "我把钥匙交给了[player_name]。"
```

Do not translate or alter `[player_name]`.

## Preserve `old` and translate `new`

```renpy
old "Return"
new "返回"
```

## Read split speech as one utterance

```renpy
# e "If you really mean that—"
e "如果你真是这么想的——"
# extend " then prove it."
extend "那就证明给我看。"
```

## Preserve menu intent

```renpy
menu:
    "Tell him the truth.":
        jump tell_truth
    "Keep quiet.":
        jump stay_silent
```

```renpy
menu:
    "告诉他真相。":
        jump tell_truth
    "保持沉默。":
        jump stay_silent
```

Do not turn the first option into a promise or the second into an accusation.

## Translate one source by context

`You're unbelievable.` may become `真有你的。`, `我真服了你。`, or
`你简直不可理喻。` depending on intent and relationship. Do not lock ordinary
phrases to one context-free translation.
