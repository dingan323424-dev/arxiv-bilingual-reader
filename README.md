# arxiv-bilingual-reader

把 arXiv 论文做成**逐句中英对照**的离线网页：每句英文下面紧跟一句中文。这是一个 AI 助手 skill（Claude Code、Codex 等支持 `SKILL.md` 的工具都能用），也可以直接当命令行脚本用。

- **来源**：arXiv 官方 HTML 版（LaTeXML），公式是 MathML，不经过 PDF 识别，不会乱码。
- **翻译**：必应网页翻译。免费、不用 API key、国内能直接连。
- **阅读体验**：
  - 开头有目录。
  - 引用编号和 Fig./Table/Eq./Sec. 都能点击跳转。
  - 鼠标停在这些链接上会弹出小框预览：参考文献、整张图表、公式、该节开头、脚注、缩写全称。
  - 支持深色模式，手机上也能读。
- **稳定出好结果**：`SKILL.md` 把生成、检查、批量、排错的完整流程写给 AI 助手，任何人装上后都能用自己的论文做出同样质量的网页；自带检查脚本，漏翻和缺图会被拦下。

> [!WARNING]
> 生成的译文是受版权保护论文的衍生物。大多数 arXiv 论文的许可不允许公开传播译文，请只在本机自用，不要上传或分享。本仓库不包含任何论文译文。

## 安装

**让 AI 助手来用（推荐）**：把 `skills/arxiv-bilingual-reader/` 整个文件夹放到你的工具读取 skill 的位置。

- Claude Code：`~/.claude/skills/arxiv-bilingual-reader/`（全局），或项目里的 `.claude/skills/arxiv-bilingual-reader/`。
- Codex 等其他支持 Agent Skills 的工具：放到它约定的 skills 目录，例如项目里的 `.agents/skills/`。
- 也可以直接对助手说：“读一下这个仓库的 `skills/arxiv-bilingual-reader/SKILL.md`，照着把 arXiv 1706.03762 做成中英对照。”

```bash
git clone https://github.com/dingan323424-dev/arxiv-bilingual-reader.git
cp -R arxiv-bilingual-reader/skills/arxiv-bilingual-reader ~/.claude/skills/
```

**依赖**：Python 3.8+，以及 `requests`、`lxml`。不想动系统 Python 就用 uv：

```bash
uv run --with requests --with lxml python skills/arxiv-bilingual-reader/scripts/bilingual_arxiv.py --selftest
```

## 用法

装好 skill 后直接跟助手说，例如：

- “把 arXiv 1706.03762 做成中英对照。”
- “这几篇论文帮我都做成中英对照：……”

助手会自己运行脚本、检查结果，再打开网页给你看。也可以手动运行（`$SKILL` 指 skill 所在目录）：

```bash
SKILL=~/.claude/skills/arxiv-bilingual-reader
# 一篇：输出到 ./arxiv-bilingual/Transformer/index.html（一篇 5–10 分钟）
python3 $SKILL/scripts/bilingual_arxiv.py 1706.03762 Transformer
# 检查：漏翻、缺图应为 0
python3 $SKILL/scripts/check_bilingual.py arxiv-bilingual/Transformer
# 批量：清单每行“arXiv号<Tab>文件夹名”，两路并行
python3 $SKILL/scripts/batch.py my-list.tsv --jobs 2
# 只改了样式或预览脚本时，不重新翻译，几秒更新已生成的网页
python3 $SKILL/scripts/bilingual_arxiv.py --restyle arxiv-bilingual/*/index.html
```

完整流程、检查标准和常见故障见 [`SKILL.md`](skills/arxiv-bilingual-reader/SKILL.md)。

## 局限

- 只支持有 HTML 版的 arXiv 论文。较老的论文或源文件转换失败的论文没有 HTML 版，请用 [PDFMathTranslate-next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next) 之类的 PDF 翻译工具。
- 必应是机器翻译，术语和数字以英文为准；同一篇论文两次生成的译文可能略有不同。
- 用的是必应网页版的非官方接口，可能被限流或失效。
- 表格内容和参考文献不翻译。

## English

`arxiv-bilingual-reader` turns an arXiv paper's official HTML version into an offline page where every English sentence is followed by its Chinese translation (Bing, free, no API key). It keeps MathML formulas and figures, and adds a table of contents, clickable references and hover previews. It ships as an agent skill (`skills/arxiv-bilingual-reader/SKILL.md`) plus plain Python scripts. Generated translations are for personal use only; do not redistribute them.

## 许可证与致谢

- 本仓库以 [AGPL-3.0-or-later](LICENSE) 发布。
- 必应翻译部分的做法沿用自 [PDFMathTranslate-next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next) 的 `BingTranslator`（AGPL-3.0）。
- 论文 HTML 由 [arXiv](https://arxiv.org) 用 LaTeXML 生成，论文版权归原作者。
