import re
import urllib.parse
import urllib.request
import http.cookiejar
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

params = {
    "pagina": "4",
    "caderno": "Empresarial 2",
    "data": "24/04/2020",
    "link": "/2020/empresarial%202/abril/24/pag_0004_015e9b81faae78882708c9e6c3848896.pdf",
    "paginaordenacao": "100004",
}
url = "https://www.imprensaoficial.com.br/DO/GatewayPDF.aspx?" + urllib.parse.urlencode(params)
print(url)
req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.imprensaoficial.com.br/"})
with opener.open(req, timeout=60) as resp:
    data = resp.read()
    ctype = resp.headers.get("Content-Type")
    print("ctype", ctype, "len", len(data), "start", data[:30])

Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas\_tmp_gateway.html").write_bytes(data)
html = data.decode("utf-8", errors="replace")
print(html[:2500])

for pat in [
    r'src=["\']([^"\']+)["\']',
    r'href=["\']([^"\']+)["\']',
    r'(https?://[^"\'\s]+)',
    r'file=["\']([^"\']+)["\']',
    r'url\(([^)]+)\)',
]:
    ms = re.findall(pat, html, flags=re.I)
    print(pat, ms[:15])
