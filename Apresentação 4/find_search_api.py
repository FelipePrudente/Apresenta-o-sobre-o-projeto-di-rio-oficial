import re
import json
import urllib.request
import urllib.parse
from pathlib import Path

OUT = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas")
TMP = OUT / "_tmp_doe_js"
TMP.mkdir(exist_ok=True)

# Download webpack.js which maps module IDs to chunks
manifest_urls = [
    "https://doe.sp.gov.br/_next/static/chunks/webpack-87c32b022a98e942.js",
    "https://doe.sp.gov.br/_next/static/chunks/main-f8b777cc49ae9b3d.js",
    "https://doe.sp.gov.br/_next/static/chunks/pages/_app-86e036c2caf07b70.js",
]
for u in manifest_urls:
    name = u.rsplit("/", 1)[-1]
    dest = TMP / name
    if not dest.exists():
        print("dl", name)
        urllib.request.urlretrieve(u, dest)

# Find chunk containing 78640
text = (TMP / "webpack-87c32b022a98e942.js").read_text(encoding="utf-8", errors="ignore")
# Next.js webpack maps like {78640:"xxxx"} or similar
for m in re.finditer(r"78640[^,]{0,40}", text):
    print("map", m.group(0))

# Broader: find any file with Is:function and FromDate together by probing common chunk names from busca imports
# From busca: C=c(78640) D=c(54564) E=c(95978) ...
needed = [78640, 54564, 95978, 81904, 97606, 70016, 70280, 11163]
for n in needed:
    ms = list(re.finditer(rf"{n}:\"([^\"]+)\"|{n}:'([^']+)'|{n}:([a-zA-Z0-9]+)", text))
    print(n, [x.group(0) for x in ms[:5]])

# Also try API discovery by calling likely endpoints with sample payload
journal = "8e1f4298-811b-4e36-0df1-08db6b8c9f7b"
section = "5d8e372f-a265-4a0f-fe4e-08db6b969ba3"
params_list = [
    {"Terms": ["balanço"], "FromDate": "2020-01-01", "ToDate": "2020-12-31", "JournalId": journal, "PageNumber": 1, "PageSize": 20, "SortField": 1},
    {"Terms": ["balanço"], "FromDate": "2020-01-01", "ToDate": "2020-12-31", "PageNumber": 1, "PageSize": 20},
]
endpoints = [
    "https://do-api-web-search.doe.sp.gov.br/v2/search",
    "https://do-api-web-search.doe.sp.gov.br/v2/search/publications",
    "https://do-api-web-search.doe.sp.gov.br/v2/publications/search",
    "https://do-api-web-search.doe.sp.gov.br/v2/search/advanced",
    "https://do-api-web-search.doe.sp.gov.br/v2/advancedsearch",
    "https://do-api-web-search.doe.sp.gov.br/v2/Search",
    "https://do-api-web-search.doe.sp.gov.br/v1/search",
    "https://do-api-web-search.doe.sp.gov.br/v2/legacy/search",
    "https://do-api-web-search.doe.sp.gov.br/v2/publication/filter",
]

def try_req(method, url, params=None):
    try:
        if method == "GET":
            q = urllib.parse.urlencode(params, doseq=True) if params else ""
            full = url + ("?" + q if q else "")
            req = urllib.request.Request(full, headers={
                "accept": "application/json",
                "origin": "https://doe.sp.gov.br",
                "referer": "https://doe.sp.gov.br/",
                "user-agent": "Mozilla/5.0",
            })
        else:
            data = json.dumps(params).encode()
            req = urllib.request.Request(url, data=data, method="POST", headers={
                "accept": "application/json",
                "content-type": "application/json",
                "origin": "https://doe.sp.gov.br",
                "referer": "https://doe.sp.gov.br/",
                "user-agent": "Mozilla/5.0",
            })
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()[:400]
            print("OK", method, resp.status, url, body[:200])
            return True
    except Exception as e:
        code = getattr(getattr(e, "code", None), "real", None) or getattr(e, "code", None)
        print("FAIL", method, code, url)
        return False

print("\n=== probing endpoints ===")
for ep in endpoints:
    # flatten Terms for GET
    p = dict(params_list[0])
    p["Terms"] = "balanço"
    try_req("GET", ep, p)
    try_req("POST", ep, params_list[0])
