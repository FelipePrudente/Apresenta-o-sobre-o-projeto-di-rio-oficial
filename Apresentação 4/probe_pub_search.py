import re
import json
import urllib.request
import urllib.parse
from pathlib import Path

TMP = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas\_tmp_doe_js")

# Scan all downloaded JS for API host / path fragments
for f in TMP.glob("*.js"):
    t = f.read_text(encoding="utf-8", errors="ignore")
    if "do-api" in t or "web-search" in t or "NEXT_PUBLIC" in t:
        print("FILE", f.name)
        for m in re.finditer(r".{0,40}(do-api|web-search|NEXT_PUBLIC|publications/search|/v2/).{0,80}", t):
            print(" ", m.group(0)[:160])

# GET publications/search with various query shapes
base = "https://do-api-web-search.doe.sp.gov.br/v2/publications/search"
variants = [
    {"Terms": "balanço", "FromDate": "2020-01-01", "ToDate": "2020-12-31", "PageNumber": 1, "PageSize": 20},
    {"terms": "balanço", "fromDate": "2020-01-01", "toDate": "2020-12-31", "pageNumber": 1, "pageSize": 20},
    {"Text": "balanço", "StartDate": "2020-01-01", "EndDate": "2020-12-31"},
    {"query": "balanço", "from": "2020-01-01", "to": "2020-12-31"},
    {"Terms": ["balanço"], "FromDate": "20200401", "ToDate": "20200430", "JournalId": "8e1f4298-811b-4e36-0df1-08db6b8c9f7b", "PageNumber": 1, "PageSize": 10, "SortField": 1},
]

# Also try swagger/openapi
for path in ["/swagger", "/swagger/index.html", "/openapi", "/v2/swagger.json", "/swagger/v1/swagger.json", "/"]:
    url = "https://do-api-web-search.doe.sp.gov.br" + path
    try:
        req = urllib.request.Request(url, headers={"user-agent": "Mozilla/5.0", "accept": "*/*"})
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = resp.read()[:300]
            print("SWAGGER OK", resp.status, path, body[:120])
    except Exception as e:
        print("SWAGGER FAIL", getattr(e, "code", None), path)

print("\n=== GET publications/search variants ===")
for p in variants:
    # handle list
    q = []
    for k, v in p.items():
        if isinstance(v, list):
            for item in v:
                q.append((k, item))
        else:
            q.append((k, v))
    url = base + "?" + urllib.parse.urlencode(q)
    try:
        req = urllib.request.Request(url, headers={
            "accept": "application/json",
            "origin": "https://doe.sp.gov.br",
            "referer": "https://doe.sp.gov.br/",
            "user-agent": "Mozilla/5.0",
        })
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read()
            print("OK", resp.status, len(body), p)
            print(body[:400])
    except Exception as e:
        print("FAIL", getattr(e, "code", None), p, getattr(e, "reason", e))

# Try OPTIONS to see Allow header
print("\n=== OPTIONS ===")
for ep in [
    "https://do-api-web-search.doe.sp.gov.br/v2/publications/search",
    "https://do-api-web-search.doe.sp.gov.br/v2/search",
]:
    try:
        req = urllib.request.Request(ep, method="OPTIONS", headers={
            "origin": "https://doe.sp.gov.br",
            "access-control-request-method": "GET",
            "user-agent": "Mozilla/5.0",
        })
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(ep, resp.status, dict(resp.headers))
    except Exception as e:
        hdrs = {}
        if hasattr(e, "headers") and e.headers:
            hdrs = dict(e.headers)
        print("OPT FAIL", ep, getattr(e, "code", None), hdrs)
