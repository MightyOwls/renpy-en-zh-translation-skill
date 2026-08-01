# Ren'Py English-to-Chinese Translation Skill

A repository-scoped Codex Skill for translating and reviewing English Ren'Py
localization files as natural Simplified Chinese while preserving executable
structure.

这是一个面向 Codex 的仓库级 Skill，用于翻译或审校英文 Ren'Py 本地化
文件。它把语法保护视为硬性条件，并在此基础上处理人物声线、叙事语域、
称谓、菜单意图和中文表达。

> Status: early development. Use version control, inspect the final diff, and
> run available Ren'Py checks before distributing a translated game.

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

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py samples --index .renpy-translation/project-index.json --speaker SPEAKER_ID --source comments --limit 12 --context 0

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py samples --index .renpy-translation/project-index.json --speaker SPEAKER_ID --file "routes/ROUTE_NAME*.rpy" --source comments --limit 12 --context 0

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py pilot --index .renpy-translation/project-index.json --file "routes/ROUTE_NAME.rpy" --start-line 100 --limit 40 --output .renpy-translation/pilot/scene.rpy

python .agents/skills/renpy-en-zh-translation/scripts/index_rpy_project.py check .renpy-translation/pilot/scene.rpy --index .renpy-translation/project-index.json --source-file "routes/ROUTE_NAME.rpy" --expected-targets 40
```

`--file` 接受项目相对的 POSIX 风格 glob，可重复指定；它适合把同一 speaker
在不同路线中的样本分开，避免其他场景稀释人物声线证据。
如果项目用包住整段文本的可见引号区分发言与其他频道，可再使用
`--outer-quotes present` 或 `--outer-quotes absent` 分组。该选项只识别句法形式，
仍须结合场景确认它表示对白、心理活动还是其他功能。
同理，`kind=narration` 只表示扫描器未发现 speaker 标识，其中仍可能混有旁白、
内心活动、匿名发言或项目自定义频道。

若现有译文未获准作为风格证据，应从 `--context 0` 开始。上下文是原文件中的
原始邻行，即使中心样本使用 `--source comments`，邻行仍可能包含活动译文或代码；
只有在这些内容可被纳入证据时才提高上下文行数。

确定校准场景后，`pilot` 会从注释原文复制限定数量的 statement，并把英文
副本作为待译的活动目标；现有活动译文不会进入输出。该命令会拒绝过期索引、
混合换行源文件、覆盖任何已索引源文件，以及未显式指定 `--overwrite` 的已有
输出。生成文件仍包含游戏原文，必须保存在本地忽略目录，不得提交到公开仓库。

完成试译后，`check` 会验证源注释仍与项目索引一致，并检查数量、配对、speaker、
属性、缩进、标签、插值、percent-format、可见引号边界、空译和文件格式。
`status=fail` 表示技术阻断；`status=review` 表示仍有未改英文、拉丁词残留候选或
标记顺序变化等待人工确认。默认情况下复核项不会返回失败码；自动化流程可加
`--strict`。没有汉字的标点、符号或专名行只作为信息报告。

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

## License

[MIT](LICENSE)
