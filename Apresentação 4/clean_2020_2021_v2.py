import csv
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas")
# Reload from JSON which still has all fields after previous clean - but previous clean already dropped some.
# Better: re-run from the scan raw if available. The CSV was overwritten.
# We still have the JSON from before clean? It was overwritten too.
# Use current file and apply stricter filters; also accept only rows with page_in_doe
# and company-like names.

rows = list(csv.DictReader((OUT / "balancos_doe_empresarial_2020-2021.csv").open(encoding="utf-8-sig")))
print("input", len(rows))

prose = re.compile(
    r"(?i)\b("
    r"quando|aplicou|efetua|possui|somente|visto\s+que|confirmar|remunera|"
    r"compromisso|normas\s+estabelecidas|transi[cç][aã]o|arrendamento|"
    r"ativos?\s+biol|reavalia|tesouraria|controlada|incorporada|"
    r"valores\s+expressos|milhares|notas\s+explicativ|demonstrad|"
    r"reconhecid|compensad|passivo|circulante|dispon[ií]vel"
    r")\b"
)
companyish = re.compile(
    r"(?i)\b("
    r"S\.?\s*A\.?|S/A|LTDA|LIMITADA|CIA\.?|COMPANHIA|BANCO|FUNDA[CÇ][AÃ]O|"
    r"INSTITUTO|ASSOCIA[CÇ][AÃ]O|COOPERATIVA|HOLDING|PARTICIPA[CÇ]|EMPRESA|"
    r"SERVI[CÇ]O|HOSPITAL|SANTA\s+CASA|SINDICATO|FEDERA[CÇ]|CLUBE|ESCOLA|"
    r"UNIVERSIDADE|FACULDADE|CONDOM[IÍ]NIO|SPE\b|EIRELI"
    r")\b"
)

clean = []
for r in rows:
    name = (r.get("name") or "").strip()
    title = (r.get("title") or "").strip().upper()
    if not name or not title:
        continue
    if name.startswith("(") or name.startswith("[") or name.startswith('"'):
        continue
    if prose.search(name):
        continue
    if len(name) < 5 or len(name) > 140:
        continue
    # Prefer entries with page number from sumario dotted leaders
    has_page = bool(r.get("page_in_doe"))
    looks_company = bool(companyish.search(name))
    letters = [c for c in name if c.isalpha()]
    up_ratio = (sum(1 for c in letters if c.isupper()) / len(letters)) if letters else 0
    # Keep if:
    # 1) has page_in_doe and (companyish OR uppercase-ish)
    # 2) or companyish with decent length and not prose
    if has_page:
        if not (looks_company or up_ratio >= 0.45):
            continue
    else:
        if not looks_company:
            continue
        if up_ratio < 0.35 and not re.search(r"(?i)\b(S\.?A\.?|LTDA)\b", name):
            continue

    clean.append(
        {
            "date": r.get("date"),
            "name": re.sub(r"\s+", " ", name),
            "title": re.sub(r"\s+", " ", title),
            "page_in_doe": r.get("page_in_doe") or "",
            "source": r.get("source") or "",
            "link": r.get("link") or "",
        }
    )

uniq = {}
for r in clean:
    k = (r["date"], r["name"].upper(), r["title"].upper())
    uniq[k] = r
clean = sorted(uniq.values(), key=lambda x: (x["date"] or "", x["name"]))

fields = ["date", "name", "title", "page_in_doe", "source", "link"]
with (OUT / "balancos_doe_empresarial_2020-2021.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(clean)
(OUT / "balancos_doe_empresarial_2020-2021.json").write_text(
    json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8"
)

by_year = Counter((r["date"] or "")[:4] for r in clean)
by_title = Counter(r["title"] for r in clean)
summary = {
    "period": "2020-2021",
    "source": "imprensaoficial.com.br - sumarios caderno Empresarial (GatewayPDF)",
    "method_note": (
        "API doe.sp.gov.br sem cobertura estruturada para 2020-2021. "
        "Extraido dos sumarios do acervo legado (caderno Empresarial)."
    ),
    "comparability_note": (
        "Nao e 1:1 com 2025/2026 (API structured). Aqui name=empresa no sumario; "
        "title=secao (BALANCO / DEMONSTRACOES...)."
    ),
    "total_rows": len(clean),
    "by_year": dict(by_year),
    "unique_names": len({r["name"].upper() for r in clean}),
    "top_titles": by_title.most_common(10),
    "with_page_in_doe": sum(1 for r in clean if r["page_in_doe"]),
}
(OUT / "balancos_doe_resumo_2020-2021.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
print("SAMPLES")
for r in clean[:12]:
    line = f"{r['date']} | {r['title']} | {r['name']}"
    print(line.encode("ascii", "replace").decode())
