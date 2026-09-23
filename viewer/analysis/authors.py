from collections import defaultdict, Counter

# =====================================================
# Author index over all articles
# =====================================================

def build_author_index(articles):
    """
    Returns (author -> set of PMIDs, author -> Counter of positions).
    Positions: "primeiro" (first), "ultimo" (last), "meio" (middle).
    A single-author paper counts as first author only.
    """
    autor_para_pmids = defaultdict(set)
    autor_posicoes = defaultdict(lambda: Counter())

    for pmid, art in articles.items():
        autores = art.get("FAU", [])
        if not autores:
            continue

        for idx, autor in enumerate(autores):
            autor_para_pmids[autor].add(pmid)

            if idx == 0:
                autor_posicoes[autor]["primeiro"] += 1
            elif idx == len(autores) - 1:
                autor_posicoes[autor]["ultimo"] += 1
            else:
                autor_posicoes[autor]["meio"] += 1

    return autor_para_pmids, autor_posicoes


# =====================================================
# Author table
# =====================================================

def build_author_table(autor_para_pmids, autor_posicoes):
    """
    Rows for a DataFrame, sorted by number of articles:
    autor | n_artigos | primeiro_autor | ultimo_autor | meio_autor
    """
    tabela = []

    for autor, pmids in autor_para_pmids.items():
        pos = autor_posicoes.get(autor, {})
        tabela.append({
            "autor": autor,
            "n_artigos": len(pmids),
            "primeiro_autor": pos.get("primeiro", 0),
            "ultimo_autor": pos.get("ultimo", 0),
            "meio_autor": pos.get("meio", 0)
        })

    tabela.sort(key=lambda x: x["n_artigos"], reverse=True)
    return tabela


# =====================================================
# Authors of one article
# =====================================================

def get_article_author_summary(article):
    """
    Total, first and last author of one article.
    """
    autores = article.get("FAU", [])

    if not autores:
        return {
            "total_autores": 0,
            "primeiro_autor": None,
            "ultimo_autor": None,
            "autores": []
        }

    return {
        "total_autores": len(autores),
        "primeiro_autor": autores[0],
        "ultimo_autor": autores[-1],
        "autores": autores
    }

