"""
Diagnóstico + coleta 2020/2021 via sumários do caderno Empresarial (Imprensa Oficial).
"""
from __future__ import annotations

import csv
import json
import re
import time
import urllib.parse
from collections import Counter
from pathlib import Path

import http.cookiejar
import urllib.request

OUT = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with opener.open(req, timeout=90) as resp:
        return resp.read()


def fetch_text(url: str) -> str:
    raw = fetch(url)
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")


def build_url(year: int, term: str, tip: str, vpc: str, mh: int = 15) -> str:
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
        f"&xhitlist_d=Empresarial+&xhitlist_hc=%5BXML%5D%5BKwic%2C3%5D&xhitlist_mh={mh}"
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


def clean(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s)
    s = (
        s.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&#231;", "ç")
        .replace("&#227;", "ã")
    )
    return re.sub(r"\s+", " ", s).strip()


def parse_cards(html: str) -> list[dict]:
    cards = []
    # each resultadoBuscaItem block until next or end
    for m in re.finditer(r'(?s)<div class="card shadow-sm resultadoBuscaItem">(.*?)</div>\s*</div>\s*<br', html):
        block = m.group(1)
        data_lbl = ""
        dm = re.search(r'lblData_\d+"[^>]*>([^<]+)<', block)
        if dm:
            data_lbl = dm.group(1).strip()
        snip = ""
        sm = re.search(r'(?s)class="bg-light text-dark"[^>]*>(.*?)</a>', block)
        if sm:
            snip = clean(sm.group(1))
        link = ""
        lm = re.search(r"link=([^&\"']+)", block)
        if lm:
            link = urllib.parse.unquote(lm.group(1))
        page = None
        pm = re.search(r"[?&]pagina=(\d+)", block)
        if pm:
            page = int(pm.group(1))
        date = None
        if data_lbl:
            dm2 = re.match(r"(\d{2})/(\d{2})/(\d{4})", data_lbl)
            if dm2:
                date = f"{dm2.group(3)}-{dm2.group(2)}-{dm2.group(1)}"
        cards.append({"date": date, "data_lbl": data_lbl, "page": page, "snippet": snip, "link": link})
    return cards


def diagnose_pagination():
    url1 = build_url(2020, "Balanço", "TUDO", "first")
    html1 = fetch_text(url1)
    c1 = parse_cards(html1)
    print("page1 total", parse_total(html1), "cards", len(c1))
    print(" first dates:", [c["data_lbl"] for c in c1[:3]])
    url2 = build_url(2020, "Balanço", "TUDO", "2")
    html2 = fetch_text(url2)
    c2 = parse_cards(html2)
    print("page2 cards", len(c2))
    print(" first dates:", [c["data_lbl"] for c in c2[:3]])
    same = c1 and c2 and c1[0]["data_lbl"] == c2[0]["data_lbl"] and c1[0]["snippet"][:40] == c2[0]["snippet"][:40]
    print("same_as_page1?", same)
    return c1


def pdf_url_from_link(link: str) -> str | None:
    # link like /2020/empresarial%202/abril/24/pag_0004_HASH.pdf
    if not link:
        return None
    if link.startswith("http"):
        return link
    # Imprensa Oficial PDF host patterns
    candidates = [
        "https://www.imprensaoficial.com.br" + link,
        "http://diariooficial.imprensaoficial.com.br" + link,
        "https://doe.sp.gov.br" + link,
    ]
    # encoded path often stored with %20
    return "https://www.imprensaoficial.com.br" + link if link.startswith("/") else None


