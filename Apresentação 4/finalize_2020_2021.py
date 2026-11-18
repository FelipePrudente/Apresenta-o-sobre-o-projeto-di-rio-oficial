import csv
import json
import re
from collections import Counter
from pathlib import Path

OUT = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas")
rows = list(csv.DictReader((OUT / "balancos_doe_empresarial_2020-2021.csv").open(encoding="utf-8-sig")))

companyish = re.compile(
    r"(?i)\b("
    r"S\.?\s*A\.?|S/A|LTDA|LIMITADA|CIA\.?|COMPANHIA|BANCO|FUNDA[CÇ]|"
    r"INSTITUTO|ASSOCIA|COOPERATIVA|HOLDING|PARTICIPA|EMPRESA|"
    r"SERVI[CÇ]O|HOSPITAL|SANTA\s+CASA|SINDICATO|FEDERA|"
    r"UNIVERSIDADE|FACULDADE|SPE\b|EIRELI|SEGUROS|LEASING|"
    r"URBANISMO|DOCAS|REFOREST|REFLOREST|DTVM|CTVM|CORRETORA"
    r")\b"
)
bad = re.compile(
    r"(?i)^(gerencial|entradas|sa[ií]das|outros\s+cr[eé]ditos|imobilizado|"
    r"investimentos|ativo|passivo|circulante|\d|total|soma)"
)

clean = []
for r in rows:
    name = (r.get("name") or "").strip()
    if not companyish.search(name):
        continue
    if bad.search(name):
        continue
    if name.startswith("-") or name.startswith("("):
        continue
    # page suspiciously high often = table artifact
    try:
        p = int(r.get("page_in_doe") or 0)
    except ValueError:
        p = 0
    if p > 200:
        continue
    clean.append(r)

uniq = {}
for r in clean:
    k = (r["date"], r["name"].upper(), r["title"].upper())
    uniq[k] = r
clean = sorted(uniq.values(), key=lambda x: (x["date"], x["name"]))

fields = ["date", "name", "title", "page_in_doe", "source", "link"]
with (OUT / "balancos_doe_empresarial_2020-2021.csv").open("w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=fields)
    w.writeheader()
    w.writerows(clean)
(OUT / "balancos_doe_empresarial_2020-2021.json").write_text(
    json.dumps(clean, ensure_ascii=False, indent=2), encoding="utf-8"
)

# IO search volume context (from earlier probes)
io_volumes = {
    "2020": {
        "Balanço (termo amplo, paginas)": 7782,
        "Balanço Patrimonial (frase, paginas)": 5814,
        "Demonstrações Financeiras (frase, paginas)": 8627,
        "Demonstrações Contábeis (frase, paginas)": 3337,
    },
    "2021": {
        "Balanço Patrimonial (frase, paginas)": None,  # filled if known
        "Demonstrações Financeiras (frase, paginas)": 10173,
        "Demonstrações Contábeis (frase, paginas)": 3884,
    },
}

summary = {
    "period": "2020-2021",
    "source": "imprensaoficial.com.br - sumarios caderno Empresarial",
    "limitation": (
        "A API estruturada do doe.sp.gov.br NAO possui edicoes de 2020-2021. "
        "Este levantamento usa o acervo legado e extrai name/title a partir dos sumarios."
    ),
    "total_rows_sumario_limpo": len(clean),
    "by_year": dict(Counter(r["date"][:4] for r in clean)),
    "unique_names": len({r["name"].upper() for r in clean}),
    "top_titles": Counter(r["title"] for r in clean).most_common(10),
    "io_fulltext_page_hits_context": io_volumes,
    "note_on_volumes": (
        "Os totais de 'paginas' da busca legada contam ocorrencias em paginas do PDF "
        "(inclui notas, tabelas e repeticoes), NAO equivalem a quantidade de empresas."
    ),
}
(OUT / "balancos_doe_resumo_2020-2021.json").write_text(
    json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(summary, ensure_ascii=False, indent=2))
print("SAMPLES")
for r in clean[:20]:
    print(f"{r['date']} | {r['title']} | {r['name']}".encode("ascii", "replace").decode())
