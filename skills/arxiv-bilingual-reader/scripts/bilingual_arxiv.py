"""把 arXiv 论文的 HTML 版转成“每句英文下面跟一句中文”的对照网页（必应机器翻译，仅供个人学习）。
Turn an arXiv paper's HTML version into an offline page with each English sentence followed by its Chinese translation.

用法 / Usage:
  python bilingual_arxiv.py 1706.03762 [文件夹名] [--out 输出目录] [--limit N]
  python bilingual_arxiv.py --selftest
  python bilingual_arxiv.py --restyle 输出目录/*/index.html   # 只换样式和悬停预览脚本，不重新翻译

依赖 requests、lxml。公式（MathML）、引用、图保持原样；表格内容和参考文献不翻译。
默认输出到当前目录下的 arxiv-bilingual/<文件夹名>/index.html，文件夹名默认是 arXiv 号。
译文是受版权保护论文的衍生物，只留在本机自用：不要提交到公开仓库，也不要外传。

Copyright (C) 2026 arxiv-bilingual-reader contributors. Licensed under AGPL-3.0-or-later (see LICENSE).
The Bing class follows the BingTranslator of PDFMathTranslate-next (AGPL-3.0),
https://github.com/PDFMathTranslate-next/PDFMathTranslate-next
"""
import html, re, sys, time
from pathlib import Path

ABBR = {"e.g", "i.e", "al", "fig", "figs", "eq", "eqs", "sec", "secs", "tab", "tabs", "vs", "cf", "resp", "approx", "ref", "refs", "no", "app", "apps", "alg"}
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0 Safari/537.36"


def split_sentences(s):
    out, start = [], 0
    for m in re.finditer(r'[.!?]["\')\]]?\s+(?=[A-Z\[({"])', s):
        word = re.search(r"(\S+)$", s[start:m.start()])
        if word and word.group(1).lstrip("([").lower() in ABBR:
            continue
        out.append(s[start:m.end()].strip())
        start = m.end()
    tail = s[start:].strip()
    return out + [tail] if tail else out


def fill(text, holes, keep_notes):
    """把 {N} 占位符换回原始 HTML（公式、引用）；中文行里去掉脚注。"""
    parts = re.split(r"\{\s*(\d+)\s*\}", text)
    res = []
    for i, p in enumerate(parts):
        if i % 2 == 0:
            res.append(html.escape(p))
        elif int(p) < len(holes):
            kind, frag = holes[int(p)]
            if keep_notes:
                res.append(frag)
            elif kind != "note":  # 中文行：去掉脚注；公式等复制过来时去掉 id，免得和英文行重复
                res.append(re.sub(r'\sid="[^"]*"', "", frag))
    return "".join(res)


class Bing:
    """必应网页翻译（免费、无需 key、国内可用；非官方接口，可能限流或失效）。
    流程沿用 PDFMathTranslate-next 的 BingTranslator（AGPL-3.0）。"""

    def __init__(self):
        import requests
        self.ses = requests.Session()
        self.ses.headers["User-Agent"] = UA
        self.sid = None

    def _refresh(self):
        r = self.ses.get("https://www.bing.com/translator")
        r.raise_for_status()
        ig = re.findall(r'"ig":"(.*?)"', r.text)[0]
        iid = re.findall(r'data-iid="(.*?)"', r.text)[-1]
        key, token = re.findall(r'params_AbusePreventionHelper\s=\s\[(.*?),"(.*?)",', r.text)[0]
        self.sid = (r.url[:-10], ig, iid, key, token)

    def __call__(self, text):
        for attempt in range(5):
            try:
                if not self.sid:
                    self._refresh()
                url, ig, iid, key, token = self.sid
                r = self.ses.post(f"{url}ttranslatev3?IG={ig}&IID={iid}",
                                  data={"fromLang": "en", "to": "zh-Hans", "text": text, "token": token, "key": key})
                r.raise_for_status()
                return r.json()[0]["translations"][0]["text"]
            except Exception:
                self.sid = None
                time.sleep(2 * (attempt + 1))
        raise RuntimeError("必应翻译连续失败")

    def many(self, sents):
        """按 900 字一批、用换行拼接；行数对不上或出现空行（必应把几句并成了一句）就逐句重翻。"""
        out, batch = [], []
        for s in sents + [None]:
            if batch and (s is None or sum(len(b) + 1 for b in batch) + len(s) > 900):
                got = self("\n".join(batch)).split("\n")
                aligned = len(got) == len(batch) and all(g.strip() for g in got)
                out += got if aligned else [self(b) for b in batch]
                batch = []
            if s is not None:
                batch.append(s[:950])
        return out


