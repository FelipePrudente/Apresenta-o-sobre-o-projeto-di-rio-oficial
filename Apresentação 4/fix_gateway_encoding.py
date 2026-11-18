import re
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

link = "/2020/empresarial%202/abril/24/pag_0004_015e9b81faae78882708c9e6c3848896.pdf"

# Build query carefully: keep %20 in link
qs = (
    "pagina=4"
    "&caderno=" + urllib.parse.quote("Empresarial 2")
    + "&data=" + urllib.parse.quote("24/04/2020", safe="/")
    + "&link=" + urllib.parse.quote(link, safe="/%")
    + "&paginaordenacao=100004"
)
url = "https://www.imprensaoficial.com.br/DO/GatewayPDF.aspx?" + qs
print(url)

req = urllib.request.Request(
    url,
    headers={
        "User-Agent": UA,
        "Referer": "https://www.imprensaoficial.com.br/DO/BuscaDO2001Documento_11_4.aspx",
    },
)
with opener.open(req, timeout=60) as resp:
    data = resp.read()
    print("ctype", resp.headers.get("Content-Type"), "len", len(data), "magic", data[:8])

out = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas\_tmp_gateway2.bin")
out.write_bytes(data)

if data.startswith(b"%PDF"):
    print("GOT PDF")
else:
    html = data.decode("utf-8", errors="replace")
    print("HTML title?", "NotificaErro" in html, "Gateway" in html)
    # find embed/object/pdfjs
    for m in re.finditer(r".{0,40}(pdf|PDFObject|embed|iframe|Viewer|aspx\?|blob).{0,80}", html):
        print(m.group(0).replace("\n", " ")[:160])
    # save html
    Path(str(out) + ".html").write_text(html, encoding="utf-8")
    print("saved html", len(html))
