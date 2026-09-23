import argparse
import subprocess
import os
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Start the Jurumim Revisor viewer (Streamlit)."
    )

    parser.add_argument("--pubmed", required=True, help="PubMed file in MEDLINE format (.txt)")
    parser.add_argument("--general", required=True, help="general table from Jurumim_Revisor.py (.xlsx)")
    parser.add_argument("--pmid", required=True, help="PMID folder from Jurumim_Revisor.py --articles")

    args = parser.parse_args()

    for caminho in (args.pubmed, args.general, args.pmid):
        if not Path(caminho).exists():
            parser.error(f"not found: {caminho}")

    # The app reads its inputs from these variables
    os.environ["VIEWER_PUBMED_FILE"] = str(Path(args.pubmed).resolve())
    os.environ["VIEWER_GENERAL_XLSX"] = str(Path(args.general).resolve())
    os.environ["VIEWER_PMID_DIR"] = str(Path(args.pmid).resolve())

    print("Starting viewer...")
    print(f"PubMed file: {os.environ['VIEWER_PUBMED_FILE']}")
    print(f"General table: {os.environ['VIEWER_GENERAL_XLSX']}")
    print(f"PMID folder: {os.environ['VIEWER_PMID_DIR']}")

    viewer_app = Path(__file__).resolve().parent / "JR_Phleb.view.py"

    if not viewer_app.exists():
        raise FileNotFoundError(f"Viewer app not found: {viewer_app}")

    # Same interpreter as this script, so the right environment's Streamlit is used
    subprocess.run(
        [sys.executable, "-m", "streamlit", "run", str(viewer_app)],
        check=True
    )


if __name__ == "__main__":
    main()

