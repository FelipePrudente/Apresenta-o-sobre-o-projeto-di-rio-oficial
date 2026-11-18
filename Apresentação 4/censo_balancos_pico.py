"""
Passagem agressiva fev-jun 2020/2021:
- busca 'Balanco' e 'Sumario' no Empresarial
- baixa paginas iniciais (1-8) e sumarios
- parse amplo de secoes BALANCO/DEMONSTRACOES
"""
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
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

OUT = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# load existing
EXISTING = OUT / "balancos_doe_empresarial_2020-2021.csv"


def log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()


def month_bounds(year: int, month: int):
    import calendar

    last = calendar.monthrange(year, month)[1]
    return (
        f"{year}{month:02d}01",
        f"{year}{month:02d}{last:02d}",
        f"01.{month:02d}.{year}",
        f"{last:02d}.{month:02d}.{year}",
    )


def fetch(url: str, referer: str | None = None, retries: int = 3) -> bytes:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    last = None
    for i in range(retries):
        try:
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
            )
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=60) as resp:
                return resp.read()
        except Exception as e:
            last = e
            time.sleep(0.6 * (i + 1))
    raise last  # type: ignore


def build_search_url(start, end, start_br, end_br, term, tip, vpc, mh=15):
    if tip == "PHRASE":
        filtro = urllib.parse.quote(f'"{term}"').replace("%20", "+")
        q_term = urllib.parse.quote(f'"{term}"').replace("%20", "%2B")
    else:
        filtro = urllib.parse.quote(term).replace("%20", "+")
        q_term = urllib.parse.quote(term).replace("%20", "+")
    periodo = urllib.parse.quote(
        f"{start_br.replace('.', '/')} a {end_br.replace('.', '/')}"
    ).replace("%20", "+")
    return (
        "https://www.imprensaoficial.com.br/DO/BuscaDO2001Resultado_11_3.aspx"
        f"?f=xhitlist&filtrodatafimsalvar={end}&filtrodatainiciosalvar={start}"
        f"&filtrogrupos=Empresarial+&filtrogrupossalvar=Empresarial+"
        f"&filtropalavraschave={filtro}&filtroperiodo={periodo}"
        f"&filtrotipopalavraschavesalvar={tip}&filtrotodosgrupos=False"
        f"&xhitlist_d=Empresarial+&xhitlist_hc=%5BXML%5D%5BKwic%2C3%5D&xhitlist_mh={mh}"
        f"&xhitlist_q=%5Bfield+%27dc%3Adatapubl%27%3A%3E%3D{start_br}%3C%3D{end_br}%5D%28{q_term}%29"
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
    return re.sub(r"\s+", " ", s.replace("&nbsp;", " ").replace("&amp;", "&")).strip()


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
                caderno = data_lbl.split(" - ")[1]
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


def gateway_pdf_url(link, page, caderno, date_br):
    pagina = str(page or 1)
    qs = (
        f"pagina={pagina}"
        f"&caderno={urllib.parse.quote(caderno or 'Empresarial')}"
        f"&data={urllib.parse.quote(date_br, safe='/')}"
        f"&link={urllib.parse.quote(link, safe='/%')}"
        f"&paginaordenacao=100{int(pagina):03d}"
    )
    return "https://www.imprensaoficial.com.br/DO/GatewayPDF.aspx?" + qs


def date_br(date_iso, data_lbl):
    if date_iso and re.match(r"\d{4}-\d{2}-\d{2}", date_iso):
        y, m, d = date_iso.split("-")
        return f"{d}/{m}/{y}"
    m = re.match(r"(\d{2}/\d{2}/\d{4})", data_lbl or "")
    return m.group(1) if m else ""


def pdf_text(b: bytes) -> str:
    return "\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(b)).pages)


SECTION_START = re.compile(
    r"(?im)^(BALAN[CÇ]OS?(?:\s+PATRIMONIA(?:L|IS))?|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS))\b.{0,40}$"
)
SECTION_END = re.compile(
    r"(?im)^(AVISOS?|EDITAIS|EDITAL|EXTRATOS?|ATAS?|CONVOCA|LICITA|COMUNICADOS?|"
    r"PUBLICIDADE|CONSTITUI|ALTERA|DISTRATOS?|ASSEMBLEIA|CONTRATOS?|DELIBERA|PORTARIA)\b"
)
BAD = re.compile(
    r"(?ix)^(sum[aá]rio|di[aá]rio|empresarial|notas?|ativo|passivo|circulante|"
    r"gerencial|entradas|sa[ií]das|investimentos|imobilizado|outros\s+cr|"
    r"dispon[ií]vel|total|soma|\(|\[|- |\d{1,3}[\.,]\d{3}|quando|aplicou)"
)
COMPANY = re.compile(
    r"(?i)\b(S\.?\s*A\.?|S/A|LTDA|LIMITADA|CIA\.?|COMPANHIA|BANCO|FUNDA[CÇ]|"
    r"INSTITUTO|ASSOCIA|COOPERATIVA|HOLDING|PARTICIPA|EMPRESA|SERVI[CÇ]O|"
    r"HOSPITAL|SANTA\s+CASA|SINDICATO|FEDERA|UNIVERSIDADE|FACULDADE|SPE\b|"
    r"EIRELI|SEGUROS|LEASING|DOCAS|DTVM|CTVM|CORRETORA|RESSEGUR|SEGURADORA|"
    r"AG[EÊ]NCIA|SOCIEDADE|GRUPO|IND[UÚ]STRIA|COM[EÉ]RCIO|ENERGIA|SANEAMENTO|"
    r"METROPOLITANO|TRANSPORTES|PROCESSAMENTO|DESENVOLV|URBANISMO|SHOP|PORTO)\b"
)


def accept(name: str) -> bool:
    name = name.strip(" .-")
    if len(name) < 5 or len(name) > 140:
        return False
    if BAD.search(name):
        return False
    if len(re.findall(r"\d", name)) > 6:
        return False
    if COMPANY.search(name):
        return True
    letters = [c for c in name if c.isalpha()]
    if not letters:
        return False
    up = sum(c.isupper() for c in letters) / len(letters)
    return up >= 0.5 and 8 <= len(name) and name.count(" ") <= 14


def parse_sumario(text: str, date: str, link: str) -> list[dict]:
    rows = []
    t = text.replace("\u00a0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    head = "\n".join(lines[:20]).lower()
    is_sumario = "sumario" in head or "sumário" in head

    mode = None
    got = 0
    for ln in lines:
        sm = SECTION_START.match(ln)
        if sm:
            mode = re.sub(r"\s+", " ", sm.group(0).upper()).strip()
            # also company on same line after section word?
            rest = ln[sm.end() :].strip(" .-")
            m2 = re.match(r"^(.+?)\s*[\.…]{2,}\s*(\d{1,4})\s*$", rest)
            if m2 and accept(m2.group(1)):
                rows.append(
                    {
                        "date": date,
                        "name": re.sub(r"\s+", " ", m2.group(1).strip(" .-")),
                        "title": mode.split()[0] if False else mode,
                        "page_in_doe": m2.group(2),
                        "link": link,
                        "source": "sumario-same-line",
                    }
                )
                got += 1
            continue
        if mode and SECTION_END.match(ln) and not SECTION_START.match(ln):
            mode = None
            continue
        if not mode:
            # one-line form without prior mode: BALANÇO COMPANY .... n
            m0 = re.match(
                r"(?i)^(BALAN[CÇ]OS?(?:\s+PATRIMONIA(?:L|IS))?|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS))\s+(.+?)\s*[\.…]{2,}\s*(\d{1,4})\s*$",
                ln,
            )
            if m0 and accept(m0.group(2)):
                rows.append(
                    {
                        "date": date,
                        "name": re.sub(r"\s+", " ", m0.group(2).strip(" .-")),
                        "title": re.sub(r"\s+", " ", m0.group(1).upper()),
                        "page_in_doe": m0.group(3),
                        "link": link,
                        "source": "one-line",
                    }
                )
                got += 1
            continue
        m = re.match(r"^(.+?)\s*[\.…]{2,}\s*(\d{1,4})\s*$", ln)
        if not m:
            m = re.match(r"^(.+?)\s{4,}(\d{1,4})\s*$", ln)
        if not m:
            continue
        try:
            if int(m.group(2)) > 250:
                continue
        except ValueError:
            continue
        if not accept(m.group(1)):
            continue
        rows.append(
            {
                "date": date,
                "name": re.sub(r"\s+", " ", m.group(1).strip(" .-")),
                "title": mode,
                "page_in_doe": m.group(2),
                "link": link,
                "source": "sumario",
            }
        )
        got += 1

    # inline multi-company on sumario pages
    flat = " ".join(lines)
    if is_sumario or got >= 1:
        for m in re.finditer(
            r"(?i)(BALAN[CÇ]OS?(?:\s+PATRIMONIA(?:L|IS))?|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS))\s+(.{5,4000}?)(?=(?:AVISOS?|EDITAIS|EDITAL|EXTRATOS?|ATAS?\b|CONVOCA|LICITA|COMUNICADOS?|DI[AÁ]RIO\s+OFICIAL)|$)",
            flat,
        ):
            title = re.sub(r"\s+", " ", m.group(1).upper())
            for em in re.finditer(
                r"([A-ZÁÉÍÓÚÃÕÂÊÔÇ0-9][A-ZÁÉÍÓÚÃÕÂÊÔÇa-zà-ú0-9 &.\-/']{3,}?)\s*[\.…]{2,}\s*(\d{1,4})",
                m.group(2),
            ):
                if not accept(em.group(1)):
                    continue
                try:
                    if int(em.group(2)) > 250:
                        continue
                except ValueError:
                    continue
                rows.append(
                    {
                        "date": date,
                        "name": re.sub(r"\s+", " ", em.group(1).strip(" .-")),
                        "title": title,
                        "page_in_doe": em.group(2),
                        "link": link,
                        "source": "inline",
                    }
                )
    return rows


def process(card):
    link = card["link"]
    if not link:
        return []
    gurl = gateway_pdf_url(
        link, card["page"], card["caderno"], date_br(card["date"], card["data_lbl"])
    )
    try:
        pdf = fetch(gurl, referer="https://www.imprensaoficial.com.br/DO/")
    except Exception:
        return []
    if not pdf.startswith(b"%PDF"):
        return []
    try:
        return parse_sumario(pdf_text(pdf), card["date"], gurl)
    except Exception:
        return []


def save(rows, tag=""):
    uniq = {}
    for r in rows:
        name = re.sub(r"\s+", " ", (r.get("name") or "").strip())
        title = re.sub(r"\s+", " ", (r.get("title") or "").strip().upper())
        date = r.get("date") or ""
        if not (name and title and date):
            continue
        # normalize title families
        if title.startswith("BALAN"):
            # keep full if patrimonial etc
            pass
        k = (date, name.upper(), title)
        if k not in uniq:
            uniq[k] = {
                "date": date,
                "name": name,
                "title": title,
                "page_in_doe": r.get("page_in_doe") or "",
                "source": r.get("source") or "",
                "link": r.get("link") or "",
            }
    cleaned = sorted(uniq.values(), key=lambda x: (x["date"], x["name"]))
    fields = ["date", "name", "title", "page_in_doe", "source", "link"]
    with (OUT / "balancos_doe_empresarial_2020-2021.csv").open(
        "w", newline="", encoding="utf-8-sig"
    ) as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(cleaned)
    (OUT / "balancos_doe_empresarial_2020-2021.json").write_text(
        json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    summary = {
        "period": "2020-2021",
        "source": "imprensaoficial.com.br - sumarios/paginas iniciais Empresarial",
        "method": "censo ampliado: busca mensal pico + paginas 1-8 + parse sumario",
        "total_rows": len(cleaned),
        "by_year": dict(Counter(r["date"][:4] for r in cleaned)),
        "by_month": dict(sorted(Counter(r["date"][:7] for r in cleaned).items())),
        "unique_names": len({r["name"].upper() for r in cleaned}),
        "top_titles": Counter(r["title"] for r in cleaned).most_common(10),
        "tag": tag,
    }
    (OUT / "balancos_doe_resumo_2020-2021.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(
        f"SAVE {tag} rows={summary['total_rows']} names={summary['unique_names']} years={summary['by_year']}"
    )
    return summary


def load_existing():
    rows = []
    if EXISTING.exists():
        rows = list(csv.DictReader(EXISTING.open(encoding="utf-8-sig")))
    return rows


def main():
    all_rows = load_existing()
    log(f"seed_rows={len(all_rows)}")
    seen = {r.get("link") for r in all_rows if r.get("link")}
    # also track by pdf path fragment
    seen_paths = set()
    for r in all_rows:
        link = r.get("link") or ""
        m = re.search(r"link=([^&]+)", link)
        if m:
            seen_paths.add(urllib.parse.unquote(m.group(1)))

    periods = []
    for year in (2020, 2021):
        for month in (2, 3, 4, 5, 6):
            periods.append((year, month))

    for year, month in periods:
        start, end, start_br, end_br = month_bounds(year, month)
        queries = [
            ("TUDO", "Balanço", 60),
            ("TUDO", "Sumário", 40),
            ("PHRASE", "Balanço Patrimonial", 40),
            ("PHRASE", "Demonstrações Financeiras", 40),
        ]
        batch = []
        for tip, term, max_pages in queries:
            try:
                html = fetch(
                    build_search_url(start, end, start_br, end_br, term, tip, "first")
                ).decode("utf-8", "replace")
            except Exception as e:
                log(f"search fail {year}-{month} {term}: {e}")
                continue
            total = parse_total(html)
            # guard absurd totals (broken filter)
            if total > 20000:
                log(f"  skip absurd total={total} for {year}-{month} {term}")
                continue
            pages = min(max_pages, max(1, (total + 14) // 15))
            log(f"{year}-{month:02d} {tip}:{term} total={total} pages={pages}")
            for p in range(1, pages + 1):
                vpc = "first" if p == 1 else str(p)
                if p > 1:
                    html = fetch(
                        build_search_url(start, end, start_br, end_br, term, tip, vpc)
                    ).decode("utf-8", "replace")
                for c in parse_cards(html):
                    link = c.get("link")
                    if not link or link in seen_paths:
                        continue
                    page = c.get("page")
                    snip = c.get("snippet") or ""
                    early = page is not None and page <= 8
                    sumario = bool(re.search(r"(?i)sum[aá]rio", snip))
                    # keep early pages or sumario mentions
                    if not (early or sumario):
                        continue
                    seen_paths.add(link)
                    batch.append(c)
                time.sleep(0.05)

        log(f"{year}-{month:02d} fetch={len(batch)}")
        with ThreadPoolExecutor(max_workers=5) as ex:
            futs = [ex.submit(process, c) for c in batch]
            for fut in as_completed(futs):
                try:
                    rows = fut.result()
                except Exception:
                    rows = []
                if rows:
                    all_rows.extend(rows)
        save(all_rows, tag=f"{year}-{month:02d}")

    summary = save(all_rows, tag="final")
    log(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
