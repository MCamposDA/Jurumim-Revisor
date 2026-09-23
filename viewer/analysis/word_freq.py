import pandas as pd
from pathlib import Path

# =====================================================
# General table
# =====================================================

def load_global_frequency_table(path):
    """
    Load the general table written by Jurumim_Revisor.py, sorted by TI+AB count.
    keep_default_na=False keeps words such as "na" and "nan" as text.
    """
    df = pd.read_excel(path, keep_default_na=False, na_values=[])

    df = df.sort_values(
        by="frequencia_tiab",
        ascending=False
    ).reset_index(drop=True)

    return df


# =====================================================
# Per-article table
# =====================================================

def load_article_frequency_table(base_dir, pmid):
    """
    Load PMID/<pmid>/<pmid>.xlsx written by --articles.
    """
    file_path = Path(base_dir) / str(pmid) / f"{pmid}.xlsx"

    if not file_path.exists():
        raise FileNotFoundError(f"No table for PMID {pmid}")

    df = pd.read_excel(file_path, keep_default_na=False, na_values=[])

    df = df.sort_values(
        by="frequencia_tiab",
        ascending=False
    ).reset_index(drop=True)

    return df


# =====================================================
# Helpers
# =====================================================

def top_words(df, n=20):
    """
    First n rows (table is already sorted by TI+AB count).
    """
    return df.head(n)


def filter_words(df, min_freq=1):
    """
    Rows with TI+AB count >= min_freq.
    """
    return df[df["frequencia_tiab"] >= min_freq]


# =====================================================
# Summary
# =====================================================

def frequency_summary(df):
    """
    Distinct words and summed occurrences in TI, AB and TI+AB.
    """
    return {
        "total_palavras": len(df),
        "soma_tiab": int(df["frequencia_tiab"].sum()),
        "soma_ti": int(df["frequencia_ti"].sum()),
        "soma_ab": int(df["frequencia_ab"].sum())
    }

