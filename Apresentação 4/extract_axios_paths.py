import re
from pathlib import Path

t = Path(r"c:\Users\28834737814\OneDrive - PRODESP\Área de Trabalho\tiraduvidas\_tmp_doe_js\_app-86e036c2caf07b70.js").read_text(encoding="utf-8", errors="ignore")

# Find axios get/post paths
for pat in [
    r'\.get\(["\']([^"\']+)["\']',
    r'\.post\(["\']([^"\']+)["\']',
    r'\.get\(`([^`]+)`',
    r'["\'](/v2/[^"\']+)["\']',
    r'["\'](v2/[^"\']+)["\']',
]:
    hits = sorted(set(re.findall(pat, t)))
    if hits:
        print("PAT", pat)
        for h in hits:
            print(" ", h)

# Print contexts around 'search'
print("\n=== search contexts ===")
for m in re.finditer(r".{0,50}search.{0,80}", t, re.I):
    s = m.group(0)
    if any(x in s for x in ("get(", "post(", "/v", "Search", "Publication", "Filter", "Legacy")):
        print(s[:160])
