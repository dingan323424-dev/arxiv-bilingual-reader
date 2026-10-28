---
name: arxiv-bilingual-reader
description: Turn arXiv papers into offline Chinese-English sentence-by-sentence reading pages from arXiv's official HTML version, translated by Bing (free, no API key, reachable from mainland China), keeping formulas, figures, clickable references, a table of contents and hover previews. Use when the user wants to read an arXiv paper in Chinese and English side by side, or to batch-translate a reading list. 触发词：中英对照、逐句对照、论文翻译、双语阅读、把 arXiv 论文翻成中文、批量翻译精读论文、translate arXiv paper bilingual.
compatibility: Python 3.8+ with requests and lxml; network access to arxiv.org and www.bing.com; any modern browser to read the output.
metadata:
  kind: capability-uplift
  version: 1.0.0
---

# arxiv-bilingual-reader

把 arXiv 论文做成“每句英文下面紧跟一句中文”的离线网页。翻译交给必应，你（AI 助手）负责：查 arXiv 号、跑脚本、检查结果、打开给用户看、处理失败。

## 何时触发

- 用户想中英对照地读某篇 arXiv 论文：“把 1706.03762 翻成中英对照”“帮我把 Attention Is All You Need 做成双语版”“这篇论文我想中英文一起看”。
- 用户给一串论文要批量做（读书会、精读清单、综述阅读）。
- 用户反馈已生成网页的排版或预览问题，要改样式（用 `--restyle`，不用重新翻译）。

## 不适用

