#!/usr/bin/env python3
"""
genera_contesto.py

Scansiona la cartella del progetto (root in cui viene eseguito lo script)
e genera un unico file di testo (context.txt) contenente tutti i file
di codice/testo del progetto, ognuno preceduto da un'intestazione con
il percorso relativo. Utile per caricare l'intero contesto di un
progetto su Claude.

Uso:
    python genera_contesto.py
    python genera_contesto.py --output mio_contesto.txt
    python genera_contesto.py --max-size-kb 500
"""

import argparse
import os

# Cartelle da escludere sempre (dipendenze, cache, VCS, ambienti virtuali, build)
EXCLUDED_DIRS = {
    ".git", ".svn", ".hg", "__pycache__", ".mypy_cache", ".pytest_cache",
    "node_modules", "venv", ".venv", "env", ".env", "dist", "build",
    ".idea", ".vscode", ".next", ".nuxt", "target", "bin", "obj",
    ".tox", "site-packages", "coverage", ".cache",
    "sessions","test_old"
}

# Estensioni di file binari/da ignorare (immagini, archivi, eseguibili, media, ecc.)
EXCLUDED_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".ico", ".webp", ".svg",
    ".pdf", ".zip", ".tar", ".gz", ".rar", ".7z",
    ".exe", ".dll", ".so", ".dylib", ".bin", ".class", ".jar",
    ".mp3", ".mp4", ".avi", ".mov", ".mkv", ".wav",
    ".ttf", ".otf", ".woff", ".woff2", ".eot",
    ".pyc", ".pyo", ".db", ".sqlite", ".sqlite3",
    ".lock",
}

# Nomi di file specifici da escludere
EXCLUDED_FILES = {
    "package-lock.json", "yarn.lock", "poetry.lock", "Pipfile.lock",
    ".DS_Store",
}


def is_text_file(filepath, blocksize=1024):
    """Verifica euristicamente se un file è testuale (non binario)."""
    try:
        with open(filepath, "rb") as f:
            chunk = f.read(blocksize)
        if b"\x00" in chunk:
            return False
        return True
    except Exception:
        return False


def should_skip(path, filename, max_size_bytes):
    ext = os.path.splitext(filename)[1].lower()
    if filename in EXCLUDED_FILES:
        return True
    if ext in EXCLUDED_EXTENSIONS:
        return True
    try:
        if os.path.getsize(path) > max_size_bytes:
            return True
    except OSError:
        return True
    if not is_text_file(path):
        return True
    return False


def collect_files(root_dir, script_name, output_name, max_size_bytes):
    collected = []
    for current_root, dirs, files in os.walk(root_dir):
        # Filtra le cartelle escluse (modifica dirs in place per fermare la ricorsione)
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".git")]

        for filename in sorted(files):
            if filename in (script_name, output_name):
                continue
            full_path = os.path.join(current_root, filename)
            if should_skip(full_path, filename, max_size_bytes):
                continue
            rel_path = os.path.relpath(full_path, root_dir)
            collected.append((rel_path, full_path))
    return collected


def build_context_file(root_dir, output_path, max_size_bytes):
    script_name = os.path.basename(__file__)
    output_name = os.path.basename(output_path)

    files = collect_files(root_dir, script_name, output_name, max_size_bytes)

    with open(output_path, "w", encoding="utf-8") as out:
        out.write(f"# CONTESTO PROGETTO\n")
        out.write(f"# Cartella radice: {os.path.abspath(root_dir)}\n")
        out.write(f"# Numero di file inclusi: {len(files)}\n")
        out.write("# Elenco file:\n")
        for rel_path, _ in files:
            out.write(f"#   - {rel_path}\n")
        out.write("\n" + "=" * 80 + "\n\n")

        for rel_path, full_path in files:
            out.write(f"{'=' * 80}\n")
            out.write(f"FILE: {rel_path}\n")
            out.write(f"{'=' * 80}\n\n")
            try:
                with open(full_path, "r", encoding="utf-8", errors="replace") as f:
                    out.write(f.read())
            except Exception as e:
                out.write(f"[Impossibile leggere il file: {e}]\n")
            out.write("\n\n")

    return len(files)


def main():
    parser = argparse.ArgumentParser(
        description="Unisce tutti i file testuali di un progetto in un unico file di testo."
    )
    parser.add_argument(
        "--output", "-o", default="context.txt",
        help="Nome del file di output (default: context.txt)"
    )
    parser.add_argument(
        "--max-size-kb", type=int, default=1024,
        help="Dimensione massima per singolo file, in KB (default: 1024 = 1MB)"
    )
    parser.add_argument(
        "--root", default=".",
        help="Cartella radice da scansionare (default: cartella corrente)"
    )
    args = parser.parse_args()

    max_size_bytes = args.max_size_kb * 1024
    n = build_context_file(args.root, args.output, max_size_bytes)
    print(f"Fatto! {n} file inclusi in '{args.output}'.")


if __name__ == "__main__":
    main()