def flatten(el, holes):
    """段落 → 带 {N} 占位符的纯文本；公式、引用、脚注、编号标签整体保留为占位符。"""
    from lxml import html as H
    buf = [el.text or ""]
    for ch in el:
        cls = ch.get("class") or ""
        internal_link = ch.tag == "a" and (ch.get("href") or "").startswith("#")  # Fig./Sec./Eq. 交叉引用，保留可点
        if ch.tag in ("math", "cite") or internal_link or "ltx_note " in cls + " " or "ltx_tag" in cls:
            holes.append(("note" if "ltx_note" in cls else ch.tag, H.tostring(ch, encoding="unicode", with_tail=False)))
            buf.append(f" {{{len(holes) - 1}}} ")
        else:
            buf.append(flatten(ch, holes))
        buf.append(ch.tail or "")
    return re.sub(r"\s+", " ", "".join(buf))


def parse_id(s):
    """接受 1706.03762、1706.03762v3 或 arXiv 的 abs/pdf/html 链接；用户写了版本号就保留。"""
    return re.sub(r"\.pdf$", "", re.sub(r"^.*arxiv\.org/(abs|pdf|html)/", "", s.strip().rstrip("/")))


def get_arxiv(path):
    """取 arxiv.org/html 下的网页或图片；连接偶尔会被中途断开，所以重试 5 次，每次多等一会儿。"""
    import requests
    for attempt in range(5):
        try:
            r = requests.get(f"https://arxiv.org/html/{path}", headers={"User-Agent": UA}, timeout=60)
            if r.status_code == 404:  # 不是网络问题，重试没用
                raise SystemExit(f"arXiv 上找不到 {path}（404）。检查 arXiv 号；较老的论文可能没有 HTML 版，见 SKILL.md“不适用”。")
            r.raise_for_status()
            return r.content
        except requests.RequestException:
            if attempt == 4:
                raise
            time.sleep(3 * (attempt + 1))


