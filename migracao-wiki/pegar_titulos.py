import requests
import json

API = "https://dragonexperience.fandom.com/pt-br/api.php"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}

def get_all_titles(namespace=0):
    titles = []
    apcontinue = ""
    session = requests.Session()
    session.headers.update(HEADERS)
    while True:
        params = {
            "action": "query",
            "list": "allpages",
            "aplimit": "max",
            "apnamespace": namespace,
            "format": "json",
        }
        if apcontinue:
            params["apcontinue"] = apcontinue
        r = session.get(API, params=params)
        if r.status_code != 200:
            print(f"Erro HTTP {r.status_code}")
            print(r.text[:500])
            break
        try:
            data = r.json()
        except json.JSONDecodeError:
            print("Resposta não é JSON:")
            print(r.text[:500])
            break
        titles.extend(p["title"] for p in data["query"]["allpages"])
        if "continue" in data:
            apcontinue = data["continue"]["apcontinue"]
        else:
            break
    return titles

titles = get_all_titles(namespace=0)
print(f"Total: {len(titles)}")

with open("titulos.txt", "w", encoding="utf-8") as f:
    f.write("\n".join(titles))