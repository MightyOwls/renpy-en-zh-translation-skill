# Ren’Py 英译中 Skill 建设项目说明

> 用途：将本文件放入 Codex 项目中，作为项目背景、范围定义和第一阶段实施指南。  
> 建议文件名：`RENPLY_TRANSLATION_SKILL_PROJECT.md`

---

## 1. 项目背景

本项目拟建设一个面向 Ren’Py 游戏的英文到简体中文翻译 Skill。

这里的 **Skill** 不应仅被理解为一段普通 pre-prompt。更准确地说，它是一个可复用、可按需调用的任务执行模块，通常由以下部分构成：

- 任务触发描述；
- 执行步骤；
- 输入与输出规范；
- 语法保护规则；
- 翻译风格指南；
- 正反例；
- 术语表；
- 可选的验证脚本；
- 最终质量检查清单。

Skill 不会重新训练或修改模型权重。它的主要价值在于把一套反复执行的工作流程进行模块化、版本化和标准化。

---

## 2. 项目目标

第一版 Skill 的目标应保持狭窄、明确：

> 给定一个或多个已经生成的 Ren’Py 本地化 `.rpy` 文件，对其中的英文玩家可见文本进行简体中文翻译，同时完整保留 Ren’Py 语法、语句类型、说话人标识、变量、插值表达式、文本标签、转义字符、缩进和代码结构。

第一版重点处理：

- 角色对话；
- 旁白；
- 内心独白；
- 菜单选项；
- `old` / `new` 本地化字符串；
- 玩家可见 UI 文本；
- 已有中译文本的复核与修订。

第一版暂不处理：

- `.rpa` 解包；
- `.rpyc` 反编译；
- 字体注入；
- 安卓移植；
- Ren’Py SDK 构建；
- 游戏部署；
- 通用程序调试；
- 翻译 API 的并发、限速和批处理；
- 全自动游戏测试。

这些内容以后应拆成独立 Skill，而不是塞进一个万能 Skill。

---

## 3. 为什么要限制第一版范围

一个同时处理解包、提取、翻译、校对、字体、部署和回归测试的 Skill 会产生以下问题：

- 触发条件不清晰；
- `SKILL.md` 过长；
- token 消耗上升；
- 不同工作流互相干扰；
- 很难定位错误来源；
- 测试范围过大；
- Codex 可能在不应修改代码时修改代码；
- 语法保护规则容易被其他任务覆盖。

因此第一版只解决：

```text
已有 tl/schinese/*.rpy
        ↓
识别可翻译文本
        ↓
翻译
        ↓
保护 Ren’Py 结构
        ↓
验证
        ↓
输出文件和报告
```

---

## 4. 推荐目录结构

建议将 Skill 作为 repository-scoped skill，放在当前 Git 仓库内：

```text
<REPO_ROOT>/
├── .agents/
│   └── skills/
│       └── renpy-en-zh-translation/
│           ├── SKILL.md
│           ├── references/
│           │   ├── renpy-preservation-rules.md
│           │   ├── translation-style-guide.md
│           │   ├── glossary.csv
│           │   ├── examples.md
│           │   └── known-failure-modes.md
│           ├── scripts/
│           │   ├── validate_rpy.py
│           │   └── compare_structure.py
│           └── assets/
│               └── review-report-template.md
├── tests/
│   └── skill_fixtures/
├── RENPLY_TRANSLATION_SKILL_PROJECT.md
└── README.md
```

第一阶段可以从更简单的结构开始：

```text
.agents/skills/renpy-en-zh-translation/
├── SKILL.md
└── references/
    ├── renpy-preservation-rules.md
    ├── translation-style-guide.md
    ├── glossary.csv
    └── examples.md
```

在观察到稳定的错误模式后，再添加验证脚本。

---

## 5. Skill 的设计原则

### 5.1 按需加载

Skill 应采用渐进式内容组织：

1. `name` 和 `description` 用于判断何时调用；
2. `SKILL.md` 定义核心流程；
3. 较长资料放入 `references/`；
4. 确定性检查交给 `scripts/`；
5. 不应把所有资料永久写进 Project Instructions。

这样可以避免每一轮都加载所有专项规则。

