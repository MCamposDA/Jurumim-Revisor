import os
import sys
from pathlib import Path
import streamlit as st
import pandas as pd

# =====================================================
# Input files (set by Jurumim_Revisor.py --viewer)
# =====================================================

PUBMED_FILE = os.getenv("VIEWER_PUBMED_FILE")
GENERAL_XLSX = os.getenv("VIEWER_GENERAL_XLSX")
PMID_DIR = os.getenv("VIEWER_PMID_DIR")
COLUMN_TRANSLATION = {
    "word": "Word",
    "term": "Term",
    "ti_frequency": "Title Frequency",
    "ab_frequency": "Abstract Frequency",
    "tiab_frequency": "Title & Abstract Frequency",
    "articles": "Articles"
}

AUTHOR_COLUMN_TRANSLATION = {
    "autor": "Author",
    "n_artigos": "Number of articles",
    "primeiro_autor": "First author",
    "ultimo_autor": "Last author",
    "meio_autor": "Middle author"
}

LABEL_TRANSLATION = {
    "primeiro": "First author",
    "primeiro autor": "First author",
    "primeiro_autor": "First author",
    "ultimo": "Last author",
    "ultimo autor": "Last author",
    "ultimo_autor": "Last author"
}


if not PUBMED_FILE or not GENERAL_XLSX or not PMID_DIR:
    st.error("Viewer started without input files.")
    st.info("Start it with: python3 Jurumim_Revisor.py input.txt output.xlsx --viewer")
    st.stop()

PUBMED_FILE = Path(PUBMED_FILE)
GENERAL_XLSX = Path(GENERAL_XLSX)
PMID_DIR = Path(PMID_DIR)
APP_DIR = Path(__file__).parent
sys.path.insert(0, str(APP_DIR))  # so "analysis" imports work from any working directory
ASSETS_DIR = APP_DIR / "assets/"


# =====================================================
# Analysis modules
# =====================================================

from analysis.word_freq import (
    load_global_frequency_table,
    load_article_frequency_table,
    top_words,
    frequency_summary
)

from analysis.load_pubmed import load_pubmed_articles

from analysis.authors import (
    build_author_index,
    build_author_table,
    get_article_author_summary
)

from analysis.affiliations import (
    get_author_country,
    get_article_countries
)

# =====================================================
# Page setup
# =====================================================

st.set_page_config(
    page_title="Jurumim Revisor",
    layout="wide"
)

# =====================================================
# Header
# =====================================================

col1, col2, col3, col4, col5 = st.columns([4, 1, 1, 1, 2])

with col2:
    st.image(
        ASSETS_DIR / "jurumim_logo.jpg",
        width=700
    )

st.markdown(
    "<h2 style='text-align: center;'>Jurumim Revisor</h2>",
    unsafe_allow_html=True
)


st.markdown(
    "<p style='text-align: center; color: #4B5563;'>"
    "Auxiliary software for systematic analysis and literary review, created by ANDRADE, M C - Laboratory of Bioinformatics and Evolutionary Biology (LABBE); Brazil"
    "</p>",
    unsafe_allow_html=True
)

st.divider()

# =====================================================
# Data loading
# =====================================================

@st.cache_data(show_spinner=True)
def load_all_data():
    articles = load_pubmed_articles(PUBMED_FILE)

    df_global = load_global_frequency_table(GENERAL_XLSX)
    autor_para_pmids, autor_posicoes = build_author_index(articles)
    # Fixed columns so an input without authors still yields a usable table
    df_autores = pd.DataFrame(
        build_author_table(autor_para_pmids, autor_posicoes),
        columns=list(AUTHOR_COLUMN_TRANSLATION)
    )

    df_autores = df_autores.rename(columns=AUTHOR_COLUMN_TRANSLATION)

    return articles, df_global, df_autores


articles, df_global, df_autores = load_all_data()

# =====================================================
# Tabs
# =====================================================

tabs = st.tabs([
    "📊 General Frequency",
    "👥 Authors (General)",
    "📄 Articles"
])

