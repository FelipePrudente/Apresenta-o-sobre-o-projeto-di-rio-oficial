import re
import pathlib
import urllib.request

dir_path = pathlib.Path(__file__).resolve().parent / "_tmp_doe_js"
dir_path.mkdir(exist_ok=True)

urls = [
    "https://doe.sp.gov.br/_next/static/chunks/274-c44ad3519a441e9b.js",
    "https://doe.sp.gov.br/_next/static/chunks/pages/balanco-ae064188a870d0c2.js",
    "https://doe.sp.gov.br/_next/static/chunks/242-47e48aaadadeb702.js",
    "https://doe.sp.gov.br/_next/static/chunks/pages/busca-avancada-05c5860c27a2cb49.js",
]

for u in urls:
    name = u.rsplit("/", 1)[-1]
    dest = dir_path / name
    if not dest.exists() or dest.stat().st_size < 1000:
        print("downloading", name)
        urllib.request.urlretrieve(u, dest)

for f in sorted(dir_path.glob("*.js")):
    t = f.read_text(encoding="utf-8", errors="ignore")
    print("\n====", f.name, "size", len(t))
    hits = set(re.findall(r'["\'](/?v\d+/[a-zA-Z0-9_\-./{}?=&]+)["\']', t))
    hits |= set(re.findall(r'https://do-api[^"\']+', t))
    hits |= set(re.findall(r'do-api-web-search[^"\']{0,100}', t))
    for h in sorted(hits):
        print(" HIT", h)
    # function names near search
    for pat in [
        r".{0,60}FromDate.{0,80}",
        r".{0,60}isLegacy.{0,80}",
        r".{0,80}/search.{0,80}",
        r".{0,60}publicationTypes.{0,80}",
        r".{0,60}NEXT_PUBLIC.{0,80}",
    ]:
        for m in re.finditer(pat, t):
            s = m.group(0).replace("\n", " ")
            if any(x in s for x in ("http", "v2", "fetch", "get(", "axios", "api", "Legacy", "search")):
                print(" CTX", s[:200])
