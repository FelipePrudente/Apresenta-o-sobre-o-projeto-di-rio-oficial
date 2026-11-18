"""Coleta balancos 2020-2021 a partir dos sumarios do caderno Empresarial (legado)."""
from __future__ import annotations

import csv
import json
import re
import sys
import time
import urllib.parse
import http.cookiejar
import urllib.request
from collections import Counter
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

OUT = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def log(msg: str) -> None:
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def fetch(url: str, referer: str | None = None) -> bytes:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers)
    with opener.open(req, timeout=60) as resp:
        return resp.read()


def fetch_text(url: str) -> str:
    return fetch(url).decode("utf-8", errors="replace")


def build_search_url(year: int, term: str, tip: str, vpc: str) -> str:
    if tip == "PHRASE":
        filtro = urllib.parse.quote(f'"{term}"').replace("%20", "+")
        q_term = urllib.parse.quote(f'"{term}"').replace("%20", "%2B")
    else:
        filtro = urllib.parse.quote(term).replace("%20", "+")
        q_term = urllib.parse.quote(term).replace("%20", "+")
    return (
        "https://www.imprensaoficial.com.br/DO/BuscaDO2001Resultado_11_3.aspx"
        f"?f=xhitlist&filtrodatafimsalvar={year}1231&filtrodatainiciosalvar={year}0101"
        f"&filtrogrupos=Empresarial+&filtrogrupossalvar=Empresarial+"
        f"&filtropalavraschave={filtro}"
        f"&filtroperiodo=01%2F01%2F{year}+a+31%2F12%2F{year}"
        f"&filtrotipopalavraschavesalvar={tip}&filtrotodosgrupos=False"
        f"&xhitlist_d=Empresarial+&xhitlist_hc=%5BXML%5D%5BKwic%2C3%5D&xhitlist_mh=15"
        f"&xhitlist_q=%5Bfield+%27dc%3Adatapubl%27%3A%3E%3D01.01.{year}%3C%3D31.12.{year}%5D%28{q_term}%29"
        f"&xhitlist_s=&xhitlist_sel=title%3BField%3Adc%3Atamanho%3BField%3Adc%3Adatapubl%3BField%3Adc%3Acaderno%3Bitem-bookmark%3Bhit-context"
        f"&xhitlist_vpc={vpc}&xhitlist_xsl=xhitlist.xsl"
    )


def parse_total(html: str) -> int:
    m = re.search(r'id="content_lblDocumentosEncontrados"[^>]*>([^<]+)<', html)
    if not m:
        return 0
    d = re.sub(r"[^\d]", "", m.group(1))
    return int(d) if d else 0


def clean_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = s.replace("&nbsp;", " ").replace("&amp;", "&").replace("&quot;", '"')
    return re.sub(r"\s+", " ", s).strip()


