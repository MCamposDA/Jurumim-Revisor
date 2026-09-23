import pandas as pd
from pathlib import Path

# Tables written by older versions used Portuguese column names
LEGACY_COLUMNS = {
    "palavra": "word",
    "termo": "term",
    "frequencia_tiab": "tiab_frequency",
    "frequencia_ti": "ti_frequency",
    "frequencia_ab": "ab_frequency",
    "art": "articles",
    "artigos_com_termo": "articles",
}

# =====================================================
# General table
# =====================================================

def load_global_frequency_table(path):
    """
    Load the general table written by Jurumim_Revisor.py, sorted by TI+AB count.
    keep_default_na=False keeps words such as "na" and "nan" as text.
    """
    df = pd.read_excel(path, keep_default_na=False, na_values=[])
    df = df.rename(columns=LEGACY_COLUMNS)

    df = df.sort_values(
        by="tiab_frequency",
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
    df = df.rename(columns=LEGACY_COLUMNS)

    df = df.sort_values(
        by="tiab_frequency",
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
    return df[df["tiab_frequency"] >= min_freq]


# =====================================================
# Summary
# =====================================================

def frequency_summary(df):
    """
    Distinct words and summed occurrences in TI, AB and TI+AB.
    """
    return {
        "total_palavras": len(df),
        "soma_tiab": int(df["tiab_frequency"].sum()),
        "soma_ti": int(df["ti_frequency"].sum()),
        "soma_ab": int(df["ab_frequency"].sum())
    }

