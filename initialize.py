"""
Jurumim Revisor - desktop interface.

    python3 initialize.py                 open the window
    python3 initialize.py --check         only check that everything needed is installed
    python3 initialize.py --shortcut      add Jurumim Revisor to the applications menu
                                          (Linux; on WSL it shows in the Windows Start menu)

The window only builds and runs Jurumim_Revisor.py commands, shown at its bottom;
the terminal tool keeps working exactly as before, with or without this file.
"""
import argparse
import importlib.util
import os
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent


def verificar():
    """List of (ok, message). Anything not ok and not marked optional stops the window."""
    itens = []
    v = sys.version_info
    itens.append((v >= (3, 9), f"Python {v.major}.{v.minor}.{v.micro} (3.9 or newer needed)"))
    try:
        import tkinter
        itens.append((True, f"Tkinter {tkinter.TkVersion}"))
    except ImportError:
        itens.append((False, "Tkinter is missing. Ubuntu/Debian: sudo apt install python3-tk; "
                             "conda: conda install tk"))
    if sys.platform.startswith('linux') and not (os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY')):
        itens.append((False, "No graphical display. On WSL, update to WSL 2 with WSLg (wsl --update); "
                             "on a server, run Jurumim_Revisor.py in the terminal instead."))
    for modulo, uso in (('pandas', 'tables'), ('openpyxl', 'Excel files'), ('nltk', 'word counting'),
                        ('Bio', 'PubMed downloads')):
        ok = importlib.util.find_spec(modulo) is not None
        itens.append((ok, f"{modulo} ({uso})" + ('' if ok else ': pip install -r requirements.txt')))
    pil = importlib.util.find_spec('PIL') is not None
    itens.append((True, "Pillow (logo)" + ('' if pil else ': not installed, the window opens without the logo '
                                                          '(optional: pip install pillow)')))
    stl = importlib.util.find_spec('streamlit') is not None
    itens.append((True, "Streamlit (viewer)" + ('' if stl else ': not installed, "Open the viewer" will not work')))
    itens.append((Path(RAIZ / 'Jurumim_Revisor.py').is_file(), "Jurumim_Revisor.py next to initialize.py"))
    return itens


def aviso_fontes():
    """Tk without Xft (default conda 'tk' on Linux) only draws one bitmap font."""
    try:
        import tkinter as tk
        from tkinter import font
        r = tk.Tk()
        r.withdraw()
        basico = {f.lower() for f in font.families()} <= {'fixed'}
        r.destroy()
    except Exception:
        return None
    if basico:
        return ('This Tk has no font support (only the bitmap font "fixed"): the window works but '
                'looks plain.\n  Fix (conda): conda install -c conda-forge "tk=*=xft_*"\n'
                '  Fix (system Python): sudo apt install python3-tk')
    return None


def atalho():
    """A .desktop entry in ~/.local/share/applications (WSLg also lists it in the Windows Start menu)."""
    if not sys.platform.startswith('linux'):
        print("--shortcut is for Linux and WSL. On Windows or macOS, run: python3 initialize.py")
        return 1
    pasta = Path.home() / '.local' / 'share' / 'applications'
    pasta.mkdir(parents=True, exist_ok=True)
    arquivo = pasta / 'jurumim-revisor.desktop'
    icone = RAIZ / 'viewer' / 'assets' / 'jurumim_logo.jpg'
    arquivo.write_text(
        "[Desktop Entry]\nType=Application\nName=Jurumim Revisor\n"
        "Comment=Systematic review over PubMed, Web of Science and Scopus\n"
        f"Exec={sys.executable} {RAIZ / 'initialize.py'}\nPath={RAIZ}\nIcon={icone}\n"
        "Terminal=false\nCategories=Science;Education;\n", encoding='utf-8')
    arquivo.chmod(0o755)
    print(f"Shortcut written: {arquivo}")
    return 0


def main():
    p = argparse.ArgumentParser(description='Jurumim Revisor desktop interface')
    p.add_argument('--check', action='store_true', help='only check the requirements')
    p.add_argument('--shortcut', action='store_true', help='add Jurumim Revisor to the applications menu')
    a = p.parse_args()
    if a.shortcut:
        return atalho()

    itens = verificar()
    falta = [m for ok, m in itens if not ok]
    if a.check or falta:
        for ok, m in itens:
            print(f"  {'ok ' if ok else 'NO '} {m}")
    fontes = None if falta else aviso_fontes()
    if fontes:
        print(f"Note: {fontes}")
    if falta:
        print("\nThe window cannot open until the items marked NO are fixed.")
        return 1
    if a.check:
        return 0

    sys.path.insert(0, str(RAIZ))
    os.chdir(RAIZ)
    from gui.app import main as abrir
    abrir()
    return 0


if __name__ == '__main__':
    sys.exit(main())
