# Ren'Py 英译中翻译 Skill

[English](README.md) | 简体中文

这是一个面向 Codex 的仓库级 Skill，用于将英文 Ren'Py 本地化文件翻译或
审校为自然的简体中文。它把可执行结构的保真视为硬性条件，并在此基础上
处理人物声线、叙事语域、称谓、菜单意图和中文表达。

> 状态：[v0.1.0](https://github.com/MightyOwls/renpy-en-zh-translation-skill/releases/tag/v0.1.0)
> 是首个完整公开版本。分发翻译后的游戏前，仍应使用版本控制、检查最终差异，
> 并运行项目可用的 Ren'Py 检查。

## 功能

- 翻译或修订角色对话、旁白、内心独白、菜单、UI 和 `old`/`new` 字符串。
- 保留 speaker、translation block、插值、文本标签、转义、缩进和代码结构。
- 在批量翻译前建立术语、人物声线、叙事语域和特殊文字通道档案。
- 使用本地索引扫描大型项目，只向模型提供汇总数据和有限样本。
- 从注释原文生成有限、干净的本地校准片段，不复制现有译文。
- 译后只输出统计和有限行号，区分技术失败、人工复核项和信息项。
- 对比注释原文与活动译文，报告配对覆盖和结构差异的位置。
- 区分受保护标记的增删与仅因中文语序产生的换序。
- 汇总编码、换行约定和 BOM，定位可能破坏文件格式的混合换行。

核心入口见
[SKILL.md](.agents/skills/renpy-en-zh-translation/SKILL.md)。详细规则位于
[references/](.agents/skills/renpy-en-zh-translation/references/)。

## 不在范围内

本 Skill 不负责：

- `.rpa` 解包或 `.rpyc` 反编译；
- 字体安装、游戏引擎调试或代码修复；
- Ren'Py 构建、安卓移植和发布；
- 无人工复核的整部游戏一键翻译。

索引脚本是轻量发现与抽样工具，不是完整的 Ren'Py AST 或语法验证器。
复杂的多行定义、自定义 statement 和项目特有语法仍需人工检查。

## 安装

将以下目录复制到目标仓库的相同位置：

```text
.agents/skills/renpy-en-zh-translation/
```

然后在 Codex 中打开目标仓库，并提出类似请求：

```text
Use $renpy-en-zh-translation to translate game/tl/schinese/chapter1.rpy.
```

或者：

```text
使用 renpy-en-zh-translation，先分析这些角色的说话方式并提出声线方案，
不要修改文件，等我确认后再开始翻译。
```

## 大型项目的低-token工作流

索引在本地读取 `.rpy` 文件。`scan` 和 `summary` 只输出统计与有限的差异
位置，不输出完整台词；只有 `samples` 会按明确上限返回原文证据。

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

扫描路径决定索引内的相对文件名。若 `scan` 的输入是单个 `.rpy` 文件，索引根目录
就是该文件的父目录，后续 `pilot --file` 和 `check --source-file` 应使用工具报告的
索引相对名（通常是文件 basename），而不是扫描命令中原有的长路径。

`summary` 会分别报告注释原文/活动目标配对和 `old`/`new` 配对；不要把两类源证据
的合计当成某个校准片段的目标数。应按索引相对文件名、原文行号和显式 `--limit`
限定 `pilot`，并在 `check` 中填写该片段实际应有的 `--expected-targets`。

`--file` 接受项目相对的 POSIX 风格 glob，可重复指定；它适合把同一 speaker
在不同路线中的样本分开，避免其他场景稀释人物声线证据。
如果项目用包住整段文本的可见引号区分发言与其他频道，可再使用
`--outer-quotes present`、`absent` 或 `partial` 分组。`partial` 表示只有一侧
可见引号，常见于被打断或跨 statement 延续的发言；`absent` 表示两侧都没有，
并忽略字符串边缘的文本标签。这些选项只识别句法形式，仍须结合场景确认它表示
对白、心理活动还是其他功能。
同理，`kind=narration` 只表示扫描器未发现 speaker 标识，其中仍可能混有旁白、
内心活动、匿名发言或项目自定义频道。

若现有译文未获准作为风格证据，应使用 `--source evidence --context 0`。该模式
优先选择注释原文与 `old`，若工程没有本地化源证据则选择原始脚本的活动语句。
上下文仍是原文件中的原始邻行，可能包含活动译文或代码；只有在这些内容可被
纳入证据时才提高上下文行数。

`--max-chars` 会同时限制样本正文与每一行上下文。若正文被截断，结果会保留原始
`text_length` 并标记 `text_truncated=true`；只有确实需要细读某一条时才提高上限。

`profile-draft` 会生成本地 JSON 档案草案，包含 speaker、字体、颜色、数量和有限
文件/行号，不包含台词。可重复使用 `--speaker` 指定优先角色；若省略，工具选择
高频源证据 speaker。所有默认规则、人物和特殊频道都以 `status=review` 创建，
字体及颜色频道的初始分类为 `unknown`。speaker 缩写、显示名、路线名和角色文件名
不能自动视为同一身份，必须根据项目证据确认。

使用有限 `samples` 填写可观察的声线特征，取得用户确认后再把对应状态改为
`approved`。`profile-check` 会检查无证据批准、未分类频道和当前索引的源证据
变化；加 `--strict` 后，任何仍待确认的项目都会阻止自动流程。项目档案包含
专有标识和证据位置，未经明确授权也应留在本地忽略目录。

确定校准场景后，`pilot` 会从注释原文复制限定数量的 statement，并把英文
副本作为待译的活动目标；现有活动译文不会进入输出。该命令会拒绝过期索引、
混合换行源文件、覆盖任何已索引源文件，以及未显式指定 `--overwrite` 的已有
输出。生成文件仍包含游戏原文，必须保存在本地忽略目录，不得提交到公开仓库。

完成试译后，`check` 会验证源注释仍与项目索引一致，并检查数量、配对、speaker、
属性、缩进、标签、插值、percent-format、可见引号边界、空译和文件格式。
`status=fail` 表示技术阻断；`status=review` 表示仍有未改英文、拉丁词残留候选或
标记顺序变化等待人工确认。默认情况下复核项不会返回失败码；自动化流程可加
`--strict`。没有汉字的标点、符号或专名行只作为信息报告。

若资源路径等完整目标必须与原文保持完全一致，可重复传入
`--allowed-unchanged "EXACT_TEXT"`。只有 source 与 target 相同且全文精确匹配
参数的语句才会从未改目标和拉丁残留复核中排除，并在结果中单独计数。不要用它
隐藏尚未审阅的英文句子；普通批准专名仍应使用精确的 `--allowed-latin` 或项目
术语表。

检查实际批次文件时，应先建立索引，再直接编辑该文件的活动中文目标。`check`
会从索引推导完整文件的预期数量，同时检查注释配对和 `old`/`new`。中文目标变化
会改变整文件哈希，这是正常信息；只有英文源证据发生变化才会被视为索引失效。
源证据包括 translation 语言与头部、block、statement 类型、speaker、属性、
缩进和原文。若检查的是独立或部分文件，仍须显式提供 `--expected-targets`，防止
整对语句被遗漏。

如果扫描原始脚本，应排除生成的本地化树，避免重复统计：

```text
python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py scan "PATH_TO_PROJECT" --index .renpy-translation/project-index.json --exclude "**/tl/**"
```

`.renpy-translation/` 已被本仓库的 `.gitignore` 排除，因为索引可能包含
完整游戏文本。不要把索引、商业游戏文本或未经授权的翻译语料提交到公开
仓库。

## 开发与验证

运行回归测试：

```text
python -m unittest discover -s tests -v
```

验证 Skill 结构：

```text
python <path-to-skill-creator>/scripts/quick_validate.py .agents/skills/renpy-en-zh-translation
```

测试夹具均为匿名合成内容。仓库不包含用于校准的商业游戏文件或真实台词。

## 项目结构

```text
.agents/skills/renpy-en-zh-translation/
├── SKILL.md
├── agents/openai.yaml
├── references/
└── scripts/index_rpy_project.py

tests/
└── skill_fixtures/
```

## 参与贡献

欢迎提交针对真实失败模式的最小匿名夹具和回归测试。请勿提交游戏本体、
未经授权的脚本、完整翻译语料、凭据或本地索引。

## 许可证

[MIT](LICENSE)