def extract_balanco_from_sumario_text(text: str, date: str, link: str) -> list[dict]:
    """
    Parse sumário text. Typical:
      BALANÇO
      COMPANY NAME .................... 12
      OTHER COMPANY ................... 15
      AVISO DE ...
    or inline: BALANÇO COMPANY .... 8 OTHER .... 2
    """
    rows = []
    # normalize dots
    t = text.replace("\r", "\n")
    t = re.sub(r"[ \t]+\n", "\n", t)
    t = re.sub(r"\n{3,}", "\n\n", t)

    # Find BALANÇO section(s)
    # Split by major section headers common in Empresarial sumário
    section_headers = (
        r"BALAN[CÇ]O|DEMONSTRA[CÇ][OÕ]ES\s+FINANCEIRAS|DEMONSTRA[CÇ][OÕ]ES\s+CONT[AÁ]BEIS|"
        r"AVISO|EDITAL|EXTRATO|ATA\b|CONVOCA|LICITA|COMUNICADO|PUBLICIDADE|"
        r"CONSTITUI|ALTERA|DISTRATO|FUS[AÃ]O|CIS[AÃ]O|TRANSFORMA"
    )
    # Work line-based
    lines = [ln.strip() for ln in t.splitlines() if ln.strip()]
    mode_title = None
    for i, ln in enumerate(lines):
        up = ln.upper()
        # Section header alone
        if re.fullmatch(r"(?i)BALAN[CÇ]OS?(?:\s+PATRIMONIA(?:L|IS))?", ln) or re.fullmatch(
            r"(?i)DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS)", ln
        ):
            mode_title = ln.upper()
            continue
        if mode_title:
            # end section when another header-like short ALLCAPS word line without dots
            if re.fullmatch(rf"(?i)(?:{section_headers})", ln) and "BALAN" not in up and "DEMONSTRA" not in up:
                mode_title = None
                continue
            # company line with dotted leader
            m = re.match(r"^(.+?)\s*\.{2,}\s*(\d+)\s*$", ln)
            if m:
                name = m.group(1).strip(" .")
                if len(name) >= 5:
                    rows.append(
                        {
                            "date": date,
                            "name": name,
                            "title": mode_title,
                            "page_in_doe": m.group(2),
                            "link": link,
                            "source": "sumario-pdf",
                        }
                    )
                continue
            # company without dots but next?
            if len(ln) >= 5 and not re.search(r"(?i)di[aá]rio oficial|empresarial\s+\d|sum[aá]rio", ln):
                # avoid pure numbers
                if not re.fullmatch(r"\d+", ln):
                    # if line looks like company (has SA/LTDA or mostly caps)
                    if re.search(r"(?i)\b(S\.?A\.?|LTDA|LIMITADA|CIA\.|COMPANHIA|BANCO|FUNDA[CÇ][AÃ]O|INSTITUTO)\b", ln) or sum(
                        ch.isupper() for ch in ln if ch.isalpha()
                    ) >= 0.5 * max(1, sum(ch.isalpha() for ch in ln)):
                        rows.append(
                            {
                                "date": date,
                                "name": ln,
                                "title": mode_title,
                                "page_in_doe": None,
                                "link": link,
                                "source": "sumario-pdf",
                            }
                        )

    # Also inline form on one long line
    for m in re.finditer(
        r"(?i)(BALAN[CÇ]O|DEMONSTRA[CÇ][OÕ]ES\s+(?:FINANCEIRAS|CONT[AÁ]BEIS))\s+(.+?)(?=(?:AVISO|EDITAL|EXTRATO|ATA\b|CONVOCA|LICITA|COMUNICADO|DI[AÁ]RIO)|$)",
        t.replace("\n", " "),
    ):
        title = m.group(1).upper()
        body = m.group(2)
        for em in re.finditer(r"([A-ZÁÉÍÓÚÃÕÂÊÔÇ0-9][A-ZÁÉÍÓÚÃÕÂÊÔÇa-zà-ú0-9 &.\-/']{4,}?)\s*\.{2,}\s*(\d+)", body):
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


def try_extract_pdf_text(pdf_bytes: bytes) -> str:
    # Prefer pypdf/pdfminer if available; else crude
    try:
        import io
        from pypdf import PdfReader

        reader = PdfReader(io.BytesIO(pdf_bytes))
        parts = []
        for page in reader.pages[:3]:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    except Exception:
        pass
    try:
        import io
        from pdfminer.high_level import extract_text

        return extract_text(io.BytesIO(pdf_bytes)) or ""
    except Exception:
        pass
    # crude strings extraction
    text = []
    for m in re.finditer(rb"[\x20-\x7E\xA0-\xFF]{4,}", pdf_bytes):
        try:
            text.append(m.group(0).decode("latin-1", errors="ignore"))
        except Exception:
            pass
    return "\n".join(text)


