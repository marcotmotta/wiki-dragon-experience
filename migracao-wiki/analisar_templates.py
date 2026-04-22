import xml.etree.ElementTree as ET
import re
from collections import Counter

# ajuste o caminho
XML_PATH = "dump.xml"
NAMESPACE = "{http://www.mediawiki.org/xml/export-0.11/}"

# regex que pega o nome do template (primeira coisa após {{)
TEMPLATE_PATTERN = re.compile(r'\{\{\s*([^\|\}\n:]+?)\s*[\|\}\n]')

counter = Counter()
pages_using = {}  # template -> set de páginas que usam

tree = ET.parse(XML_PATH)
root = tree.getroot()

for page in root.findall(f"{NAMESPACE}page"):
    title_el = page.find(f"{NAMESPACE}title")
    if title_el is None:
        continue
    title = title_el.text

    revision = page.find(f"{NAMESPACE}revision")
    if revision is None:
        continue
    text_el = revision.find(f"{NAMESPACE}text")
    if text_el is None or not text_el.text:
        continue

    templates = TEMPLATE_PATTERN.findall(text_el.text)
    for t in templates:
        name = t.strip()
        # ignora parser functions (começam com #)
        if name.startswith("#"):
            continue
        counter[name] += 1
        pages_using.setdefault(name, set()).add(title)

print(f"Total de templates únicos: {len(counter)}\n")
print(f"{'Template':<40} {'Usos':>6} {'Páginas':>8}")
print("-" * 60)
for name, count in counter.most_common():
    n_pages = len(pages_using[name])
    print(f"{name:<40} {count:>6} {n_pages:>8}")