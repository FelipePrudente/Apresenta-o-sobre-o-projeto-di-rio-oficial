import csv
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas")
rows = list(csv.DictReader((OUT / "balancos_doe_empresarial_2020-2021.csv").open(encoding="utf-8-sig")))
print("raw", len(rows))

junk = re.compile(
    r"(?ix)^("
    r"\(\d+\)|"
    r"P[ÁA]GINA|EMPRESARIAL|DI[ÁA]RIO|SUM[ÁA]RIO|"
    r"ATIVO|PASSIVO|CIRCULANTE|NOTAS?|"
    r"Balan[cç]o\s+patrimonial|Demonstra|"
    r"Empresa\s+incorporada|Em\s+dezembro|Em\s+abril|"
    r"valores?\s|quando\s|reconhec|compensad|"
    r"CRC\b|Contador|Diretor"
    r")"
)

clean = []
for r in rows:
    name = (r.get("name") or "").strip()
    if len(name) < 5 or len(name) > 180:
        continue
    if junk.search(name):
        continue
    if name.count(" ") > 22:
        continue
    letters = [c for c in name if c.isalpha()]
    if letters:
        up = sum(1 for c in letters if c.isupper()) / len(letters)
        if up < 0.25 and not re.search(
            r"(?i)\b(S\.?A\.?|LTDA|CIA|COMPANHIA|BANCO|FUNDA|INSTITUTO|ASSOCI)\b", name
        ):
            continue
    r["name"] = re.sub(r"\s+", " ", name)
    r["title"] = re.sub(r"\s+", " ", (r.get("title") or "").strip())
    clean.append(r)

uniq = {}
for r in clean:
    k = (r["date"], r["name"].upper(), r["title"].upper())
    uniq[k] = r
clean = sorted(uniq.values(), key=lambda x: (x["date"], x["name"]))

fields = ["date", "name", "title", "page_in_doe", "source", "link"]
with (OUT / "balancos_doe_empresarial_2020-2021.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
    w.writeheader()
    w.writerows(clean)
(OUT / "balancos_doe_empresarial_2020-2021.json").write_text(
    json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8"
)

by_year = Counter(r["date"][:4] for r in clean)
summary = {
    "period": "2020-2021",
    "source": "imprensaoficial.com.br - sumarios caderno Empresarial (GatewayPDF)",
    "method_note": (
        "API doe.sp.gov.br sem cobertura estruturada para 2020-2021. "
        "Extraido dos sumarios do acervo legado (caderno Empresarial)."
    ),
    "comparability_note": (
        "Nao e identico ao levantamento 2025/2026 (API structured name/title). "
        "Aqui o name vem do sumario e o title da secao (BALANCO / DEMONSTRACOES...)."
    ),
    "total_rows": len(clean),
    "by_year": dict(by_year),
    "unique_names": len({r["name"].upper() for r in clean}),
    "top_titles": Counter(r["title"].upper() for r in clean).most_common(10),
}
(OUT / "balancos_doe_resumo_2020-2021.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
print("SAMPLES")
for r in clean[:8]:
    print((r["date"] + " | " + r["title"] + " | " + r["name"]).encode("ascii", "replace").decode())