def main(arxiv_id, name, out_root, limit=None):
    from lxml import html as H
    doc = H.fromstring(get_arxiv(arxiv_id))
    if not doc.xpath("//article"):
        raise SystemExit(f"arXiv:{arxiv_id} 没有可用的 HTML 正文（作者源文件转换失败或太老）。改用 PDF 翻译工具，见 SKILL.md“不适用”。")
    art = doc.xpath("//article")[0]
    title = " ".join(art.xpath("string(.//h1)").split())  # 翻译前取，免得把中文标题也拼进来
    # 目录在 article 外面，单独带上；参考文献保留（不翻译），正文里的引用编号才点得到
    toc = "".join(H.tostring(t, encoding="unicode") for t in doc.xpath("//nav[contains(@class,'ltx_TOC')]"))
    out = Path(out_root).expanduser() / name
    (out / "img").mkdir(parents=True, exist_ok=True)
    for img in art.xpath(".//img"):
        src = img.get("src")
        local = "img/" + src.replace("/", "_")
        if not (out / local).exists():
            (out / local).write_bytes(get_arxiv(src))
        img.set("src", local)

    blocks = [e for e in art.xpath(".//p[contains(@class,'ltx_p')] | .//figcaption | .//*[contains(@class,'ltx_title')]")
              if not e.xpath("ancestor::table | ancestor::*[contains(@class,'ltx_bibliography')]")][:limit]
    jobs = []
    for el in blocks:
        holes = []
        sents = split_sentences(flatten(el, holes))
        if sents:
            jobs.append((el, holes, sents))
    flat = [s for _, _, sents in jobs for s in sents]
    print(f"{len(jobs)} 段，{len(flat)} 句，开始翻译……", flush=True)
    translated, k = Bing().many(flat), 0
    # 段落重写后，段内小片段（列表加粗项、子图编号）的锚点会丢；记下它们所在段落，链接改指段落
    lost = {}
    for el, _, _ in jobs:
        home = el.get("id") or next((a.get("id") for a in el.iterancestors() if a.get("id")), None)
        lost.update({d.get("id"): home for d in el.iterdescendants() if d.get("id") and home})
    for el, holes, sents in jobs:
        zh, k = translated[k:k + len(sents)], k + len(sents)
        if "ltx_title" in (el.get("class") or ""):
            el.append(H.fragment_fromstring(f'<span class="zh">{fill(" ".join(zh), holes, False)}</span>'))
        else:
            pairs = "".join(f'<span class="en">{fill(e, holes, True)}</span><span class="zh">{fill(z, holes, False)}</span>'
                            for e, z in zip(sents, zh))
            for ch in list(el):
                el.remove(ch)
            el.text = None
            for frag in H.fragments_fromstring(pairs):
                el.append(frag)

    alive = set(art.xpath(".//@id"))
    for a in art.xpath(".//a[starts-with(@href,'#')]"):
        target = a.get("href")[1:]
        if target not in alive and lost.get(target) in alive:
            a.set("href", "#" + lost[target])

    head = (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f"<title>{html.escape(title)}（中英逐句对照）</title><style>{CSS}</style></head><body>"
            f'<p class="note">来源：<a href="https://arxiv.org/abs/{arxiv_id}">arXiv:{arxiv_id}</a> 的 HTML 版，生成于 {time.strftime("%Y-%m-%d")}。'
            "中文为必应机器翻译，仅供个人学习，请勿外传；术语和数字以英文原文为准，引用页码以 PDF 为准。</p>"
            f'<details id="toc" open><summary>目录</summary>{toc}</details><a class="totop" href="#toc">目录</a>')
    (out / "index.html").write_text(head + H.tostring(art, encoding="unicode") + SCRIPT + "</body></html>", encoding="utf-8")
    print(f"\n已生成 {out / 'index.html'}")


def restyle(page):
    """只换已生成网页的样式和脚本，不重新翻译（改了 CSS / JS 之后用）。"""
    s = Path(page).read_text(encoding="utf-8")
    s = re.sub(r"<style>.*?</style>", lambda _: f"<style>{CSS}</style>", s, count=1, flags=re.S)
    h1 = re.search(r'<h1[^>]*>(.*?)<span class="zh">', s, re.S)  # 旧版标签页标题把中英文粘在一起，按英文标题重写
    if h1:
        title = html.escape(" ".join(html.unescape(re.sub(r"<[^>]+>", "", h1.group(1))).split()))
        s = re.sub(r"<title>.*?</title>", lambda _: f"<title>{title}（中英逐句对照）</title>", s, count=1, flags=re.S)
    s = re.sub(r'<script id="peek">.*?</script>', "", s, flags=re.S).replace("</body>", SCRIPT + "</body>")
    Path(page).write_text(s, encoding="utf-8")


