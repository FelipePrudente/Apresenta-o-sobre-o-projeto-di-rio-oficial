"""
Censo ampliado de balancos 2020-2021 no caderno Empresarial (legado Imprensa Oficial).

Estrategia:
- Busca mes a mes por "Sumario Caderno Empresarial" (melhor cobertura que o ano inteiro)
- Complemento com "Sumario BALANCO" nos meses de pico (fev-jun)
- Extrai apenas linhas de sumario: EMPRESA ...... pagina sob secao BALANCO/DEMONSTRACOES
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
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

YEARS = (2020, 2021)
# todos os meses; pico recebe query extra
MONTHS = list(range(1, 13))
PEAK = {2, 3, 4, 5, 6}


def log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()


def month_bounds(year: int, month: int) -> tuple[str, str, str, str]:
    """Return start/end as YYYYMMDD and dd.mm.yyyy for IO query."""
    import calendar

    last = calendar.monthrange(year, month)[1]
    start = f"{year}{month:02d}01"
    end = f"{year}{month:02d}{last:02d}"
    start_br = f"01.{month:02d}.{year}"
    end_br = f"{last:02d}.{month:02d}.{year}"
    return start, end, start_br, end_br


def fetch(url: str, referer: str | None = None, retries: int = 3) -> bytes:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    last_err = None
    for i in range(retries):
        try:
            # opener local por chamada (thread-safe)
            local = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
            req = urllib.request.Request(url, headers=headers)
            with local.open(req, timeout=60) as resp:
                return resp.read()
        except Exception as e:
            last_err = e
            time.sleep(0.8 * (i + 1))
    raise last_err  # type: ignore


def fetch_text(url: str) -> str:
    return fetch(url).decode("utf-8", errors="replace")


def build_search_url(
    start: str,
    end: str,
    start_br: str,
    end_br: str,
    term: str,
    tip: str,
    vpc: str,
) -> str:
    if tip == "PHRASE":
        filtro = urllib.parse.quote(f'"{term}"').replace("%20", "+")
        q_term = urllib.parse.quote(f'"{term}"').replace("%20", "%2B")
    else:
        filtro = urllib.parse.quote(term).replace("%20", "+")
        q_term = urllib.parse.quote(term).replace("%20", "+")
    periodo = urllib.parse.quote(f"{start_br.replace('.', '/')} a {end_br.replace('.', '/')}", safe="").replace("%20", "+")
    # IO uses 01.01.2020 style inside field query
    return (
        "https://www.imprensaoficial.com.br/DO/BuscaDO2001Resultado_11_3.aspx"
        f"?f=xhitlist&filtrodatafimsalvar={end}&filtrodatainiciosalvar={start}"
        f"&filtrogrupos=Empresarial+&filtrogrupossalvar=Empresarial+"
        f"&filtropalavraschave={filtro}"
        f"&filtroperiodo={periodo}"
        f"&filtrotipopalavraschavesalvar={tip}&filtrotodosgrupos=False"
        f"&xhitlist_d=Empresarial+&xhitlist_hc=%5BXML%5D%5BKwic%2C3%5D&xhitlist_mh=15"
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
# also allow section header with trailing spaces / page noise
SECTION_START_SOFT = re.compile(
    r"(?im)^(BALAN[CÇ]OS?(?:\s+PATRIMONIA(?:L|IS))?|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS))\b"
)
SECTION_END = re.compile(
    r"(?im)^(AVISOS?|EDITAIS|EDITAL|EXTRATOS?|ATAS?|CONVOCA[CÇ]|LICITA|COMUNICADOS?|"
    r"PUBLICIDADE|CONSTITUI|ALTERA|DISTRATOS?|ASSEMBLEIA|CONTRATOS?|"
    r"DELIBERA|PORTARIA|RESOLU)\b"
)
BAD_NAME = re.compile(
    r"(?ix)^(sum[aá]rio|di[aá]rio|empresarial|notas?|ativo|passivo|circulante|"
    r"gerencial|entradas|sa[ií]das|investimentos|imobilizado|outros\s+cr|"
    r"dispon[ií]vel|total|soma|\(|\[|- |\d{1,3}[\.,]\d{3})"
)
COMPANYISH = re.compile(
    r"(?i)\b("
    r"S\.?\s*A\.?|S/A|LTDA|LIMITADA|CIA\.?|COMPANHIA|BANCO|FUNDA[CÇ]|"
    r"INSTITUTO|ASSOCIA|COOPERATIVA|HOLDING|PARTICIPA|EMPRESA|"
    r"SERVI[CÇ]O|HOSPITAL|SANTA\s+CASA|SINDICATO|FEDERA|"
    r"UNIVERSIDADE|FACULDADE|SPE\b|EIRELI|SEGUROS|LEASING|"
    r"URBANISMO|DOCAS|DTVM|CTVM|CORRETORA|RESSEGUR|SEGURADORA|"
    r"AG[EÊ]NCIA|AUTARQUIA|SOCIEDADE|GRUPO|INDUSTRIA|IND[UÚ]STRIA|"
    r"COM[EÉ]RCIO|COMERCIO|PARTICIPA[CÇ]|ENERGIA|SANEAMENTO|"
    r"METROPOLITANO|TRANSPORTES|PROCESSAMENTO|DESENVOLV"
    r")\b"
)


def looks_like_company(name: str) -> bool:
    if COMPANYISH.search(name):
        return True
    letters = [c for c in name if c.isalpha()]
    if not letters:
        return False
    up = sum(1 for c in letters if c.isupper()) / len(letters)
    # ALL-CAPS/title-ish corporate names without SA/LTDA in OCR sometimes
    return up >= 0.55 and len(name) >= 8 and name.count(" ") <= 14


def parse_sumario(text: str, date: str, link: str) -> list[dict]:
    rows: list[dict] = []
    t = text.replace("\u00a0", " ")
    t = re.sub(r"[ \t]+", " ", t)
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    head = "\n".join(lines[:15]).lower()
    is_sumario = ("sumário" in head) or ("sumario" in head) or ("sumÁrio" in head.lower())
    # some OCR miss the word; accept if early page has several dotted leaders after BALANCO
    mode = None
    dotted_in_mode = 0
    provisional: list[dict] = []

    def accept_name(name: str) -> bool:
        name = name.strip(" .-")
        if len(name) < 5 or len(name) > 140:
            return False
        if BAD_NAME.search(name):
            return False
        if re.search(r"(?i)\b(quando|aplicou|reconhec|compensad|milhares|valores expressos|notas explicativ)\b", name):
            return False
        if len(re.findall(r"\d", name)) > 6:
            return False
        return looks_like_company(name)

    for ln in lines:
        if SECTION_START.match(ln) or (SECTION_START_SOFT.match(ln) and len(ln) < 60):
            m = SECTION_START_SOFT.match(ln)
            mode = m.group(1).upper() if m else ln.upper()
            continue
        if mode and SECTION_END.match(ln) and not SECTION_START_SOFT.match(ln):
            mode = None
            continue
        if not mode:
            continue
        m = re.match(r"^(.+?)\s*[\.…]{2,}\s*(\d{1,4})\s*$", ln)
        if not m:
            m = re.match(r"^(.+?)\s{4,}(\d{1,4})\s*$", ln)
        if not m:
            continue
        name = m.group(1).strip(" .-")
        page = m.group(2)
        try:
            if int(page) > 250:
                continue
        except ValueError:
            continue
        if not accept_name(name):
            continue
        dotted_in_mode += 1
        provisional.append(
            {
                "date": date,
                "name": re.sub(r"\s+", " ", name),
                "title": mode,
                "page_in_doe": page,
                "link": link,
                "source": "sumario",
            }
        )

    # Inline block on sumario pages
    flat = " ".join(lines)
    if is_sumario or dotted_in_mode >= 2:
        for m in re.finditer(
            r"(?i)(BALAN[CÇ]OS?(?:\s+PATRIMONIA(?:L|IS))?|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS))\s+(.{5,3000}?)(?=(?:AVISOS?|EDITAIS|EDITAL|EXTRATOS?|ATAS?\b|CONVOCA|LICITA|COMUNICADOS?|DI[AÁ]RIO\s+OFICIAL)|$)",
            flat,
        ):
            title = re.sub(r"\s+", " ", m.group(1).upper()).strip()
            body = m.group(2)
            for em in re.finditer(
                r"([A-ZÁÉÍÓÚÃÕÂÊÔÇ0-9][A-ZÁÉÍÓÚÃÕÂÊÔÇa-zà-ú0-9 &.\-/']{3,}?)\s*[\.…]{2,}\s*(\d{1,4})",
                body,
            ):
                name = em.group(1).strip(" .-")
                page = em.group(2)
                try:
                    if int(page) > 250:
                        continue
                except ValueError:
                    continue
                if not accept_name(name):
                    continue
                provisional.append(
                    {
                        "date": date,
                        "name": re.sub(r"\s+", " ", name),
                        "title": title,
                        "page_in_doe": page,
                        "link": link,
                        "source": "sumario-inline",
                    }
                )

    if is_sumario or dotted_in_mode >= 2:
        rows.extend(provisional)
    return rows


def process_card(c: dict) -> list[dict]:
    link = c["link"]
    if not link:
        return []
    date_br = date_br_from_iso(c["date"], c["data_lbl"])
    gurl = gateway_pdf_url(link, c["page"], c["caderno"], date_br)
    try:
        pdf = fetch(gurl, referer="https://www.imprensaoficial.com.br/DO/")
    except Exception:
        return []
    if not pdf.startswith(b"%PDF"):
        return []
    try:
        return parse_sumario(pdf_text(pdf), c["date"], gurl)
    except Exception:
        return []


def iter_search(year: int, month: int, term: str, tip: str, max_pages: int = 40):
    start, end, start_br, end_br = month_bounds(year, month)
    html = fetch_text(build_search_url(start, end, start_br, end_br, term, tip, "first"))
    total = parse_total(html)
    pages = min(max_pages, max(1, (total + 14) // 15)) if total else 0
    log(f"  {year}-{month:02d} {tip}:{term} total={total} pages={pages}")
    if total == 0:
        return
    for p in range(1, pages + 1):
        vpc = "first" if p == 1 else str(p)
        if p > 1:
            html = fetch_text(build_search_url(start, end, start_br, end_br, term, tip, vpc))
        cards = parse_cards(html)
        if not cards:
            break
        yield from cards
        time.sleep(0.08)


def should_fetch(card: dict, require_bal: bool) -> bool:
    snip = card.get("snippet") or ""
    page = card.get("page")
    is_sumario = bool(re.search(r"(?i)sum[aá]rio", snip))
    has_bal = bool(re.search(r"(?i)balan[cç]o|demonstra[cç][oõ]es\s+(financeiras|cont)", snip))
    early = page is not None and page <= 8
    if require_bal:
        return (is_sumario and has_bal) or (is_sumario and early and has_bal)
    # for sumario caderno phrase: prefer sumario pages; if early page with balanco, keep
    return is_sumario or (early and has_bal)


def save(all_rows: list[dict], tag: str = "") -> dict:
    uniq = {}
    for r in all_rows:
        name = re.sub(r"\s+", " ", (r.get("name") or "").strip())
        title = re.sub(r"\s+", " ", (r.get("title") or "").strip().upper())
        date = r.get("date") or ""
        if not name or not title or not date:
            continue
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
    csv_path = OUT / "balancos_doe_empresarial_2020-2021.csv"
    json_path = OUT / "balancos_doe_empresarial_2020-2021.json"
    fields = ["date", "name", "title", "page_in_doe", "source", "link"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(cleaned)
    json_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
    by_year = Counter(r["date"][:4] for r in cleaned)
    by_month = Counter(r["date"][:7] for r in cleaned)
    summary = {
        "period": "2020-2021",
        "source": "imprensaoficial.com.br - sumarios caderno Empresarial (GatewayPDF)",
        "method": "busca mensal + parse de sumario (empresa......pagina)",
        "total_rows": len(cleaned),
        "by_year": dict(by_year),
        "by_month": dict(sorted(by_month.items())),
        "unique_names": len({r["name"].upper() for r in cleaned}),
        "top_titles": Counter(r["title"] for r in cleaned).most_common(10),
        "tag": tag,
    }
    (OUT / "balancos_doe_resumo_2020-2021.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    log(f"SAVE {tag} rows={len(cleaned)} unique_names={summary['unique_names']} by_year={summary['by_year']}")
    return summary


def main() -> None:
    all_rows: list[dict] = []
    seen_links: set[str] = set()
    fetched = 0

    for year in YEARS:
        for month in MONTHS:
            queries = [("PHRASE", "Sumário Caderno Empresarial", False, 30)]
            if month in PEAK:
                queries.append(("TUDO", "Sumário BALANÇO", True, 25))
                queries.append(("PHRASE", "Sumário Caderno Empresarial 2", False, 20))

            batch_cards = []
            for tip, term, require_bal, max_pages in queries:
                try:
                    for card in iter_search(year, month, term, tip, max_pages=max_pages):
                        link = card.get("link")
                        if not link or link in seen_links:
                            continue
                        if not should_fetch(card, require_bal):
                            continue
                        seen_links.add(link)
                        batch_cards.append(card)
                except Exception as e:
                    log(f"  search err {year}-{month:02d} {term}: {e}")

            log(f"  {year}-{month:02d} cards_to_fetch={len(batch_cards)}")
            # fetch PDFs with small pool
            with ThreadPoolExecutor(max_workers=4) as ex:
                futs = {ex.submit(process_card, c): c for c in batch_cards}
                for fut in as_completed(futs):
                    fetched += 1
                    try:
                        rows = fut.result()
                    except Exception:
                        rows = []
                    if rows:
                        all_rows.extend(rows)
            save(all_rows, tag=f"{year}-{month:02d}")
            time.sleep(0.2)

    summary = save(all_rows, tag="final")
    log(json.dumps(summary, ensure_ascii=False, indent=2))
    log(f"DONE fetched_pdfs~={fetched} links={len(seen_links)}")


if __name__ == "__main__":
    main()