def parse_cards(html: str) -> list[dict]:
    cards = []
    for m in re.finditer(
        r'(?s)<div class="card shadow-sm resultadoBuscaItem">(.*?)</div>\s*</div>\s*<br',
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
            snip = clean_html(sm.group(1))
        link = ""
        lm = re.search(r"link=([^&\"']+)", block)
        if lm:
            link = urllib.parse.unquote(lm.group(1))
        page = None
        pm = re.search(r"[?&]pagina=(\d+)", block)
        if pm:
            page = int(pm.group(1))
        caderno = ""
        cm = re.search(r"[?&]caderno=([^&\"']+)", block)
        if cm:
            caderno = urllib.parse.unquote(cm.group(1).replace("+", " "))
        date = None
        if data_lbl:
            dm2 = re.match(r"(\d{2})/(\d{2})/(\d{4})", data_lbl)
            if dm2:
                date = f"{dm2.group(3)}-{dm2.group(2)}-{dm2.group(1)}"
            if not caderno and " - " in data_lbl:
                parts = data_lbl.split(" - ")
                if len(parts) > 1:
                    caderno = parts[1]
        cards.append(
            {
                "date": date,
                "data_lbl": data_lbl,
                "page": page,
                "caderno": caderno,
                "snippet": snip,
                "link": link,
            }
        )
    return cards


def gateway_pdf_url(link: str, page: int | None, caderno: str, date_br: str) -> str:
    pagina = str(page or 1)
    qs = (
        f"pagina={pagina}"
        f"&caderno={urllib.parse.quote(caderno or 'Empresarial')}"
        f"&data={urllib.parse.quote(date_br, safe='/')}"
        f"&link={urllib.parse.quote(link, safe='/%')}"
        f"&paginaordenacao=100{int(pagina):03d}"
    )
    return "https://www.imprensaoficial.com.br/DO/GatewayPDF.aspx?" + qs


def date_br_from_iso(date_iso: str | None, data_lbl: str) -> str:
    if date_iso and re.match(r"\d{4}-\d{2}-\d{2}", date_iso):
        y, m, d = date_iso.split("-")
        return f"{d}/{m}/{y}"
    m = re.match(r"(\d{2}/\d{2}/\d{4})", data_lbl or "")
    return m.group(1) if m else ""


def pdf_text(pdf_bytes: bytes) -> str:
    reader = PdfReader(BytesIO(pdf_bytes))
    return "\n".join((page.extract_text() or "") for page in reader.pages)


SECTION_START = re.compile(
    r"(?im)^(BALAN[CÇ]OS?(?:\s+PATRIMONIA(?:L|IS))?|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS))\s*$"
)
SECTION_END = re.compile(
    r"(?im)^(AVISOS?|EDITAIS|EDITAL|EXTRATOS?|ATAS?|CONVOCA|LICITA|COMUNICADOS?|"
    r"PUBLICIDADE|CONSTITUI|ALTERA|DISTRATOS?|ASSEMBLEIA|CONTRATOS?)\s*$"
)


def parse_sumario(text: str, date: str, link: str) -> list[dict]:
    rows = []
    t = text.replace("\u00a0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]

    mode = None
    for ln in lines:
        if SECTION_START.match(ln):
            mode = ln.upper()
            continue
        if mode and SECTION_END.match(ln):
            mode = None
            continue
        if not mode:
            continue
        m = re.match(r"^(.+?)\s*[\.…]{2,}\s*(\d+)\s*$", ln)
        if not m:
            m = re.match(r"^(.+?)\s{3,}(\d+)\s*$", ln)
        if m:
            name = m.group(1).strip(" .")
            if len(name) >= 5 and not re.search(r"(?i)sum[aá]rio|di[aá]rio oficial|empresarial\s+\d|notas explicativ", name):
                rows.append(
                    {
                        "date": date,
                        "name": name,
                        "title": mode,
                        "page_in_doe": m.group(2),
                        "link": link,
                        "source": "sumario",
                    }
                )
            continue
        # Publication header form: right after BALANÇO, company name without dots
        # only accept if looks like company and section just started (few rows so far for this mode/date)
        if re.search(r"(?i)\b(S\.?A\.?|LTDA|CIA\.|COMPANHIA|BANCO|FUNDA[CÇ]|INSTITUTO|ASSOCIAC|ASSOCIA)\b", ln):
            if len(ln) <= 160 and not re.search(r"(?i)quando|demonstrad|reconhec|valor de|data do", ln):
                rows.append(
                    {
                        "date": date,
                        "name": ln.strip(" ."),
                        "title": mode,
                        "page_in_doe": None,
                        "link": link,
                        "source": "header",
                    }
                )

    flat = " ".join(lines)
    for m in re.finditer(
        r"(?i)(?:Sum[aá]rio[^\.]{0,60})?(BALAN[CÇ]O|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS))\s+(.{10,2000}?)(?=(?:AVISO|EDITAL|EXTRATO|ATA\b|CONVOCA|LICITA|COMUNICADO|DI[AÁ]RIO\s+OFICIAL)|$)",
        flat,
    ):
        title = m.group(1).upper()
        body = m.group(2)
        for em in re.finditer(
            r"([A-ZÁÉÍÓÚÃÕÂÊÔÇ0-9][A-ZÁÉÍÓÚÃÕÂÊÔÇa-zà-ú0-9 &.\-/']{3,}?)\s*[\.…]{2,}\s*(\d+)",
            body,
        ):
            name = em.group(1).strip(" .")
            if len(name) >= 5:
                rows.append(
                    {
                        "date": date,
                        "name": name,
                        "title": title,
                        "page_in_doe": em.group(2),
                        "link": link,
                        "source": "sumario-inline",
                    }
                )
    return rows


def collect_year(year: int) -> list[dict]:
    rows: list[dict] = []
    seen_links: set[str] = set()

    # Two complementary queries
    queries = [
        ("PHRASE", "Sumário Caderno Empresarial", 80),
        ("TUDO", "Sumário BALANÇO", 40),
    ]

    for tip, term, max_pages in queries:
        log(f"## {year} {tip} {term}")
        html = fetch_text(build_search_url(year, term, tip, "first"))
        total = parse_total(html)
        pages = min(max_pages, max(1, (total + 14) // 15))
        log(f"total={total} pages_to_scan={pages}")

        for p in range(1, pages + 1):
            vpc = "first" if p == 1 else str(p)
            if p > 1:
                html = fetch_text(build_search_url(year, term, tip, vpc))
            cards = parse_cards(html)
            if not cards:
                log(f"empty page {p}")
                break
            got = 0
            for c in cards:
                link = c["link"]
                if not link or link in seen_links:
                    continue
                snip = c["snippet"] or ""
                starts_sumario = bool(re.match(r"(?i)^\s*sum[aá]rio\s+caderno", snip))
                has_bal = bool(re.search(r"(?i)balan[cç]o|demonstra[cç][oõ]es\s+(financeiras|cont)", snip))
                # For Sumário Caderno phrase: keep only those mentioning balanço/demonstrações
                if term.startswith("Sumário Caderno") and not (starts_sumario and has_bal):
                    if not (re.search(r"(?i)sum[aá]rio", snip) and has_bal and c["page"] and c["page"] <= 8):
                        continue
                if term == "Sumário BALANÇO" and not (re.search(r"(?i)sum[aá]rio", snip) and has_bal):
                    continue

                seen_links.add(link)
                date_br = date_br_from_iso(c["date"], c["data_lbl"])
                gurl = gateway_pdf_url(link, c["page"], c["caderno"], date_br)
                try:
                    pdf = fetch(gurl, referer="https://www.imprensaoficial.com.br/DO/")
                except Exception as e:
                    log(f"  pdf err {c['date']}: {e}")
                    continue
                if not pdf.startswith(b"%PDF"):
                    continue
                try:
                    extracted = parse_sumario(pdf_text(pdf), c["date"], gurl)
                except Exception as e:
                    log(f"  parse err {c['date']}: {e}")
                    continue
                if extracted:
                    rows.extend(extracted)
                    got += len(extracted)
            log(f"page {p}/{pages}: cards={len(cards)} +{got} acum={len(rows)} links={len(seen_links)}")
            time.sleep(0.1)
    return rows


def main() -> None:
    all_rows = []
    for year in (2020, 2021):
        all_rows.extend(collect_year(year))

    uniq = {}
    for r in all_rows:
        k = (
            r.get("date"),
            re.sub(r"\s+", " ", (r.get("name") or "").strip().upper()),
            re.sub(r"\s+", " ", (r.get("title") or "").strip().upper()),
        )
        if k not in uniq:
            uniq[k] = r
    cleaned = sorted(uniq.values(), key=lambda x: (x.get("date") or "", x.get("name") or ""))
    junk = re.compile(
        r"(?i)^(P[AÁ]GINA|EMPRESARIAL|DI[AÁ]RIO|SUM[AÁ]RIO|ATIVO|PASSIVO|CIRCULANTE|NOTAS?|"
        r"Balan[cç]o patrimonial|Demonstra[cç][aã]o do resultado)\b"
    )
    cleaned = [r for r in cleaned if r.get("name") and not junk.search(r["name"]) and len(r["name"]) >= 5]

    csv_path = OUT / "balancos_doe_empresarial_2020-2021.csv"
    json_path = OUT / "balancos_doe_empresarial_2020-2021.json"
    fields = ["date", "name", "title", "page_in_doe", "source", "link"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(cleaned)
    json_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")

    by_year = Counter((r.get("date") or "")[:4] for r in cleaned)
    summary = {
        "period": "2020-2021",
        "source": "imprensaoficial.com.br - sumarios caderno Empresarial (GatewayPDF)",
        "note": "API estruturada doe.sp.gov.br nao cobre 2020-2021. Lista a partir dos sumarios do acervo legado.",
        "total_rows": len(cleaned),
        "by_year": dict(by_year),
        "unique_names": len({r["name"].upper() for r in cleaned}),
        "top_titles": Counter((r.get("title") or "").upper() for r in cleaned).most_common(20),
    }
    (OUT / "balancos_doe_resumo_2020-2021.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(json.dumps(summary, ensure_ascii=False, indent=2))
    log(f"CSV={csv_path}")
    for r in cleaned[:12]:
        log(f"{r['date']} | {r['title']} | {r['name']}")


if __name__ == "__main__":
    main()
