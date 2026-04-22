import requests
import os
from urllib.parse import unquote

API = "https://dragonexperience.fandom.com/pt-br/api.php"
OUTPUT = "images"
os.makedirs(OUTPUT, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}

def list_all_images():
    images = []
    aicontinue = ""
    session = requests.Session()
    session.headers.update(HEADERS)
    while True:
        params = {
            "action": "query",
            "list": "allimages",
            "ailimit": "max",
            "format": "json",
        }
        if aicontinue:
            params["aicontinue"] = aicontinue
        r = session.get(API, params=params)
        data = r.json()
        images.extend(data["query"]["allimages"])
        if "continue" in data:
            aicontinue = data["continue"]["aicontinue"]
        else:
            break
    return images

def download(url, filename):
    path = os.path.join(OUTPUT, filename)
    if os.path.exists(path):
        return
    r = requests.get(url, headers=HEADERS, stream=True)
    if r.status_code == 200:
        with open(path, "wb") as f:
            for chunk in r.iter_content(8192):
                f.write(chunk)
        print(f"✓ {filename}")
    else:
        print(f"✗ {filename} ({r.status_code})")

imgs = list_all_images()
print(f"Encontradas {len(imgs)} imagens")
for img in imgs:
    name = unquote(img["name"])
    safe_name = "".join(c if c not in '<>:"/\\|?*' else "-" for c in name)
    download(img["url"], safe_name)