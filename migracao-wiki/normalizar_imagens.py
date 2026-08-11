"""Normaliza imagens em migracao-wiki/images/ que vieram da Fandom como webp
disfarçado (extensão .png/.jpg/.jpeg mas conteúdo real é webp).

Detecta webp via magic bytes (RIFF...WEBP nos primeiros 12 bytes) e converte
in-place usando `sips` (utilitário nativo do macOS), preservando o nome do
arquivo. Idempotente — re-rodar não toca arquivos já convertidos.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path


IMAGES = Path("/Users/inco/mark/wiki-dragon-experience/migracao-wiki/images")


def is_webp(path: Path) -> bool:
    """RIFF....WEBP nos primeiros 12 bytes → é webp."""
    try:
        with path.open("rb") as f:
            head = f.read(12)
    except Exception:
        return False
    return len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP"


def target_format(path: Path) -> str | None:
    """Mapeia extensão do nome → format string aceito pelo sips."""
    ext = path.suffix.lower()
    if ext == ".png":
        return "png"
    if ext in (".jpg", ".jpeg"):
        return "jpeg"
    return None


def convert(path: Path, fmt: str) -> bool:
    """Converte path (webp disfarçado) pro formato fmt, in-place. Retorna True se OK."""
    with tempfile.NamedTemporaryFile(suffix=path.suffix, delete=False) as tmp:
        tmp_path = Path(tmp.name)
    try:
        result = subprocess.run(
            ["sips", "-s", "format", fmt, str(path), "--out", str(tmp_path)],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(f"  [ERR] sips falhou em {path.name}: {result.stderr.strip()}")
            return False
        # sobrescreve o original
        shutil.move(str(tmp_path), str(path))
        return True
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


def main() -> int:
    arquivos = sorted([p for p in IMAGES.iterdir() if p.is_file()])
    total = len(arquivos)
    print(f"Total de arquivos: {total}")

    webp_disfarcados = []
    for p in arquivos:
        if is_webp(p):
            webp_disfarcados.append(p)
    print(f"WebP disfarçado a converter: {len(webp_disfarcados)}")
    if not webp_disfarcados:
        print("Nada a fazer.")
        return 0

    convertidos = 0
    falhas: list[str] = []
    sem_target = []
    for i, p in enumerate(webp_disfarcados, 1):
        fmt = target_format(p)
        if fmt is None:
            sem_target.append(p.name)
            print(f"  [{i}/{len(webp_disfarcados)}] SKIP {p.name} (extensão não suportada)")
            continue
        ok = convert(p, fmt)
        if ok:
            convertidos += 1
            print(f"  [{i}/{len(webp_disfarcados)}] ok {p.name} ({fmt})")
        else:
            falhas.append(p.name)

    print(f"\nConvertidos: {convertidos} | Falhas: {len(falhas)} | Sem target: {len(sem_target)}")
    if falhas:
        print("\nFalhas:")
        for nm in falhas:
            print(f"  - {nm}")
    if sem_target:
        print("\nSem target (extensão não suportada):")
        for nm in sem_target:
            print(f"  - {nm}")
    return 0 if not falhas else 1


if __name__ == "__main__":
    sys.exit(main())
