"""
Levanta publicações de balanço no DOE/Imprensa Oficial (legado) 2020-2021.
Fonte: busca do caderno Empresarial em imprensaoficial.com.br
Extrai name/title a partir de snippets de sumário e cabeçalhos.
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path

OUT = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# Termos alinhados ao levantamento 2025/2026
SEARCHES = [
    ("PHRASE", "Balanço Patrimonial"),
    ("PHRASE", "Demonstrações Financeiras"),
    ("PHRASE", "Demonstrações Contábeis"),
    ("PHRASE", "Balanços Patrimoniais"),
    ("PHRASE", "Demonstrações Financeiras"),
    ("TUDO", "Sumário Caderno Empresarial BALANÇO"),
]

TITLE_PAT = re.compile(
    r"(?i)\b("
    r"BALAN[CÇ]OS?\s+PATRIMONIA(?:L|IS)"
    r"|BALAN[CÇ]O\s+PATRIMONIAL(?:\s+CONSOLIDADO)?"
    r"|BALAN[CÇ]O(?:S)?"
    r"|DEMONSTRA[CÇ][AÃ]O(?:ES)?\s+(?:FINANCEIRAS|CONT[AÁ]BEIS)"
    r"|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS)"
    r"|RESUMO\s+GERAL\s+DO\s+BALAN[CÇ]O"
    r")\b"
)

SECTION_STOP = re.compile(
    r"(?i)\b("
    r"AVISO|EDITAL|EXTRATO|ATA\b|CONVOCA|LICITA|CONTRATO|COMUNICADO|"
    r"DEMONSTRA|BALAN[CÇ]O|ASSEMBLEIA|PUBLICIDADE|SUM[AÁ]RIO|"
    r"EMPRESARIAL|DI[AÁ]RIO\s+OFICIAL|P[AÁ]GINA|PAG\."
    r")\b"
)


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=90) as resp:
        raw = resp.read()
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def build_search_url(year: int, term: str, tip: str, page: str) -> str:
    term_enc = urllib.parse.quote(term, safe="")
    # phrase in query needs + for spaces inside quotes sometimes; use quote
    if tip == "PHRASE":
        q_term = urllib.parse.quote(f'"{term}"', safe="")
        # IO historically used + inside quotes for spaces
        q_term = q_term.replace("%20", "%2B")
        filtro = urllib.parse.quote(f'"{term}"', safe="").replace("%20", "+")
    else:
        q_term = urllib.parse.quote(term, safe="").replace("%20", "+")
        filtro = q_term

    return (
        "https://www.imprensaoficial.com.br/DO/BuscaDO2001Resultado_11_3.aspx"
        f"?f=xhitlist"
        f"&filtrodatafimsalvar={year}1231"
        f"&filtrodatainiciosalvar={year}0101"
        f"&filtrogrupos=Empresarial+"
        f"&filtrogrupossalvar=Empresarial+"
        f"&filtropalavraschave={filtro}"
        f"&filtroperiodo=01%2F01%2F{year}+a+31%2F12%2F{year}"
        f"&filtrotipopalavraschavesalvar={tip}"
        f"&filtrotodosgrupos=False"
        f"&xhitlist_d=Empresarial+"
        f"&xhitlist_hc=%5BXML%5D%5BKwic%2C3%5D"
        f"&xhitlist_mh=50"
        f"&xhitlist_q=%5Bfield+%27dc%3Adatapubl%27%3A%3E%3D01.01.{year}%3C%3D31.12.{year}%5D%28{q_term}%29"
        f"&xhitlist_s="
        f"&xhitlist_sel=title%3BField%3Adc%3Atamanho%3BField%3Adc%3Adatapubl%3BField%3Adc%3Acaderno%3Bitem-bookmark%3Bhit-context"
        f"&xhitlist_vpc={page}"
        f"&xhitlist_xsl=xhitlist.xsl"
    )


def parse_total(html: str) -> int:
    m = re.search(r'id="content_lblDocumentosEncontrados"[^>]*>([^<]+)<', html)
    if not m:
        return 0
    digits = re.sub(r"[^\d]", "", m.group(1))
    return int(digits) if digits else 0


def clean_text(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    s = re.sub(r"\s+", " ", s).strip()
    return s


def parse_cards(html: str) -> list[dict]:
    cards = []
    for m in re.finditer(
        r'(?s)class="card shadow-sm resultadoBuscaItem">(.*?)</div>\s*</div>\s*(?:<br|\s*<div class="card)',
        html,
    ):
        block = m.group(1)
        data_lbl = ""
        dm = re.search(r'lblData_\d+"[^>]*>([^<]+)<', block)
        if dm:
            data_lbl = dm.group(1).strip()
        snip = ""
        sm = re.search(r'(?s)class="bg-light text-dark"[^>]*>(.*?)</a>', block)
        if sm:
            snip = clean_text(sm.group(1))
        link = ""
        lm = re.search(r'link=([^&"\']+)', block)
        if lm:
            link = urllib.parse.unquote(lm.group(1))
        page = None
        pm = re.search(r'[?&]pagina=(\d+)', block)
        if pm:
            page = int(pm.group(1))
        date = None
        caderno = None
        if data_lbl:
            parts = [p.strip() for p in data_lbl.split(" - ")]
            if parts:
                # dd/mm/yyyy
                dm2 = re.match(r"(\d{2})/(\d{2})/(\d{4})", parts[0])
                if dm2:
                    date = f"{dm2.group(3)}-{dm2.group(2)}-{dm2.group(1)}"
            if len(parts) > 1:
                caderno = parts[1]
        cards.append(
            {
                "date": date,
                "data_lbl": data_lbl,
                "caderno": caderno,
                "page": page,
                "snippet": snip,
                "link": link,
            }
        )
    return cards


def extract_from_sumario(snippet: str, date: str, source: str) -> list[dict]:
    """Parse company names listed under BALANÇO in sumário-like text."""
    rows = []
    if not re.search(r"(?i)sum[aá]rio|balan[cç]o", snippet):
        return rows

    # Pattern: BALANÇO COMPANY ..... page OR BALANÇO COMPANY... next company
    # Split by long dotted leaders
    text = snippet
    # Focus after first BALANÇO header in sumário
    m = re.search(r"(?i)(?:sum[aá]rio[^\.]{0,80})?(BALAN[CÇ]O\b.*)$", text)
    if not m:
        return rows
    chunk = m.group(1)

    # Split entries separated by dotted leaders + page numbers
    parts = re.split(r"\.{3,}\s*\d+\s*", chunk)
    for part in parts:
        part = part.strip(" .-\t")
        if not part:
            continue
        # Remove leading section word BALANÇO once
        part2 = re.sub(r"(?i)^BALAN[CÇ]O\s+", "", part).strip()
        if not part2 or len(part2) < 4:
            continue
        # Stop at next obvious section word mid-string
        # Keep first company-like token sequence
        # If still has multiple companies jammed, split on 2+ spaces before ALLCAPS company
        candidates = re.split(r"\s{2,}(?=[A-ZÁÉÍÓÚÃÕÂÊÔÇ0-9])", part2)
        for cand in candidates:
            name = cand.strip(" .")
            name = re.sub(r"\s+\d+$", "", name).strip()
            if len(name) < 5 or len(name) > 180:
                continue
            if re.fullmatch(r"(?i)BALAN[CÇ]O|DEMONSTRA.*|SUM[AÁ]RIO|EMPRESARIAL.*", name):
                continue
            # discard if looks like body text (lowercase heavy / too many words)
            letters = re.findall(r"[A-Za-zÀ-ÿ]", name)
            if not letters:
                continue
            upper_ratio = sum(1 for ch in letters if ch.isupper()) / max(len(letters), 1)
            if upper_ratio < 0.35 and " S.A" not in name.upper() and " LTDA" not in name.upper():
                # likely prose
                if len(name.split()) > 12:
                    continue
            rows.append(
                {
                    "date": date,
                    "name": name,
                    "title": "BALANÇO",
                    "source": source,
                    "evidence": snippet[:240],
                }
            )
    return rows


def extract_title_header(snippet: str, date: str, source: str) -> list[dict]:
    """When snippet starts with a publication title like BALANÇO / DEMONSTRAÇÕES..."""
    rows = []
    s = snippet.strip()
    # strip leading ellipsis
    s = re.sub(r"^\.+", "", s).strip()
    m = TITLE_PAT.match(s)
    if not m:
        # also allow NAME - BALANÇO
        m2 = re.match(r"(?i)^(.{5,120}?)\s*[-–—]\s*(BALAN[CÇ]O|DEMONSTRA[CÇ].*)$", s)
        if m2:
            rows.append(
                {
                    "date": date,
                    "name": m2.group(1).strip(),
                    "title": m2.group(2).strip()[:180],
                    "source": source,
                    "evidence": snippet[:240],
                }
            )
        return rows

    title = m.group(1)
    # extend title with common suffixes on same line
    rest = s[m.end() :].strip()
    title_ext = title
    extra = re.match(
        r"(?i)^(\s*(?:PATRIMONIAL|CONSOLIDADO|GERAL|FINANCEIRO|ENCERRADO.*?\d{4}|EM 31.*?\d{4}|DOS EXERC.*?\d{4}|REFERENTES.*?\d{4}|/\d{4}|\d{4}){0,6})",
        " " + rest,
    )
    if extra:
        title_ext = (title + extra.group(1)).strip()
        title_ext = re.sub(r"\s+", " ", title_ext)[:200]

    # Try to get company from "BALANÇO COMPANY" form at start of sumário
    after = rest
    company = None
    cm = re.match(r"^([A-ZÁÉÍÓÚÃÕÂÊÔÇ0-9][A-ZÁÉÍÓÚÃÕÂÊÔÇ0-9a-zà-ú &\.\-/']{3,100}?)(?:\.{2,}|\s{2,}|\.\.\.|$)", after)
    if cm and not SECTION_STOP.match(cm.group(1)):
        company = cm.group(1).strip(" .")
        if len(company.split()) > 16:
            company = None

    rows.append(
        {
            "date": date,
            "name": company or "(não identificado no snippet)",
            "title": title_ext.upper() if title_ext.isascii() or True else title_ext,
            "source": source,
            "evidence": snippet[:240],
        }
    )
    return rows


def normalize_key(row: dict) -> tuple:
    name = re.sub(r"\s+", " ", (row.get("name") or "").strip().upper())
    title = re.sub(r"\s+", " ", (row.get("title") or "").strip().upper())
    return (row.get("date"), name, title)


def harvest_year(year: int) -> list[dict]:
    all_rows: list[dict] = []
    seen_pages = set()  # (date, page, link)

    # Prefer searches likely to hit headers/sumários with less noise
    queries = [
        ("PHRASE", "Balanço Patrimonial"),
        ("PHRASE", "Demonstrações Financeiras"),
        ("PHRASE", "Demonstrações Contábeis"),
        ("PHRASE", "Balanços Patrimoniais"),
        ("TUDO", "Balanço"),
    ]

    for tip, term in queries:
        page = "first"
        page_num = 1
        total = None
        max_pages = 40 if term == "Balanço" else 80  # Balanço is huge; sample early pages + rely on other terms
        if term == "Balanço":
            max_pages = 30  # 50*30=1500 pages sample focused on ranking relevance

        print(f"\n=== {year} | {tip} | {term} ===")
        while page_num <= max_pages:
            url = build_search_url(year, term, tip, page)
            try:
                html = fetch(url)
            except Exception as e:
                print(" fetch fail", page, e)
                break
            if total is None:
                total = parse_total(html)
                print(" total docs:", total)
                if total == 0:
                    break
                # compute pages available
                avail = max(1, (total + 49) // 50)
                max_pages = min(max_pages, avail)

            cards = parse_cards(html)
            if not cards:
                print(" no cards at", page)
                break

            kept = 0
            for c in cards:
                key = (c["date"], c["page"], c["link"])
                if key in seen_pages:
                    continue
                seen_pages.add(key)
                snip = c["snippet"] or ""
                # Prefer sumário / early pages / title-like starts
                is_sumario = bool(re.search(r"(?i)sum[aá]rio\s+caderno", snip))
                is_titleish = bool(TITLE_PAT.match(re.sub(r"^\.+", "", snip).strip()))
                is_early = c["page"] is not None and c["page"] <= 8
                if term == "Balanço" and not (is_sumario or is_titleish or is_early):
                    continue

                source = f"{tip}:{term}"
                if is_sumario:
                    rows = extract_from_sumario(snip, c["date"], source)
                    if not rows:
                        rows = extract_title_header(snip, c["date"], source)
                else:
                    rows = extract_title_header(snip, c["date"], source)
                    if not rows and is_sumario:
                        rows = extract_from_sumario(snip, c["date"], source)

                for r in rows:
                    r["caderno"] = c.get("caderno")
                    r["page"] = c.get("page")
                    r["link"] = c.get("link")
                    r["year"] = year
                    all_rows.append(r)
                    kept += 1

            print(f" page {page_num}/{max_pages}: cards={len(cards)} extracted+={kept} acum={len(all_rows)}")

            page_num += 1
            page = str(page_num)
            time.sleep(0.25)

    # Deduplicate
    uniq = {}
    for r in all_rows:
        k = normalize_key(r)
        if k[1] == "(NÃO IDENTIFICADO NO SNIPPET)" or k[1] == "":
            # keep but weaker
            k = (k[0], k[1], k[2], r.get("link"))
        if k not in uniq:
            uniq[k] = r
    return list(uniq.values())


def main():
    rows = []
    for year in (2020, 2021):
        rows.extend(harvest_year(year))

    # Filter out obvious junk names
    cleaned = []
    junk = re.compile(
        r"(?i)^(ATIVO|PASSIVO|CIRCULANTE|NOTAS?|VALORES|EXPRESSOS|CONTROLADORA|CONSOLIDADO|"
        r"DEMONSTRA|CRC\b|P[AÁ]GINA|EMPRESARIAL|DI[AÁ]RIO|SUM[AÁ]RIO|E O VALOR|UM ATIVO)\b"
    )
    for r in rows:
        name = (r.get("name") or "").strip()
        if junk.search(name):
            continue
        if name.startswith("...") or " reconhecido" in name.lower():
            continue
        cleaned.append(r)

    cleaned.sort(key=lambda x: (x.get("date") or "", x.get("name") or "", x.get("title") or ""))

    csv_path = OUT / "balancos_doe_empresarial_2020-2021.csv"
    json_path = OUT / "balancos_doe_empresarial_2020-2021.json"
    fields = ["date", "year", "name", "title", "caderno", "page", "source", "link", "evidence"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(cleaned)
    json_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")

    by_year = Counter(r["year"] for r in cleaned)
    names = {r["name"] for r in cleaned if r.get("name") and "não identificado" not in r["name"].lower()}
    titles = Counter(re.sub(r"\s+", " ", (r.get("title") or "").strip().upper()) for r in cleaned)

    summary = {
        "period": "2020-2021",
        "source": "imprensaoficial.com.br (legado) — caderno Empresarial",
        "note": (
            "A API doe.sp.gov.br/v2/summary/structured e advanced-search não retornam "
            "edições de 2020-2021. Este arquivo foi montado a partir da busca legada, "
            "priorizando sumários e títulos com balanço/demonstrações."
        ),
        "total_rows": len(cleaned),
        "by_year": dict(by_year),
        "unique_names_identified": len(names),
        "top_titles": titles.most_common(20),
    }
    (OUT / "balancos_doe_resumo_2020-2021.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("\n==== RESUMO ====")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("CSV:", csv_path)
    print("JSON:", json_path)


if __name__ == "__main__":
    main()
