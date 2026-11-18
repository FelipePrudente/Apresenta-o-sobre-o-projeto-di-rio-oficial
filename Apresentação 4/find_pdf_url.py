import re
import urllib.parse
import urllib.request
import http.cookiejar

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"
cj = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))

link = "/2020/empresarial%202/abril/24/pag_0004_015e9b81faae78882708c9e6c3848896.pdf"
doc = (
    "https://www.imprensaoficial.com.br/DO/BuscaDO2001Documento_11_4.aspx?"
    + urllib.parse.urlencode(
        {
            "link": link,
            "pagina": "4",
            "data": "24/04/2020",
            "caderno": "Empresarial 2",
            "paginaordenacao": "100004",
        }
    )
)
print("DOC", doc)
req = urllib.request.Request(doc, headers={"User-Agent": UA})
with opener.open(req, timeout=60) as resp:
    html = resp.read().decode("utf-8", errors="replace")
print("len", len(html))

# find pdf/iframe/src/object
for pat in [
    r'src=["\']([^"\']+\.pdf[^"\']*)["\']',
    r'href=["\']([^"\']+\.pdf[^"\']*)["\']',
    r'(https?://[^"\'\s]+\.pdf[^"\'\s]*)',
    r'iframe[^>]+src=["\']([^"\']+)["\']',
    r'FileName["\']?\s*[:=]\s*["\']([^"\']+)["\']',
    r'link=([^&"\']+\.pdf)',
]:
    ms = re.findall(pat, html, flags=re.I)
    if ms:
        print("PAT", pat, "->", ms[:5])

# print interesting chunks
for key in ["pdf", "iframe", "viewer", "blob", "azure", "storage", "Gateway", "pag_0004"]:
    idx = html.lower().find(key.lower())
    if idx >= 0:
        print("\nKEY", key, html[max(0, idx - 80) : idx + 160].replace("\n", " "))

# Also try known storage patterns
cands = [
    "https://www.imprensaoficial.com.br/DO/GatewayPDF.aspx?link=" + urllib.parse.quote(link),
    "https://www.imprensaoficial.com.br/Certificacao/GatewayCertificaPDF.aspx?link=" + urllib.parse.quote(link),
    "http://diariooficial.imprensaoficial.com.br" + link,
    "https://do-legado.imprensaoficial.com.br" + link,
    "https://www.imprensaoficial.com.br/cgi/imagem?" + urllib.parse.urlencode({"f": link}),
]
for u in cands:
    try:
        req = urllib.request.Request(u, headers={"User-Agent": UA, "Referer": doc})
        with opener.open(req, timeout=30) as resp:
            b = resp.read(20)
            print("TRY", resp.status, b[:15], u[:90])
    except Exception as e:
        print("FAIL", getattr(e, "code", None), u[:90], e)