### 5.2 静态规则与动态材料分离

稳定内容：

- Skill 执行规则；
- Ren’Py 语法保护规则；
- 风格指南；
- 输出格式；
- 术语表结构；
- QA 清单。

动态内容：

- 当前 `.rpy` 文件；
- 当前游戏的人物表；
- 当前批次的上下文；
- 当前用户要求；
- 当前错误日志。

在可控的 API 工作流中，稳定内容应放在 prompt 前部，动态文件放在后部，以提高缓存复用可能性。

### 5.3 不依赖模型“记住”

Skill 并不会因为在前一个任务中使用过，就永久写入模型权重。每次执行时，相关规则仍需成为本次运行的有效上下文。

在普通 ChatGPT 或 Codex 产品内，相同 Skill 可能受到 prompt caching 优化，但不能假定一定命中。缓存匹配通常依赖相同的连续前缀，而不是简单判断“这是同一个 Skill”。

---

## 6. 第一版 `SKILL.md` 初稿

将以下内容保存到：

```text
.agents/skills/renpy-en-zh-translation/SKILL.md
```

```markdown
---
name: renpy-en-zh-translation
description: Translate English Ren'Py localization files into Simplified Chinese while preserving Ren'Py syntax, dialogue and narration structure, text tags, interpolation, identifiers, and executable code. Use for translating or revising .rpy localization files, especially files under tl/schinese. Do not use for general prose translation, archive extraction, decompilation, engine debugging, deployment, font repair, or unrelated code modification.
---

# Ren'Py English-to-Chinese Translation

## Purpose

Translate English Ren'Py localization content into natural Simplified
Chinese without damaging executable Ren'Py syntax or changing the semantic
role of dialogue, narration, menu choices, and interface strings.

The translation must satisfy:

1. Faithfulness: preserve meaning, characterization, tone, and context.
2. Readability: produce natural Chinese rather than rigid literal translation.
3. Technical integrity: preserve all Ren'Py syntax and protected tokens.

## Expected inputs

The user may provide:

- One or more `.rpy` files.
- A directory containing generated localization files.
- A glossary of character names, locations, terminology, and preferred translations.
- Character profiles or dialogue-style references.
- Existing English-Chinese translations for revision.
- A no-translation list.
- Encoding and output-directory requirements.

Inspect the project before making assumptions when essential information is missing.
Use established project conventions when they are clearly supported by files.

## Supported content

Translate only player-visible translatable text, including:

- Character dialogue.
- Narration.
- Internal monologue.
- Menu choices.
- User-facing interface strings.
- `old` and `new` localization string pairs.
- Text inside valid Ren'Py translation blocks.

Do not translate executable code or structural identifiers.

## Protected content

Preserve exactly unless the task explicitly requires a technical repair:

- Label names.
- Translation block identifiers.
- Character and speaker identifiers.
- Python identifiers.
- Screen names.
- Image and audio names.
- File paths.
- Variable interpolation such as `[name]`.
- Percent-formatting expressions.
- Ren'Py text tags such as `{i}`, `{/i}`, `{b}`, `{/b}`,
  `{color=...}`, `{font=...}`, `{size=...}`, `{alpha=...}`,
  `{a=...}`, `{w}`, `{nw}`, and other control tags.
- Escaped characters and backslashes.
- Quote style required by the existing statement.
- Indentation and code-block structure.
- Comments containing the original source text.
- Control statements and Python blocks.

Do not remove, translate, normalize, reorder, or silently repair protected
tokens unless explicitly instructed.

## Dialogue and narration

Determine the statement type before translating.

- Preserve character dialogue as character dialogue.
- Preserve narration as narration.
- Preserve internal monologue according to source structure.
- Do not add a speaker identifier to narration.
- Do not remove or replace a speaker identifier from dialogue.
- Do not convert dialogue into a quoted narrative sentence.
- Preserve `extend` and continuation behavior.
- Use neighboring lines to infer speaker voice and context.

## Names and terminology

Read `references/glossary.csv` when available.

For every named entity:

1. Use the approved glossary entry when one exists.
2. Otherwise preserve the original name unless project files establish an approved Chinese form.
3. Do not invent inconsistent transliterations.
4. Flag unresolved ambiguity for manual review.

Apply approved terminology consistently across all files in the same task.

## Translation procedure

1. Inspect the requested files and surrounding project structure.
2. Identify the localization form used by each file.
3. Locate only player-visible source strings.
4. Record protected tokens in every source string.
5. Classify each string as dialogue, narration, internal monologue,
   menu text, UI text, or non-translatable code.
6. Read relevant glossary, style guide, neighboring lines, and character context.
7. Translate into natural Simplified Chinese.
8. Restore every protected token in the correct semantic position.
9. Compare translated statements with source statements.
10. Verify that no executable content or statement type changed.
11. Check for untranslated strings, including very short strings.
12. Run available validation scripts.
13. Review the final diff before completion.

## Short strings

Do not skip a string merely because it is short.

Translate player-visible content such as:

- Greetings.
- Interjections.
- Reactions.
- One-word dialogue.
- Brief confirmations.
- Menu choices.
- Short UI labels.
- Written sound expressions when intended for the player.

Leave a short string unchanged only when it is:

- A protected identifier.
- A variable.
- A code token.
- A file or asset name.
- Explicitly listed in the no-translation list.
- A proper name that project conventions require preserving.

## Translation quality

Prefer meaning and characterization over word-for-word correspondence.

The Chinese should:

- Sound natural in its dramatic context.
- Preserve speaker personality and relationships.
- Retain humor, irony, hesitation, aggression, intimacy, and formality.
- Avoid unnecessary expansion that harms text-box display.
- Avoid unexplained English unless it is protected or stylistically intentional.
- Remain consistent with earlier translated scenes.

Do not sanitize, embellish, summarize, or invent content.

## Uncertainty handling

Never fabricate source text or claim that a file contains wording not present.

For ambiguous lines:

1. Inspect preceding and following lines.
2. Inspect character and glossary references.
3. Choose the best-supported interpretation only when confidence is sufficient.
4. Otherwise preserve the source temporarily and report the exact file and line.

Clearly separate observed source content from suggested translation.

## File-writing rules

- Do not overwrite source scripts outside the localization directory unless explicitly instructed.
- Prefer the established `tl/schinese` structure.
- Preserve newline convention.
- Preserve required encoding.
- Avoid rewriting an entire file for a small change.
- Limit changes to the requested translation scope.
- Never modify unrelated Python or Ren'Py logic.

## Required validation

Before completion, verify:

- Every requested file was processed.
- Every translatable source string has a corresponding Chinese translation.
- Short strings were not silently omitted.
- Dialogue remains dialogue.
- Narration remains narration.
- Speaker identifiers are unchanged.
- Interpolation expressions are preserved.
- Text tags are present, correctly parameterized, and balanced.
- Quotes and escape characters remain valid.
- Indentation and translation-block structure remain valid.
- No executable Python or Ren'Py code was translated.
- Glossary terms are consistent.
- No source sentence was invented.
- The final diff contains only intended localization changes.

Run Ren'Py lint or syntax checks when the environment supports them.

## Final response

Report:

1. Files translated or revised.
2. Number of strings processed, when measurable.
3. Validation performed.
4. Unresolved ambiguities.
5. Exact files and lines requiring manual review.

Do not reproduce all translated text in chat when files were written successfully.
```