CSS = """:root{--bg:#fdfcf9;--fg:#1d1d1f;--zh:#1c5d99;--line:#e6e2d8;--muted:#6b6b6b}
@media (prefers-color-scheme:dark){:root{--bg:#18191b;--fg:#e8e6e1;--zh:#8ab8e6;--line:#34363a;--muted:#9a9a9a}
img{background:#fff}}
body{background:var(--bg);color:var(--fg);max-width:46rem;margin:0 auto;padding:1.5rem 1rem 4rem;font:16px/1.65 -apple-system,"PingFang SC",sans-serif}
.note{font-size:.85rem;color:var(--muted);border:1px solid var(--line);padding:.6rem .8rem;border-radius:6px}
.en,.zh{display:block}.zh{color:var(--zh);margin:.1rem 0 .7rem;font-size:.95em}
.ltx_title .zh{font-size:.8em;margin:.2rem 0 0}figure{margin:1.5rem 0}img{max-width:100%;height:auto}
table{margin:.8rem auto;border-collapse:collapse;max-width:100%;display:block;overflow-x:auto}td,th{padding:.15rem .4rem}
.ltx_note_outer{display:none}a{color:inherit}.ltx_note_mark{cursor:help;color:var(--zh)}
/* 论文里被缩放过的表格带着固定宽高，换了字体就会溢出、和下方内容叠在一起；这里取消缩放，表格按原大小显示，过宽就横向滚动 */
.ltx_transformed_outer{width:auto!important;height:auto!important;vertical-align:baseline!important;display:block;overflow-x:auto}
.ltx_transformed_inner{transform:none!important;width:auto!important}.ltx_inline-block{height:auto!important}
#toc{border:1px solid var(--line);border-radius:6px;padding:.4rem .8rem;margin:1rem 0}#toc ol{list-style:none;padding-left:1rem;margin:.2rem 0}
a[href^="#"]{color:var(--zh)}.ltx_biblist{list-style:none;padding-left:0;font-size:.85em}
.totop{position:fixed;right:1rem;bottom:1rem;background:var(--bg);border:1px solid var(--line);border-radius:6px;padding:.3rem .7rem;text-decoration:none}
.peek{position:absolute;z-index:10;max-width:min(36rem,calc(100vw - 16px));max-height:50vh;overflow:auto;background:var(--bg);
border:1px solid var(--line);border-radius:8px;padding:.6rem .8rem;box-shadow:0 6px 24px rgba(0,0,0,.18);font-size:.9rem;line-height:1.55}
.peek figure,.peek table{margin:0}.peek .ltx_note_outer{display:inline}"""

# 鼠标停在引用编号、Fig./Table/Eq./Sec. 链接或脚注号上，弹出小框预览目标内容；点击照常跳转
SCRIPT = """<script id="peek">(() => {
  const tip = Object.assign(document.createElement("div"), {className: "peek", hidden: true});
  document.body.append(tip);
  let timer;
  const byHref = (a) => document.getElementById(decodeURIComponent(a.getAttribute("href").slice(1)));
  const pack = (...nodes) => {
    const d = document.createElement("div");
    d.append(...nodes.filter(Boolean).map((n) => n.cloneNode(true)));
    return d;
  };
  const target = (el) => {
    if (el.matches(".ltx_note_mark")) return el.closest(".ltx_note")?.querySelector(".ltx_note_content");
    const t = byHref(el);
    if (!t) return null;
    const box = t.closest(".ltx_bibitem, figure, .ltx_equation, .ltx_equationgroup");
    if (box) return box;
    if (t.matches("section")) return pack(t.querySelector(".ltx_title"), t.querySelector(".ltx_para"));
    if (t.matches("dt")) return pack(t, t.nextElementSibling);
    return t.closest(".ltx_para") || t;
  };
  // 中文行里复制的公式会带重复 id；arXiv 自己也有缺陷：有的“Sec.”后面没编号、有的缩写只显示键名（如 slam），从链接目标补上
  document.querySelectorAll(".zh [id]").forEach((n) => n.removeAttribute("id"));
  document.querySelectorAll('a[href^="#"]').forEach((a) => {
    const t = byHref(a), miss = a.querySelector(".ltx_missing");
    if (!t) return;
    if (miss && t.matches("dt")) miss.textContent = t.textContent.trim();
    else if (/^(Sec|Section|App|Appendix)\\.?$/.test(a.textContent.trim())) {
      const head = t.querySelector(":scope > .ltx_title")?.cloneNode(true);  // 只看这一节自己的标题，别抓到节里的表号
      if (!head) return;
      const tag = head.querySelector(":scope > .ltx_tag")?.textContent.trim().replace(/[.:]$/, "");
      head.querySelectorAll(".zh, .ltx_tag").forEach((n) => n.remove());
      a.append(" " + (tag || head.textContent.trim()));  // arXiv 有的附录节没编号，就用节标题
    }
  });
  const show = (el) => {
    const src = target(el);
    if (!src) return;
    clearTimeout(timer);
    tip.replaceChildren(src.cloneNode(true));
    tip.querySelectorAll("[id]").forEach((n) => n.removeAttribute("id"));
    tip.hidden = false;
    const r = el.getBoundingClientRect(), w = tip.offsetWidth, h = tip.offsetHeight;
    const x = Math.min(Math.max(8, r.left), innerWidth - w - 8);
    const y = r.bottom + h + 14 > innerHeight && r.top - h - 6 > 8 ? r.top - h - 6 : r.bottom + 6;
    tip.style.left = x + scrollX + "px";
    tip.style.top = y + scrollY + "px";
  };
  const trigger = (e) => e.target.closest('a[href^="#"]:not(#toc a):not(.totop), .ltx_note_mark');
  document.addEventListener("mouseover", (e) => {
    if (e.target.closest(".peek")) return clearTimeout(timer);
    const el = trigger(e);
    if (el) show(el);
  });
  document.addEventListener("mouseout", (e) => {
    if (trigger(e) || e.target.closest(".peek")) timer = setTimeout(() => (tip.hidden = true), 250);
  });
})();</script>"""


