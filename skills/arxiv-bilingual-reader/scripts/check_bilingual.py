"""检查生成的中英对照网页。Check generated bilingual pages.

用法：python check_bilingual.py arxiv-bilingual/*/      （文件夹或 index.html 都行）

每篇一行：句数、漏翻（英文句后面没有中文）、无汉字的中文行、页内链接与跳不到的、目录条数、参考文献条数、图片与缺图。
“漏翻”或“缺图”不为 0、或缺 index.html 时退出码为 1。
“无汉字”大多是误报（只有公式、模型名或单独一个句号，必应原样保留），会列出前几条供人工看一眼。
“跳不到”的链接可能是 arXiv 原网页本来就断的，列出来供核对，不算失败。

Copyright (C) 2026 arxiv-bilingual-reader contributors. Licensed under AGPL-3.0-or-later.
"""
import re, sys
from pathlib import Path

from lxml import html as H

bad = 0
for arg in sys.argv[1:] or sys.exit(__doc__):
    d = Path(arg)
    f = d if d.suffix == ".html" else d / "index.html"
    if not f.exists():
        print(f"{d}\t缺 index.html")
        bad += 1
        continue
    r = H.parse(str(f)).getroot()
    ids = set(r.xpath("//@id"))
    ens = r.xpath('//span[@class="en"]')
    nxt = [e.getnext() for e in ens]
    missing = sum(x is None or x.get("class") != "zh" for x in nxt)
    no_han = [e.text_content().strip()[:50] for e, x in zip(ens, nxt) if x is not None and not re.search(r"[一-鿿]", x.text_content())]
    links = [a.get("href") for a in r.xpath("//a[@href]") if a.get("href").startswith("#")]
    dead = sorted({h for h in links if h[1:] not in ids})
    imgs = r.xpath("//img/@src")
    no_img = sum(not (f.parent / s).exists() for s in imgs)
    print(f"{f.parent.name}\t句 {len(ens)}\t漏翻 {missing}\t无汉字 {len(no_han)}\t链接 {len(links)}\t跳不到 {len(dead)}"
          f"\t目录 {len(r.xpath('//*[@id=\"toc\"]//li'))}\t文献 {len(r.xpath('//li[contains(@class,\"ltx_bibitem\")]'))}"
          f"\t图 {len(imgs)}\t缺图 {no_img}")
    if no_han:
        print("  无汉字（多为误报）:", no_han[:3])
    if dead:
        print("  跳不到:", dead[:5])
    bad += missing > 0 or no_img > 0
sys.exit(1 if bad else 0)
