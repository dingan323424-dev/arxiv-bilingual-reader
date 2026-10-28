"""按清单批量生成中英对照网页。Batch-generate bilingual pages from a reading list.

用法：python batch.py 清单.tsv [--out arxiv-bilingual] [--jobs 2] [--force]

清单每行：arXiv号<Tab>文件夹名[<Tab>备注]；空行和 # 开头的行跳过。
- 已有 index.html 的跳过（加 --force 重新生成）。
- 同时跑 --jobs 篇（默认 2；两路并行时必应没有限流，再多没试过）。
- 失败的在最后再重跑一次（已下载的图片会复用），然后对全部篇目跑 check_bilingual.py。

Copyright (C) 2026 arxiv-bilingual-reader contributors. Licensed under AGPL-3.0-or-later.
"""
import subprocess, sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
args = sys.argv[1:]
opt = lambda k, d: args[args.index(k) + 1] if k in args else d
if not args or args[0].startswith("--"):
    sys.exit(__doc__)
out, jobs, force = Path(opt("--out", "arxiv-bilingual")), int(opt("--jobs", "2")), "--force" in args

papers = []
for line in Path(args[0]).read_text(encoding="utf-8").splitlines():
    cols = line.split("\t")
    if line.strip() and not line.startswith("#"):
        papers.append((cols[0].strip(), cols[1].strip() if len(cols) > 1 and cols[1].strip() else cols[0].strip()))
todo = [p for p in papers if force or not (out / p[1] / "index.html").exists()]
print(f"清单 {len(papers)} 篇，要生成 {len(todo)} 篇，{jobs} 路并行", flush=True)


def run(paper):
    arxiv_id, name = paper
    r = subprocess.run([sys.executable, str(HERE / "bilingual_arxiv.py"), arxiv_id, name, "--out", str(out)],
                       capture_output=True, text=True)
    tail = (r.stdout + r.stderr).strip().splitlines()[-1:] or [""]
    print(f"{'完成' if r.returncode == 0 else '失败'}  {name} ({arxiv_id})  {tail[0][:160]}", flush=True)
    return r.returncode == 0


with ThreadPoolExecutor(jobs) as pool:
    failed = [p for p, ok in zip(todo, pool.map(run, todo)) if not ok]
if failed:
    print(f"\n重跑失败的 {len(failed)} 篇……", flush=True)
    failed = [p for p in failed if not run(p)]

print("\n检查：", flush=True)
check = subprocess.run([sys.executable, str(HERE / "check_bilingual.py"), *[str(out / name) for _, name in papers]])
if failed:
    print("\n仍失败：", ", ".join(f"{n} ({i})" for i, n in failed))
sys.exit(1 if failed or check.returncode else 0)