---

## 7. `references/` 文件规划

### 7.1 `renpy-preservation-rules.md`

用途：集中记录所有不可更改的 Ren’Py 结构。

建议内容：

```markdown
# Ren'Py Preservation Rules

## Never modify

- translate block identifiers
- label names
- speaker identifiers
- Python identifiers
- variable interpolation
- text-tag names and parameters
- image, audio, and file paths
- indentation
- code blocks
- escape sequences

## Example: dialogue

Source:

```renpy
# carl "I don't know."
carl "I don't know."
```

Valid:

```renpy
# carl "I don't know."
carl "我不知道。"
```

Invalid:

```renpy
# carl "I don't know."
"我不知道。"
```

## Example: narration

Source:

```renpy
# "The room was empty."
"The room was empty."
```

Valid:

```renpy
# "The room was empty."
"房间里空无一人。"
```

Invalid:

```renpy
narrator "房间里空无一人。"
```

## Example: protected tags

Source:

```renpy
e "Hello, [player_name]. {i}Are you awake?{/i}"
```

Valid:

```renpy
e "你好，[player_name]。{i}你醒着吗？{/i}"
```
```

### 7.2 `translation-style-guide.md`

用途：定义中文翻译风格，而不是技术结构。

建议包含：

- 使用自然简体中文；
- 避免生硬欧化句；
- 保留角色语气；
- 对话应适合字幕框；
- 菜单选项保持简洁；
- 不擅自加引号；
- 不擅自增加主语；
- 不弱化粗俗、讽刺或感情色彩；
- 不将人物名随意音译；
- 保持同一角色称谓一致；
- 对歌词、双关、俚语和文化梗单独标注。