def collect_sumarios(year: int, max_result_pages: int = 60) -> list[dict]:
    """Search pages that look like sumário mentioning BALANÇO and parse PDF text."""
    rows = []
    seen_links = set()

    # Search specifically for sumário + balanço
    queries = [
        ("TUDO", "Sumário BALANÇO"),
        ("PHRASE", "Sumário Caderno Empresarial"),
        ("TUDO", "Balanço"),
    ]

    for tip, term in queries:
        print(f"\n## {year} search {tip} {term}")
        html = fetch_text(build_url(year, term, tip, "first", mh=15))
        total = parse_total(html)
        print(" total", total)
        pages = min(max_result_pages, max(1, (total + 14) // 15))
        for p in range(1, pages + 1):
            vpc = "first" if p == 1 else str(p)
            if p > 1:
                html = fetch_text(build_url(year, term, tip, vpc, mh=15))
            cards = parse_cards(html)
            if not cards:
                print(" empty page", p)
                break
            useful = 0
            for c in cards:
                snip = c["snippet"] or ""
                link = c["link"]
                if not link or link in seen_links:
                    continue
                is_sumario = bool(re.search(r"(?i)sum[aá]rio", snip)) or (c["page"] is not None and c["page"] <= 5)
                has_bal = bool(re.search(r"(?i)balan[cç]o|demonstra[cç][oõ]es\s+(financeiras|cont)", snip))
                if tip == "TUDO" and term == "Balanço" and not (is_sumario and has_bal):
                    # only sumário hits for broad term
                    if not (is_sumario and has_bal):
                        continue
                if not (is_sumario or has_bal):
                    continue
                if not is_sumario and c["page"] and c["page"] > 6:
                    continue

                seen_links.add(link)
                pdf_path = link if link.startswith("/") else "/" + link
                # Fix double encoding
                pdf_url = "https://www.imprensaoficial.com.br" + pdf_path
                # Sometimes path already has %2520
                try:
                    pdf_bytes = fetch(pdf_url)
                except Exception as e:
                    # try unquote once
                    try:
                        pdf_url2 = "https://www.imprensaoficial.com.br" + urllib.parse.unquote(pdf_path)
                        pdf_bytes = fetch(pdf_url2)
                        pdf_url = pdf_url2
                    except Exception as e2:
                        print("  pdf fail", c["date"], e2)
                        continue

                if not pdf_bytes.startswith(b"%PDF"):
                    # maybe HTML wrapper
                    if b"%PDF" in pdf_bytes[:2000]:
                        pdf_bytes = pdf_bytes[pdf_bytes.find(b"%PDF") :]
                    else:
                        print("  not pdf", c["date"], pdf_url[:80], pdf_bytes[:40])
                        continue

                text = try_extract_pdf_text(pdf_bytes)
                extracted = extract_balanco_from_sumario_text(text, c["date"], pdf_url)
                if extracted:
                    useful += len(extracted)
                    rows.extend(extracted)
                else:
                    # fallback: company right after BALANÇO in snippet
                    for m in re.finditer(
                        r"(?i)BALAN[CÇ]O\s+([A-ZÁÉÍÓÚÃÕÂÊÔÇ0-9][A-ZÁÉÍÓÚÃÕÂÊÔÇa-zà-ú0-9 &.\-/']{4,80})",
                        snip,
                    ):
                        name = m.group(1).strip(" .")
                        if "compensados" in name.lower() or "valor" in name.lower():
                            continue
                        rows.append(
                            {
                                "date": c["date"],
                                "name": name,
                                "title": "BALANÇO",
                                "page_in_doe": None,
                                "link": pdf_url,
                                "source": "snippet-fallback",
                            }
                        )
                        useful += 1
            print(f" result-page {p}/{pages}: cards={len(cards)} new_links useful+= {useful} acum={len(rows)}")
            time.sleep(0.2)
            if tip == "PHRASE" and term.startswith("Sumário") and p >= 40:
                break
            if tip == "TUDO" and term == "Balanço" and p >= 25:
                break
    return rows


def main():
    print("=== diagnose pagination ===")
    diagnose_pagination()

    # check pdf lib
    try:
        import pypdf

        print("pypdf ok", pypdf.__version__)
    except Exception:
        print("pypdf missing - trying pip install")
        import subprocess, sys

        subprocess.check_call([sys.executable, "-m", "pip", "install", "pypdf", "-q"])

    all_rows = []
    for year in (2020, 2021):
        all_rows.extend(collect_sumarios(year))

    # dedupe
    uniq = {}
    for r in all_rows:
        k = (
            r.get("date"),
            re.sub(r"\s+", " ", (r.get("name") or "").strip().upper()),
            re.sub(r"\s+", " ", (r.get("title") or "").strip().upper()),
        )
        if k not in uniq:
            uniq[k] = r
    cleaned = list(uniq.values())
    cleaned.sort(key=lambda x: (x.get("date") or "", x.get("name") or ""))

    csv_path = OUT / "balancos_doe_empresarial_2020-2021.csv"
    json_path = OUT / "balancos_doe_empresarial_2020-2021.json"
    fields = ["date", "name", "title", "page_in_doe", "source", "link"]
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in cleaned:
            w.writerow(r)
    json_path.write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")

    by_year = Counter((r.get("date") or "")[:4] for r in cleaned)
    summary = {
        "period": "2020-2021",
        "source": "imprensaoficial.com.br (sumários do caderno Empresarial)",
        "note": "API nova doe.sp.gov.br sem cobertura estruturada para 2020-2021. Extraído de PDFs de sumário.",
        "total_rows": len(cleaned),
        "by_year": dict(by_year),
        "unique_names": len({r["name"].upper() for r in cleaned if r.get("name")}),
        "top_titles": Counter((r.get("title") or "").upper() for r in cleaned).most_common(15),
    }
    (OUT / "balancos_doe_resumo_2020-2021.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("CSV", csv_path)


if __name__ == "__main__":
    main()