# =====================================================
# Tab 1: overall word frequency
# =====================================================

with tabs[0]:
    st.header("📊 Words General Frequency")

    col1, col2 = st.columns(2)

    with col1:
        resumo = frequency_summary(df_global)
        st.metric("Words", resumo["total_palavras"])
        st.metric("Title & Abstract occurrence", resumo["soma_tiab"])

    with col2:
        st.metric("Title occurrence", resumo["soma_ti"])
        st.metric("Abstract occurrence", resumo["soma_ab"])

    st.subheader("Complete chart")
    st.dataframe(df_global.rename(columns=COLUMN_TRANSLATION))

    st.subheader("Top words")
    n_top = st.slider("Number of words", 10, 100, 20)
    st.dataframe(top_words(df_global, n_top).rename(columns=COLUMN_TRANSLATION))

# =====================================================
# Tab 2: authors
# =====================================================

with tabs[1]:
    st.header("👥 Authors — General View")

    st.dataframe(df_autores)

    st.subheader("Filter by minimum number of articles")
    max_artigos = int(df_autores["Number of articles"].max()) if not df_autores.empty else 0

    # st.slider fails when min == max, so it is only shown when there is a range
    if max_artigos > 1:
        min_artigos = st.slider("Articles", 1, max_artigos, 1)
        st.dataframe(df_autores[df_autores["Number of articles"] >= min_artigos])
    elif df_autores.empty:
        st.info("No authors found in the PubMed file.")
    else:
        st.info("Every author has a single article; nothing to filter.")

# =====================================================
# Tab 3: single article
# =====================================================

with tabs[2]:
    st.header("📄 Single article view")

    pmid_to_title = {
        pmid: art.get("TI", f"PMID {pmid}")
        for pmid, art in articles.items()
    }

    # Searchable by title
    selected_pmid = st.selectbox(
        "🔍 Search by article title",
        options=list(pmid_to_title.keys()),
        format_func=lambda x: pmid_to_title[x]
    )

    article = articles.get(selected_pmid)

    if article:
        st.subheader(article.get("TI", "Untitled"))
        st.markdown(f"**PMID:** {selected_pmid}")

        autor_resumo = get_article_author_summary(article)

        st.markdown(f"**Total of authors:** {autor_resumo['total_autores']}")
        st.markdown(f"**First author:** {autor_resumo['primeiro_autor']}")
        st.markdown(f"**Last author:** {autor_resumo['ultimo_autor']}")

        st.subheader("👥 Article’s authors")

        autores_artigo = autor_resumo["autores"]

        if autores_artigo:
            df_autores_artigo = df_autores[
                df_autores["Author"].isin(autores_artigo)
            ].sort_values("Number of articles", ascending=False)

            st.dataframe(df_autores_artigo)
        else:
            st.info("No available author for this article.")

        # Country of each author comes only from that author's own AD lines
        st.subheader("🌍 Residence (first and last authors)")

        paises = get_article_countries(article)

        if paises:
            for pos, pais in paises.items():
                label = LABEL_TRANSLATION.get(pos.lower(), pos.capitalize())
                st.markdown(f"**{label}:** {pais}")
        else:
            st.info("Not available.")

        if "IS" in article and article["IS"]:
            st.subheader("🔗 Identifiers")
            st.write(article["IS"])

        st.divider()

        # Table written by Jurumim_Revisor.py --articles
        st.subheader("📊 Article’s words frequency")

        try:
            df_artigo = load_article_frequency_table(PMID_DIR, selected_pmid)
            df_artigo = df_artigo.rename(columns=COLUMN_TRANSLATION)
            st.dataframe(df_artigo)
        except Exception:
            st.warning("No chart available for this article.")

st.divider()

st.markdown("<br>", unsafe_allow_html=True)

col1, col2, col3, col4 = st.columns([6, 1, 1, 1])

with col3:
    st.image(
        ASSETS_DIR / "jurumim_logo.jpg",
        width=120
    )

with col4:
    st.image(
        ASSETS_DIR / "labbe_logo.png",
        width=160
    )