### 7.3 `glossary.csv`

建议字段：

```csv
source,translation,type,status,notes
Carl,Carl,character,approved,Preserve original spelling
Echo,Echo,title,approved,Do not translate
Lake Emma,艾玛湖,location,approved,Project standard
Save,保存,ui,approved,Use consistently
Load,读取,ui,approved,Use consistently
```

可增加：

- `game`
- `character`
- `chapter`
- `source_file`
- `case_sensitive`
- `do_not_translate`
- `preferred_register`

### 7.4 `examples.md`

放真实项目中的正反例，尤其是曾经发生过的错误：

- 对话变成旁白；
- 旁白被加上 speaker；
- 人物名被翻译；
- 短句漏翻；
- `{font=...}` 丢失；
- `[variable]` 被翻译；
- 反斜杠和引号损坏；
- 模型在报告中虚构原文；
- `old` / `new` 关系处理错误；
- UI 文本与剧情文本风格混淆。

### 7.5 `known-failure-modes.md`

建议记录：

| 失败模式 | 后果 | 检测方式 | 处理规则 |
|---|---|---|---|
| speaker 被删除 | 对话变成旁白 | 结构 diff | 阻止写入 |
| speaker 被新增 | 旁白变成角色发言 | 结构 diff | 阻止写入 |
| 短字符串跳过 | 漏译 | 英文残留扫描 | 报告并修复 |
| text tag 丢失 | 显示或运行错误 | token 集合比较 | 阻止写入 |
| 插值变量改变 | 运行错误 | 插值集合比较 | 阻止写入 |
| 人名被擅自音译 | 术语不一致 | glossary 检查 | 人工复核 |
| 虚构文件原文 | 校对报告失真 | 行号与原文回查 | 拒绝输出该项 |

---

## 8. 验证脚本规划

模型擅长翻译和语境判断，但不应单独承担确定性结构验证。

建议开发：

```text
scripts/validate_rpy.py
scripts/compare_structure.py
```

### 8.1 第一阶段验证项目

脚本至少检查：

1. 文件可按指定编码读取；
2. 双引号、单引号是否闭合；
3. Ren’Py text tags 是否平衡；
4. 原文与译文的插值变量集合是否一致；
5. speaker identifier 是否变化；
6. translate block identifier 是否变化；
7. Python block 是否被修改；
8. 缩进层级是否变化；
9. `old` 与 `new` 对应关系是否损坏；
10. 是否出现明显未翻译的英文字符串；
11. 是否出现空翻译；
12. 是否出现异常全角或半角转义；
13. 修改是否超出目标目录。

### 8.2 结构化抽取思路

为每个可翻译 statement 抽取：

```python
{
    "file": "example.rpy",
    "line": 120,
    "statement_type": "dialogue",
    "speaker": "carl",
    "text": "Hello, [name].",
    "interpolations": ["[name]"],
    "tags": [],
    "indent": 4,
    "quote_type": "\""
}
```

翻译后重新抽取并比较：

```text
允许变化：
- text 的自然语言部分

禁止变化：
- statement_type
- speaker
- block identifier
- interpolation set
- tag name and parameters
- indentation
- executable code
```

### 8.3 验证结果等级

建议采用：

- `ERROR`：会导致语法、运行或结构错误，禁止提交；
- `WARNING`：可能存在漏译、术语或语义问题；
- `INFO`：统计信息；
- `REVIEW`：需要人工判断的歧义。

