import json
import csv
import time
import urllib.parse
import urllib.request
from pathlib import Path

OUT = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas")
BASE = "https://do-api-web-search.doe.sp.gov.br/"
JOURNAL = "8e1f4298-811b-4e36-0df1-08db6b8c9f7b"  # Empresarial
SECTION = "5d8e372f-a265-4a0f-fe4e-08db6b969ba3"  # Atos Empresariais

HEADERS = {
    "accept": "application/json, text/plain, */*",
    "origin": "https://doe.sp.gov.br",
    "referer": "https://doe.sp.gov.br/",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

TERMS = [
    "balanço",
    "balanços",
    "balanço patrimonial",
    "balanços patrimoniais",
    "demonstrações financeiras",
    "demonstrações contábeis",
    "demonstracao financeira",
    "demonstrações financeiras",
]


def api_get(path, params):
    # axios qs serialize - arrays as repeated keys
    q = []
    for k, v in params.items():
        if v is None:
            continue
        if isinstance(v, list):
            for item in v:
                q.append((k, item))
        else:
            q.append((k, v))
    url = BASE + path + "?" + urllib.parse.urlencode(q, safe="")
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode("utf-8"))


def probe():
    print("=== probe advanced-search ===")
    for terms in (["balanço"], ["Balanço Patrimonial"], ["Demonstrações Financeiras"]):
        params = {
            "Terms": terms,
            "FromDate": "2020-01-01",
            "ToDate": "2020-12-31",
            "JournalId": JOURNAL,
            "SectionId": SECTION,
            "PageNumber": 1,
            "PageSize": 5,
            "SortField": 1,
        }
        try:
            data = api_get("v2/advanced-search/publications", params)
            print(terms, "keys", list(data.keys()) if isinstance(data, dict) else type(data))
            print(json.dumps(data, ensure_ascii=False)[:800])
        except Exception as e:
            print("FAIL", terms, e)

    print("\n=== probe without section ===")
    try:
        data = api_get(
            "v2/advanced-search/publications",
            {
                "Terms": ["balanço"],
                "FromDate": "2020-04-01",
                "ToDate": "2020-04-30",
                "JournalId": JOURNAL,
                "PageNumber": 1,
                "PageSize": 5,
                "SortField": 1,
            },
        )
        print(json.dumps(data, ensure_ascii=False)[:1200])
    except Exception as e:
        print("FAIL", e)

    print("\n=== filters ===")
    try:
        data = api_get(
            "v2/advanced-search/filters",
            {
                "Terms": ["balanço"],
                "FromDate": "2020-01-01",
                "ToDate": "2020-12-31",
                "JournalId": JOURNAL,
                "PageNumber": 1,
                "PageSize": 20,
                "SortField": 1,
            },
        )
        print(json.dumps(data, ensure_ascii=False)[:1200])
    except Exception as e:
        print("FAIL filters", e)


if __name__ == "__main__":
    probe()