if __name__ == "__main__":
    if sys.argv[1:] == ["--selftest"]:
        assert split_sentences("Pavllo et al. {0} propose X. It works (see Fig. 3). Then {1} fails!") == \
            ["Pavllo et al. {0} propose X.", "It works (see Fig. 3).", "Then {1} fails!"]
        assert split_sentences("Details are in (app. {2} ). Next one.") == ["Details are in (app. {2} ).", "Next one."]
        assert fill("点图 { 0 } 很好 {1}", [("math", "<math/>"), ("note", "<n/>")], False) == "点图 <math/> 很好 "
        assert fill("{0}", [("math", '<math id="m1"/>')], False) == "<math/>"
        assert fill("{0}", [("math", '<math id="m1"/>')], True) == '<math id="m1"/>'
        assert [parse_id(x) for x in ("1706.03762", "https://arxiv.org/abs/1706.03762v3", "arxiv.org/pdf/1706.03762v2.pdf",
                                      "https://arxiv.org/html/1706.03762/")] == ["1706.03762", "1706.03762v3", "1706.03762v2", "1706.03762"]
        try:
            from lxml import html as H
            holes = []
            assert flatten(H.fromstring('<p>See <a href="#S1">Sec. 1</a> and <a href="http://x">site</a>.</p>'), holes) == "See {0} and site."
            assert holes == [("a", '<a href="#S1">Sec. 1</a>')]
        except ImportError:
            print("（没装 lxml，跳过链接检查；装上 lxml 再跑能测全）")
        print("selftest ok")
    elif sys.argv[1:2] == ["--restyle"]:
        for p in sys.argv[2:]:
            restyle(p)
            print("已更新样式", p)
    else:
        args = sys.argv[1:]
        opt = lambda k, d=None: args[args.index(k) + 1] if k in args else d
        pos = [a for i, a in enumerate(args) if not a.startswith("--") and (i == 0 or args[i - 1] not in ("--out", "--limit"))]
        if not pos:
            sys.exit(__doc__)
        arxiv_id = parse_id(pos[0])
        main(arxiv_id, pos[1] if len(pos) > 1 else arxiv_id, opt("--out", "arxiv-bilingual"),
             int(opt("--limit")) if opt("--limit") else None)
