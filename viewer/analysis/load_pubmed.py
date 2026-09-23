import re
from collections import defaultdict
from pathlib import Path

# =====================================================
# MEDLINE / PubMed parser
# =====================================================

def parse_pubmed_file(pubmed_txt):
    """
    Read a MEDLINE file and return {PMID: article dict}.

    Besides the MEDLINE tags, each article gets '_AD_BY_AUTHOR': a list aligned
    with 'FAU' holding the AD lines written right after each author.
    """
    pubmed_txt = Path(pubmed_txt)
    if not pubmed_txt.exists():
        raise FileNotFoundError(f"File not found: {pubmed_txt}")

    texto = pubmed_txt.read_text(encoding="utf-8", errors="ignore")
    artigos = {}

    for bloco in re.split(r"\n(?=PMID-)", texto):
        bloco = bloco.strip()
        if not bloco:
            continue

        campos = defaultdict(list)
        chave_atual = None
        # One list of affiliations per author, in FAU order (and AU order for
        # old records that have no FAU).
        ad_fau, ad_au = [], []
        ad_alvo = None

        for linha in bloco.splitlines():
            linha = linha.rstrip("\r")
            # New tag: "FAU - Name"
            if len(linha) >= 6 and linha[4:6] == "- ":
                chave_atual = linha[:4].strip()
                valor = linha[6:].strip()
                campos[chave_atual].append(valor)

                if chave_atual == "FAU":
                    ad_fau.append([])
                elif chave_atual == "AU":
                    ad_au.append([])
                elif chave_atual == "AD":
                    ad_alvo = []
                    if ad_fau:
                        ad_fau[-1].append(valor)
                        ad_alvo.append(ad_fau[-1])
                    if ad_au:
                        ad_au[-1].append(valor)
                        ad_alvo.append(ad_au[-1])

            # Continuation line (6 spaces)
            elif linha.startswith("      ") and chave_atual:
                resto = linha.strip()
                campos[chave_atual][-1] += " " + resto
                if chave_atual == "AD" and ad_alvo:
                    for lista in ad_alvo:
                        lista[-1] += " " + resto

        pmid = campos.get("PMID", [None])[0]
        if not pmid:
            continue

        artigo = normalize_article_fields(campos)
        artigo["_AD_BY_AUTHOR"] = ad_fau if "FAU" in campos else ad_au
        artigos[pmid] = artigo

    return artigos


# =====================================================
# Field normalization
# =====================================================

def normalize_article_fields(campos):
    """
    - TI and AB become single strings.
    - FAU becomes a list of authors (falls back to AU when FAU is absent).
    - Other tags: string when they occur once, list otherwise.
    """
    artigo = {}

    for campo, valores in campos.items():
        if campo in {"TI", "AB"}:
            artigo[campo] = " ".join(valores).strip()
        elif campo == "FAU":
            artigo["FAU"] = normalize_authors(valores)
        else:
            artigo[campo] = valores if len(valores) > 1 else valores[0]

    if "FAU" not in artigo and "AU" in campos:
        artigo["FAU"] = normalize_authors(campos["AU"])

    return artigo


# =====================================================
# Authors
# =====================================================

def normalize_authors(fau_list):
    """
    One author per FAU line, kept as written ("Silva, Maria Aparecida").
    No truncation and no de-duplication: two co-authors with the same name are
    still two authors, and the list stays aligned with the affiliations.
    """
    return [re.sub(r"\s+", " ", a).strip() for a in fau_list if a.strip()]


# =====================================================
# Entry point used by the viewer
# =====================================================

def load_pubmed_articles(pubmed_txt):
    return parse_pubmed_file(pubmed_txt)


if __name__ == "__main__":
    import sys
    artigos = parse_pubmed_file(sys.argv[1])
    print(f"Articles loaded: {len(artigos)}")
    primeiro = next(iter(artigos.values()))
    for k, v in primeiro.items():
        print(f"{k}: {v}")