---

## 9. 测试集设计

第一批准备 10–20 个小型 `.rpy` fixture，不要直接用整部游戏测试。

### 9.1 必测正向案例

1. 普通角色对话；
2. 无 speaker 的旁白；
3. 内心独白；
4. `extend`；
5. 菜单选项；
6. `old` / `new` 字符串；
7. `[player_name]` 插值；
8. `{i}`、`{b}`、`{color}`；
9. `{font=fonts/TypicalWriter-G3LO.ttf}`；
10. 转义引号和反斜杠；
11. 单词级短句；
12. 多句长对话；
13. 人名与地名；
14. UI 选项；
15. 已有中译文修订；
16. 同一句在不同上下文中的不同译法。

### 9.2 必测负向案例

以下任务不应触发或不应由该 Skill 处理：

- 普通英文文章翻译；
- Ren’Py 崩溃日志分析；
- `.rpa` 解包；
- `.rpyc` 反编译；
- 字体乱码修复；
- 游戏窗口标题修改；
- API 并发性能优化；
- Python 程序重构；
- 安卓构建。

### 9.3 评分维度

每个 fixture 分别评价：

- 是否正确触发；
- 是否识别正确语句类型；
- speaker 是否保留；
- 标签是否保留；
- 插值是否保留；
- 是否漏翻；
- 术语是否一致；
- 中文是否自然；
- 是否越界修改；
- 是否虚构文件内容；
- 验证器是否发现结构错误。

---

## 10. 实施阶段

### 阶段 1：建立纯指令 Skill

目标：

- 创建目录；
- 写入 `SKILL.md`；
- 创建初始 references；
- 使用少量 fixture 测试；
- 不写复杂自动化。

完成标准：

- 能正确处理基础对话、旁白、菜单和标签；
- 不修改代码；
- 能报告歧义。

### 阶段 2：补充真实规则和案例

将实际项目中遇到的错误添加到：

- `examples.md`
- `known-failure-modes.md`
- `glossary.csv`

避免只写抽象规则。

### 阶段 3：开发确定性验证器

目标：

- speaker 对比；
- 标签与插值对比；
- 缩进与 block 对比；
- 英文残留扫描；
- JSON 或 Markdown 报告。

### 阶段 4：建立回归测试

每修复一个失败案例，就增加一个 fixture。

原则：

> 每个曾经造成实际问题的 bug，都应转化为永久测试。

### 阶段 5：拆分翻译与 QA

当单一 Skill 变得过长时，拆成：

```text
renpy-en-zh-translation
renpy-translation-qa
```

翻译 Skill 负责生成中文；QA Skill 负责审查中英文对应、术语、漏译、结构和幻觉。

### 阶段 6：扩展其他独立 Skill

以后可单独建设：

```text
renpy-string-extraction
renpy-localization-deployment
renpy-font-diagnosis
renpy-regression-debugging
renpy-project-onboarding
```

---

## 11. 与 token 和缓存有关的注意事项

### 11.1 Skill 会占用上下文

当 Skill 被调用时，其核心指令需要进入本次有效上下文，因此会占用 input tokens。

但：

- 安装 Skill 不等于每轮加载完整 Skill；
- `references/` 应按需读取；
- 脚本可直接运行，不一定全文输入模型；
- Project Instructions 应保持简短；
- 专项规则应放在 Skill，而不是全部写进项目永久指令。

### 11.2 相同 Skill 不保证缓存命中

连续任务 1、2、3 使用同一个 Skill 时：

- 相同 Skill 内容有较高缓存复用潜力；
- 但缓存通常要求相同的连续 prompt 前缀；
- 如果动态文件或对话内容出现在 Skill 之前，可能破坏缓存；
- 普通 ChatGPT/Codex 用户通常无法验证内部缓存顺序；
- 不应把缓存命中作为 Skill 正确性的设计前提。

### 11.3 设计优化

- `SKILL.md` 只放核心流程；
- 长例子放 `references/`；
- 每份 reference 聚焦单一主题；
- 避免一个超长万能 Skill；
- 不要在 Skill 中重复整个项目架构；
- 项目架构另放文档，按需读取；
- 动态术语可放项目级 glossary，而不是每次复制到核心指令。

