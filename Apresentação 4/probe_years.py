import json
import urllib.parse
import urllib.request

BASE = "https://do-api-web-search.doe.sp.gov.br/"
HEADERS = {
    "accept": "application/json",
    "origin": "https://doe.sp.gov.br",
    "referer": "https://doe.sp.gov.br/",
    "user-agent": "Mozilla/5.0",
}
JOURNAL = "8e1f4298-811b-4e36-0df1-08db6b8c9f7b"


def api_get(path, params):
    q = []
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, list):
            for item in v:
                q.append((k, item))
        else:
            q.append((k, v))
    url = BASE + path + "?" + urllib.parse.urlencode(q)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


tests = [
    {"label": "2025 balanço", "params": {"Terms": ["balanço"], "FromDate": "2025-04-01", "ToDate": "2025-04-30", "JournalId": JOURNAL, "PageNumber": 1, "PageSize": 3, "SortField": 1}},
    {"label": "2024 balanço", "params": {"Terms": ["balanço"], "FromDate": "2024-04-01", "ToDate": "2024-04-30", "JournalId": JOURNAL, "PageNumber": 1, "PageSize": 3, "SortField": 1}},
    {"label": "2023 balanço", "params": {"Terms": ["balanço"], "FromDate": "2023-04-01", "ToDate": "2023-04-30", "JournalId": JOURNAL, "PageNumber": 1, "PageSize": 3, "SortField": 1}},
    {"label": "2021 balanço", "params": {"Terms": ["balanço"], "FromDate": "2021-04-01", "ToDate": "2021-04-30", "JournalId": JOURNAL, "PageNumber": 1, "PageSize": 3, "SortField": 1}},
    {"label": "2020 no journal", "params": {"Terms": ["balanço"], "FromDate": "2020-04-01", "ToDate": "2020-04-30", "PageNumber": 1, "PageSize": 3, "SortField": 1}},
    {"label": "2020 Demonstrações", "params": {"Terms": ["Demonstrações Financeiras"], "FromDate": "2020-01-01", "ToDate": "2020-12-31", "PageNumber": 1, "PageSize": 3, "SortField": 1}},
    {"label": "2025 title exact sample", "params": {"Terms": ["BALANÇO"], "FromDate": "2025-04-25", "ToDate": "2025-04-25", "JournalId": JOURNAL, "PageNumber": 1, "PageSize": 5, "SortField": 1}},
]

for t in tests:
    try:
        data = api_get("v2/advanced-search/publications", t["params"])
        items = data.get("items") or []
        print(f"\n{t['label']}: totalItems={data.get('totalItems')} n={len(items)}")
        for it in items[:2]:
            print(" ", {k: it.get(k) for k in ("title", "name", "date", "publicationDate", "slug", "isLegacy", "id", "path") if k in it or True})
            print("  keys", list(it.keys()))
            print("  raw", json.dumps(it, ensure_ascii=False)[:350])
    except Exception as e:
        print(t["label"], "FAIL", e)