- **arXiv 没有 HTML 版**（较老的论文，或作者源文件转换失败）：脚本会直接报错退出。改用 PDF 翻译工具，如 [PDFMathTranslate-next](https://github.com/PDFMathTranslate-next/PDFMathTranslate-next)。
- **不在 arXiv 上的论文**（期刊 PDF、知网等）：本 skill 只吃 arXiv 的 HTML。
- **要高质量人工级译文**：必应是机器翻译，术语和数字以英文为准。
- **不要你在对话里逐句翻全文**：既慢又贵，也没有对照排版。翻译一律交给脚本。

## 准备（每台机器一次）

1. 找到本 skill 的目录（下文记作 `$SKILL_DIR`，里面有 `scripts/`），在用户想放输出的目录下运行命令。
2. 确认依赖：`python3 -c "import requests, lxml"`。缺了就任选一种，不要往系统 Python 里硬装：
   - 有 uv：把下文的 `python3` 换成 `uv run --with requests --with lxml python`。
   - 否则建虚拟环境：`python3 -m venv ~/.venvs/arxiv-bilingual && ~/.venvs/arxiv-bilingual/bin/pip install requests lxml`，下文的 `python3` 换成 `~/.venvs/arxiv-bilingual/bin/python`。
3. 自检：`python3 "$SKILL_DIR/scripts/bilingual_arxiv.py" --selftest` 应输出 `selftest ok`。
4. 网络：要能连 `arxiv.org` 和 `www.bing.com`。在有网络白名单的沙箱里运行时，先放行这两个域名。

## 做一篇

1. **拿到 arXiv 号**：用户给的号、`arxiv.org/abs|pdf|html/...` 链接都行（脚本自己解析，带版本号如 `v2` 会保留）。只给了论文名时，先上 arXiv 搜到号，告诉用户你找到的是哪篇再继续。
2. **运行**（一篇 5–10 分钟，大部分时间花在翻译上；能放后台就放后台）：

   ```bash
   python3 "$SKILL_DIR/scripts/bilingual_arxiv.py" 1706.03762 Transformer --out arxiv-bilingual
   ```

   第二个参数是文件夹名（可省略，默认用 arXiv 号）。输出：`arxiv-bilingual/Transformer/index.html`，图片在同目录 `img/`。
3. **检查**：

   ```bash
   python3 "$SKILL_DIR/scripts/check_bilingual.py" arxiv-bilingual/Transformer
   ```

   “漏翻”“缺图”必须是 0（不是 0 就重跑这篇）。“无汉字”几乎都是误报（整行只有公式、模型名或句号），扫一眼列出的几条即可。“跳不到”的链接通常是 arXiv 原网页本来就断的，告诉用户即可。
4. **打开**给用户看：macOS `open arxiv-bilingual/Transformer/index.html`，Linux `xdg-open …`，Windows `start …`。沙箱不让开浏览器时，把这条命令给用户自己运行。
5. **汇报**：句数、检查结果、文件位置。提醒用户译文只供自用。

## 批量做一个清单

把用户给的论文整理成一个 TSV 清单（放在用户的工作目录，不要放进本 skill 目录）：每行 `arXiv号<Tab>文件夹名[<Tab>备注]`，`#` 开头为注释。例如 `my-list.tsv`：

```text
# arXiv号	文件夹名	备注
1706.03762	Transformer	Attention Is All You Need
2010.11929	ViT	An Image is Worth 16x16 Words
```

```bash
python3 "$SKILL_DIR/scripts/batch.py" my-list.tsv --out arxiv-bilingual --jobs 2
```

已有 `index.html` 的会跳过（`--force` 重做）；两路并行；失败的最后自动重跑一次，再统一检查。20 篇约 1 小时。

## 改样式或预览，不重新翻译

样式和悬停预览脚本在 `bilingual_arxiv.py` 的 `CSS`、`SCRIPT` 两个常量里。改完之后：

```bash
python3 "$SKILL_DIR/scripts/bilingual_arxiv.py" --selftest
python3 "$SKILL_DIR/scripts/bilingual_arxiv.py" --restyle arxiv-bilingual/*/index.html
```

`--restyle` 只替换样式、预览脚本和标签页标题，几秒钟完成，可以重复运行。

## 输出物

每篇一个文件夹：`index.html` + `img/`，离线可读，不依赖外网。网页里有：

- 每句英文下面一行蓝色中文；章节标题下面附中文；附录照翻。
- 公式（MathML）、图片原样保留；表格内容和参考文献不翻译。
- 开头可折叠的目录，右下角固定“目录”按钮。
- 引用编号、Fig./Table/Eq./Sec. 都能点击跳转；鼠标停留时弹出小框预览（参考文献条目、整张图表、公式、该节开头、脚注、缩写全称）。
- 深色模式，手机宽度可读。
- 顺带修补 arXiv HTML 的两个常见缺陷：“Sec.” 后面缺编号（补节号或节标题）、缩写只显示键名（如 `slam` → `SLAM`）。

## 已知问题和处理

| 现象 | 原因 | 处理 |
|---|---|---|
| `SSLError` / 连接被断开 | 到 arxiv.org 的连接不稳定 | 脚本已重试 5 次；仍失败就重跑，已下载的图片会跳过 |
| “必应翻译连续失败” | 必应限流或接口变化 | 过几分钟重跑；并行别超过 2 路 |
| 报 404 或“没有可用的 HTML 正文” | 这篇没有 HTML 版 | 见“不适用”，改用 PDF 翻译工具 |
| 一句话在 “app.”“Sec.” 之类缩写处被断开 | 缩写表没收录 | 把缩写加进脚本里的 `ABBR`，跑 `--selftest` 后重新生成那一篇 |
| 表格挤在一起 | 原文表格带固定缩放 | 样式里已取消缩放；仍有问题就截图给维护者 |
| 脚本开头打印的句数比检查的多 | 开头的数包括章节标题 | 以检查脚本的句数为准 |
| uv 报 `Failed to initialize cache` | 沙箱里写不了 `~/.cache/uv` | 命令前加 `UV_CACHE_DIR="$TMPDIR/uv-cache"` |

## 版权

大多数 arXiv 论文的许可不允许公开传播译文。生成的网页只留在本机自用：不要提交到公开仓库，不要上传分享。输出目录如果在 git 仓库里，把它加进 `.gitignore`。

## 示例

- 用户：“帮我把 Attention Is All You Need 做成中英对照。” → 搜到 arXiv 1706.03762，告诉用户；运行 `bilingual_arxiv.py 1706.03762 Transformer`；检查；打开；汇报句数、“漏翻 0、缺图 0”和位置 `arxiv-bilingual/Transformer/index.html`。
- 用户：“把这个清单里的论文都翻了。” → 整理成 TSV，跑 `batch.py`，结束后贴出检查表。
- 用户：“鼠标放上去没有预览小框。” → 确认网页里有 `<script id="peek">`；没有就用 `--restyle` 更新。
