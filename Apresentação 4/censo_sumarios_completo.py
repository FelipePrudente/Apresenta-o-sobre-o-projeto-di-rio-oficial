"""
Censo 2020-2021: baixa TODOS os sumarios do caderno Empresarial e extrai secao BALANCO.
Nao exige 'balanco' no snippet (o sumario pode comecar por outra secao).
"""
from __future__ import annotations

import calendar
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
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader

OUT = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


def log(msg: str) -> None:
    sys.stdout.buffer.write((msg + "\n").encode("utf-8", errors="replace"))
    sys.stdout.flush()


def fetch(url: str, referer: str | None = None, retries: int = 3) -> bytes:
    headers = {"User-Agent": UA, "Accept": "*/*"}
    if referer:
        headers["Referer"] = referer
    err = None
    for i in range(retries):
        try:
            opener = urllib.request.build_opener(
                urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
            )
            req = urllib.request.Request(url, headers=headers)
            with opener.open(req, timeout=60) as resp:
                return resp.read()
        except Exception as e:
            err = e
            time.sleep(0.5 * (i + 1))
    raise err  # type: ignore


def build_url(d0: date, d1: date, term: str, tip: str, vpc: str) -> str:
    start = d0.strftime("%Y%m%d")
    end = d1.strftime("%Y%m%d")
    start_br = d0.strftime("%d.%m.%Y")
    end_br = d1.strftime("%d.%m.%Y")
    if tip == "PHRASE":
        filtro = urllib.parse.quote(f'"{term}"').replace("%20", "+")
        q_term = urllib.parse.quote(f'"{term}"').replace("%20", "%2B")
    else:
        filtro = urllib.parse.quote(term).replace("%20", "+")
        q_term = urllib.parse.quote(term).replace("%20", "+")
    periodo = urllib.parse.quote(f"{d0.strftime('%d/%m/%Y')} a {d1.strftime('%d/%m/%Y')}").replace(
        "%20", "+"
    )
    return (
        "https://www.imprensaoficial.com.br/DO/BuscaDO2001Resultado_11_3.aspx"
        f"?f=xhitlist&filtrodatafimsalvar={end}&filtrodatainiciosalvar={start}"
        f"&filtrogrupos=Empresarial+&filtrogrupossalvar=Empresarial+"
        f"&filtropalavraschave={filtro}&filtroperiodo={periodo}"
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
            snip = re.sub(r"<[^>]+>", " ", sm.group(1))
            snip = re.sub(r"\s+", " ", snip).strip()
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
        dt = None
        if data_lbl:
            dm2 = re.match(r"(\d{2})/(\d{2})/(\d{4})", data_lbl)
            if dm2:
                dt = f"{dm2.group(3)}-{dm2.group(2)}-{dm2.group(1)}"
            if not caderno and " - " in data_lbl:
                caderno = data_lbl.split(" - ")[1]
        cards.append(
            {
                "date": dt,
                "data_lbl": data_lbl,
                "page": page,
                "caderno": caderno,
                "snippet": snip,
                "link": link,
            }
        )
    return cards


def gateway(link, page, caderno, data_lbl, dt):
    if dt:
        y, m, d = dt.split("-")
        date_br = f"{d}/{m}/{y}"
    else:
        m = re.match(r"(\d{2}/\d{2}/\d{4})", data_lbl or "")
        date_br = m.group(1) if m else ""
    pagina = str(page or 1)
    qs = (
        f"pagina={pagina}"
        f"&caderno={urllib.parse.quote(caderno or 'Empresarial')}"
        f"&data={urllib.parse.quote(date_br, safe='/')}"
        f"&link={urllib.parse.quote(link, safe='/%')}"
        f"&paginaordenacao=100{int(pagina):03d}"
    )
    return "https://www.imprensaoficial.com.br/DO/GatewayPDF.aspx?" + qs


def pdf_text(b: bytes) -> str:
    return "\n".join((p.extract_text() or "") for p in PdfReader(BytesIO(b)).pages)


SECTION_START = re.compile(
    r"(?im)^(BALAN[CÇ]OS?(?:\s+PATRIMONIA(?:L|IS))?|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS))\b.{0,50}$"
)
SECTION_END = re.compile(
    r"(?im)^(AVISOS?|EDITAIS|EDITAL|EXTRATOS?|ATAS?|CONVOCA|LICITA|COMUNICADOS?|"
    r"PUBLICIDADE|CONSTITUI|ALTERA|DISTRATOS?|ASSEMBLEIA|CONTRATOS?|DELIBERA|PORTARIA|"
    r"ACORDOS?|CONVEN|HOMOLOGA|ADJUDICA|PREGAO|PREGÃO)\b"
)
BAD = re.compile(
    r"(?ix)^(sum[aá]rio|di[aá]rio|empresarial|notas?|ativo|passivo|circulante|"
    r"gerencial|entradas|sa[ií]das|investimentos|imobilizado|outros\s+cr|"
    r"dispon[ií]vel|total|soma|\(|\[|- |\d{1,3}[\.,]\d{3})"
)
COMPANY = re.compile(
    r"(?i)\b(S\.?\s*A\.?|S/A|LTDA|LIMITADA|CIA\.?|COMPANHIA|BANCO|FUNDA[CÇ]|"
    r"INSTITUTO|ASSOCIA|COOPERATIVA|HOLDING|PARTICIPA|EMPRESA|SERVI[CÇ]O|"
    r"HOSPITAL|SANTA\s+CASA|SINDICATO|FEDERA|UNIVERSIDADE|FACULDADE|SPE\b|"
    r"EIRELI|SEGUROS|LEASING|DOCAS|DTVM|CTVM|CORRETORA|RESSEGUR|SEGURADORA|"
    r"AG[EÊ]NCIA|SOCIEDADE|GRUPO|IND[UÚ]STRIA|COM[EÉ]RCIO|ENERGIA|SANEAMENTO|"
    r"METROPOLITANO|TRANSPORTES|PROCESSAMENTO|DESENVOLV|URBANISMO|PORTO|SHOP)\b"
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
    return up >= 0.55 and len(name) >= 8 and name.count(" ") <= 14


def parse_sumario(text: str, dt: str, link: str) -> list[dict]:
    rows = []
    t = re.sub(r"[ \t]+", " ", text.replace("\u00a0", " "))
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    mode = None
    for ln in lines:
        sm = SECTION_START.match(ln)
        if sm:
            mode = re.sub(r"\s+", " ", sm.group(0).upper()).strip()
            rest = ln[sm.end() :].strip(" .-")
            m2 = re.match(r"^(.+?)\s*[\.…]{2,}\s*(\d{1,4})\s*$", rest)
            if m2 and accept(m2.group(1)):
                rows.append(
                    {
                        "date": dt,
                        "name": re.sub(r"\s+", " ", m2.group(1).strip(" .-")),
                        "title": mode,
                        "page_in_doe": m2.group(2),
                        "link": link,
                        "source": "same-line",
                    }
                )
            continue
        if mode and SECTION_END.match(ln) and not SECTION_START.match(ln):
            mode = None
            continue
        if not mode:
            continue
        m = re.match(r"^(.+?)\s*[\.…]{2,}\s*(\d{1,4})\s*$", ln) or re.match(
            r"^(.+?)\s{4,}(\d{1,4})\s*$", ln
        )
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
                "date": dt,
                "name": re.sub(r"\s+", " ", m.group(1).strip(" .-")),
                "title": mode,
                "page_in_doe": m.group(2),
                "link": link,
                "source": "sumario",
            }
        )

    # inline
    flat = " ".join(lines)
    if re.search(r"(?i)sum[aá]rio", flat) or rows:
        for m in re.finditer(
            r"(?i)(BALAN[CÇ]OS?(?:\s+PATRIMONIA(?:L|IS))?|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS))\s+(.{5,5000}?)(?=(?:AVISOS?|EDITAIS|EDITAL|EXTRATOS?|ATAS?\b|CONVOCA|LICITA|COMUNICADOS?|DI[AÁ]RIO\s+OFICIAL)|$)",
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
                        "date": dt,
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
    url = gateway(link, card["page"], card["caderno"], card["data_lbl"], card["date"])
    try:
        pdf = fetch(url, referer="https://www.imprensaoficial.com.br/DO/")
    except Exception:
        return []
    if not pdf.startswith(b"%PDF"):
        return []
    try:
        return parse_sumario(pdf_text(pdf), card["date"], url)
    except Exception:
        return []


def save(rows, tag=""):
    uniq = {}
    for r in rows:
        name = re.sub(r"\s+", " ", (r.get("name") or "").strip())
        title = re.sub(r"\s+", " ", (r.get("title") or "").strip().upper())
        dt = r.get("date") or ""
        if not (name and title and dt):
            continue
        k = (dt, name.upper(), title)
        if k not in uniq:
            uniq[k] = {
                "date": dt,
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
        "source": "imprensaoficial.com.br - todos os sumarios Empresarial",
        "method": "busca Sumario Caderno Empresarial (sem exigir balanco no snippet) + parse secao",
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
    log(f"SAVE {tag} rows={summary['total_rows']} names={summary['unique_names']} {summary['by_year']}")
    return summary


def weekdays(d0: date, d1: date):
    d = d0
    while d <= d1:
        if d.weekday() < 6:  # mon-sat (DOE sometimes sat)
            yield d
        d += timedelta(days=1)


def main():
    all_rows = []
    seed = OUT / "balancos_doe_empresarial_2020-2021.csv"
    if seed.exists():
        all_rows = list(csv.DictReader(seed.open(encoding="utf-8-sig")))
    log(f"seed={len(all_rows)}")

    seen = set()
    for r in all_rows:
        link = r.get("link") or ""
        m = re.search(r"link=([^&]+)", urllib.parse.unquote(link))
        if m:
            seen.add(urllib.parse.unquote(m.group(1)))
        # also raw path
        if "/20" in link:
            mm = re.search(r"(/20\d{2}/[^&\s]+?\.pdf)", urllib.parse.unquote(link))
            if mm:
                seen.add(mm.group(1))

    # 1) Full-year phrase search for sumarios (paginate all, fetch all sumario-like)
    for year in (2020, 2021):
        d0, d1 = date(year, 1, 1), date(year, 12, 31)
        for tip, term, max_pages in [
            ("PHRASE", "Sumário Caderno Empresarial", 80),
            ("PHRASE", "Sumário Caderno Empresarial 2", 80),
            ("TUDO", "Sumário Caderno", 60),
        ]:
            html = fetch(build_url(d0, d1, term, tip, "first")).decode("utf-8", "replace")
            total = parse_total(html)
            if total > 30000:
                log(f"skip absurd {year} {term} total={total}")
                continue
            pages = min(max_pages, max(1, (total + 14) // 15))
            log(f"{year} {tip}:{term} total={total} pages={pages}")
            batch = []
            for p in range(1, pages + 1):
                vpc = "first" if p == 1 else str(p)
                if p > 1:
                    html = fetch(build_url(d0, d1, term, tip, vpc)).decode("utf-8", "replace")
                for c in parse_cards(html):
                    link = c.get("link")
                    if not link or link in seen:
                        continue
                    snip = c.get("snippet") or ""
                    page = c.get("page")
                    # ANY sumario page or early page from this search
                    if re.search(r"(?i)sum[aá]rio", snip) or (page is not None and page <= 10):
                        seen.add(link)
                        batch.append(c)
                time.sleep(0.05)
            log(f"  fetch_batch={len(batch)}")
            with ThreadPoolExecutor(max_workers=5) as ex:
                for fut in as_completed([ex.submit(process, c) for c in batch]):
                    try:
                        rows = fut.result()
                    except Exception:
                        rows = []
                    if rows:
                        all_rows.extend(rows)
            save(all_rows, tag=f"{year}-{term[:20]}")

    # 2) Day-by-day peak season (fev-jun) for missed editions
    for year in (2020, 2021):
        for month in (2, 3, 4, 5, 6):
            last = calendar.monthrange(year, month)[1]
            batch = []
            for d in weekdays(date(year, month, 1), date(year, month, last)):
                try:
                    html = fetch(build_url(d, d, "Sumário", "TUDO", "first")).decode(
                        "utf-8", "replace"
                    )
                except Exception:
                    continue
                total = parse_total(html)
                if total == 0:
                    continue
                for c in parse_cards(html):
                    link = c.get("link")
                    if not link or link in seen:
                        continue
                    snip = c.get("snippet") or ""
                    page = c.get("page")
                    if re.search(r"(?i)sum[aá]rio", snip) or (page is not None and page <= 8):
                        seen.add(link)
                        batch.append(c)
                # also page 2 of results if many
                if total > 15:
                    try:
                        html2 = fetch(build_url(d, d, "Sumário", "TUDO", "2")).decode(
                            "utf-8", "replace"
                        )
                        for c in parse_cards(html2):
                            link = c.get("link")
                            if not link or link in seen:
                                continue
                            snip = c.get("snippet") or ""
                            page = c.get("page")
                            if re.search(r"(?i)sum[aá]rio", snip) or (
                                page is not None and page <= 8
                            ):
                                seen.add(link)
                                batch.append(c)
                    except Exception:
                        pass
                time.sleep(0.08)
            log(f"daypass {year}-{month:02d} batch={len(batch)}")
            with ThreadPoolExecutor(max_workers=5) as ex:
                for fut in as_completed([ex.submit(process, c) for c in batch]):
                    try:
                        rows = fut.result()
                    except Exception:
                        rows = []
                    if rows:
                        all_rows.extend(rows)
            save(all_rows, tag=f"day-{year}-{month:02d}")

    summary = save(all_rows, tag="final")
    log(json.dumps(summary, ensure_ascii=False, indent=2))
    for r in sorted(all_rows, key=lambda x: (x.get("date") or "", x.get("name") or ""))[:12]:
        log(f"{r.get('date')} | {r.get('title')} | {r.get('name')}")


if __name__ == "__main__":
    main()
