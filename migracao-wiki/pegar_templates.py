import os
import re
import json
import urllib.request
import urllib.parse

API = "https://dragonexperience.fandom.com/pt-br/api.php"
REPORT = "relatorio_templates.txt"
OUTPUT = "templates"
os.makedirs(OUTPUT, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

def read_template_names():
    names = []
    with open(REPORT, encoding="utf-8") as f:
        in_table = False
        for line in f:
            if line.startswith("-----"):
                in_table = True
                continue
            if not in_table:
                continue
            m = re.match(r"(\S.*?)\s{2,}\d+\s+\d+\s*$", line.rstrip())
            if m:
                names.append(m.group(1).strip())
    return names

def fetch_templates(names):
    """Queries up to 50 titles per request. Returns dict {title: content_or_None}."""
    results = {}
    for i in range(0, len(names), 50):
        batch = names[i:i+50]
        titles = "|".join(f"Predefinição:{n}" for n in batch)
        params = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "titles": titles,
            "format": "json",
            "formatversion": "2",
        }
        url = API + "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        for page in data.get("query", {}).get("pages", []):
            title = page.get("title", "")
            name = title.split(":", 1)[1] if ":" in title else title
            if page.get("missing"):
                results[name] = None
                continue
            revs = page.get("revisions", [])
            if not revs:
                results[name] = None
                continue
            results[name] = revs[0].get("slots", {}).get("main", {}).get("content", "")
    return results

def safe_filename(name):
    return re.sub(r"[^\w\-. ]", "_", name).strip()

def main():
    names = read_template_names()
    print(f"Templates a buscar: {len(names)}")
    templates = fetch_templates(names)
    found = sum(1 for v in templates.values() if v is not None)
    missing = [n for n, v in templates.items() if v is None]
    print(f"Encontrados: {found} | Ausentes: {len(missing)}")
    if missing:
        print("Ausentes:", ", ".join(missing))
    for name, content in templates.items():
        path = os.path.join(OUTPUT, safe_filename(name) + ".wiki")
        if content is None:
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"<!-- TEMPLATE NÃO ENCONTRADO NA API: Predefinição:{name} -->\n")
        else:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
    print(f"Salvo em: {OUTPUT}/")

if __name__ == "__main__":
    main()