---

## 12. 建议给 Codex 的第一条指令

可以在项目根目录向 Codex 提交：

```text
Read RENPLY_TRANSLATION_SKILL_PROJECT.md and build the first repository-scoped
version of the Ren'Py English-to-Simplified-Chinese translation skill.

Requirements:

1. Create `.agents/skills/renpy-en-zh-translation/`.
2. Create the initial `SKILL.md` based on the specification in the project document.
3. Create focused reference files:
   - `renpy-preservation-rules.md`
   - `translation-style-guide.md`
   - `glossary.csv`
   - `examples.md`
   - `known-failure-modes.md`
4. Do not build extraction, decompilation, deployment, font repair, or API batching.
5. Create a small `tests/skill_fixtures/` set covering dialogue, narration,
   interpolation, text tags, menu strings, short strings, and Python blocks.
6. Do not implement a complex validator yet. First produce a design note for
   `validate_rpy.py` and identify what can be checked deterministically.
7. Keep all changes scoped to the new Skill and test fixtures.
8. Review the final diff and report:
   - files created;
   - design decisions;
   - unresolved questions;
   - next recommended implementation step.
```

---

## 13. 第二阶段给 Codex 的指令

第一版测试完成后：

```text
Use the existing skill fixtures and observed failures to implement
`scripts/validate_rpy.py`.

The validator must operate deterministically and must not translate text.

At minimum, check:

- speaker identifier preservation;
- translation block identifier preservation;
- interpolation-token equality;
- text-tag equality and balance;
- quote and escape validity;
- indentation stability;
- Python and executable-code preservation;
- empty translations;
- likely untranslated English player-facing strings.

Produce machine-readable JSON output and a concise human-readable report.
Add regression fixtures for every detected failure mode.
Do not automatically rewrite files in this phase.
```

---

## 14. 第一版完成定义

第一版可被认为完成，当它满足：

1. 可以对生成好的 `tl/schinese/*.rpy` 文件执行翻译；
2. 不改变 speaker、block、代码、标签、变量、插值和缩进；
3. 不跳过短句；
4. 不擅自翻译人物名；
5. 不虚构源文件内容；
6. 能明确标注歧义文件和行号；
7. 具有至少 10–20 个小型测试 fixture；
8. 所有实际发现的结构错误均可被测试或验证器捕获；
9. 修改范围仅限目标本地化文件；
10. 最终 diff 可以由人工快速审查。

---

## 15. 后续可讨论的关键决策

Codex 开始建设后，需要逐步确定：

- Skill 仅翻译 `tl/schinese`，还是也支持从英文原始脚本创建翻译块；
- 对已有 `old/new` 文件，应修改哪些字段；
- 是否保留英文注释；
- 默认文件编码；
- 默认换行符；
- 人名默认保留英文还是允许 approved transliteration；
- 如何检测“一词多义”的上下文；
- 如何管理跨文件人物语气；
- 是否允许自动写回，还是先输出 patch；
- validator 是否支持 Ren’Py AST；
- 是否调用 Ren’Py lint；
- 如何处理自定义 statement 和自定义 text tag；
- 如何识别 UI 字符串与剧情文本；
- 如何标记低置信度译文；
- glossary 的优先级和覆盖规则。

第一版不必一次解决所有问题。应使用实际 fixture 和真实项目错误逐步演化。

---

## 16. 核心原则总结

```text
Skill 不是万能 prompt。
Skill 是一套范围明确、可验证、可复用的执行规程。

模型负责：
- 语境理解；
- 翻译；
- 风格；
- 歧义判断。

脚本负责：
- 结构比较；
- 标签比较；
- 插值比较；
- 代码保护；
- 确定性验证。

人工负责：
- 关键术语审批；
- 高风险歧义；
- 角色语气定稿；
- 最终发布判断。
```

最重要的工程准则：

> 先建立一个窄而可靠的翻译 Skill，再用真实失败案例、验证器和回归测试逐步扩大能力。不要从第一天就建设一个覆盖整个 Ren’Py 汉化生命周期的万能 Skill。
