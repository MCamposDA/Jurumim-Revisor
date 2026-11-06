"""
Duplicate removal across databases.

Records are compared in order of priority; the first one seen is kept, so
PubMed records (richer: MeSH, affiliations for every author) win over WoS.
A later record is a duplicate when it shares, in this order:

  1. PMID (WoS and Scopus records carry the PMID when the article is also in
     MEDLINE), or the WoS UT / Scopus EID (overlapping exports of one database)
  2. DOI (case and "https://doi.org/" prefixes ignored)
  3. title + year: same title once reduced to letters and digits, and
     publication years at most 1 apart (epub vs print year). Titles shorter
     than MIN_TITULO characters ("Editorial", "Erratum") are never matched this way.

Records with different PMIDs are never merged, and a title match is refused
when both records have DOIs and they differ (see _conflito).

The kept record is not rewritten: it only gains DB (all sources it was found in)
and, from a WoS duplicate, UT and TC (times cited); from a Scopus duplicate,
EID and TCSC (Scopus cited by).

When the kept record has no abstract and the duplicate has one in English, the
kept record takes it (AB, with ABS = "<database> (duplicate record)"), e.g. a
WoS Starter record kept over the Scopus CSV record of the same article.
"""
from .medline import _campos, chave_titulo

MIN_TITULO = 30
NOME_BASE = {'PubMed': 'PubMed', 'WOS': 'Web of Science', 'Scopus': 'Scopus'}


def _resumo(r):
    c = _campos(r.to_medline())
    return ' '.join(c.get('AB', [])).strip(), (c.get('ABS') or [None])[0]


def _conflito(a, b, por_titulo=False):
    """
    True when two records cannot be the same article: different PMIDs (a PMID
    belongs to one article) or, for a title match, different DOIs. Generic
    titles are often shared by different articles of the same year.
    """
    if a.pmid and b.pmid and a.pmid != b.pmid:
        return True
    return por_titulo and bool(a.doi and b.doi and a.doi != b.doi)


def remover_duplicatas(registros):
    """Return (kept records, report rows). Input order sets the priority."""
    por_pmid, por_doi, por_titulo, por_ut, por_eid = {}, {}, {}, {}, {}
    mantidos, relatorio = [], []

    for r in registros:
        alvo, motivo = None, None
        tkey = chave_titulo(r.titulo)
        for chave, indice, nome in ((r.pmid, por_pmid, 'PMID'), (r.ut, por_ut, 'WoS UT'),
                                    (r.eid, por_eid, 'Scopus EID'), (r.doi, por_doi, 'DOI')):
            if chave and chave in indice and not _conflito(r, indice[chave]):
                alvo, motivo = indice[chave], nome
                break
        if alvo is None and len(tkey) >= MIN_TITULO:
            for outro in por_titulo.get(tkey, []):
                anos_ok = r.ano is None or outro.ano is None or abs(r.ano - outro.ano) <= 1
                if anos_ok and not _conflito(r, outro, por_titulo=True):
                    alvo, motivo = outro, 'title + year'
                    break

        if alvo is None:
            mantidos.append(r)
            alvo = r
        else:
            _mesclar(alvo, r)
            relatorio.append({
                'removed_source': r.fonte, 'removed_id': r.id,
                'kept_source': alvo.fonte, 'kept_id': alvo.id,
                'matched_on': motivo, 'title': r.titulo,
                'removed_doi': r.doi or '', 'kept_doi': alvo.doi or '',
            })

        # Index every key of the record (and of its duplicates) under the kept one
        for chave, indice in ((r.pmid, por_pmid), (r.ut, por_ut), (r.eid, por_eid), (r.doi, por_doi)):
            if chave:
                indice.setdefault(chave, alvo)
        if len(tkey) >= MIN_TITULO:
            lista = por_titulo.setdefault(tkey, [])
            if alvo not in lista:
                lista.append(alvo)

    return mantidos, relatorio


def _mesclar(alvo, dup):
    for f in dup.fontes:
        if f not in alvo.fontes:
            alvo.fontes.append(f)
    if dup.ut and not alvo.ut:
        alvo.ut = dup.ut
        alvo.extras.append(('UT', dup.ut))
    if dup.tc and not alvo.tc:
        alvo.tc = dup.tc
        alvo.extras.append(('TC', dup.tc))
    if dup.eid and not alvo.eid:
        alvo.eid = dup.eid
        alvo.extras.append(('EID', dup.eid))
    if dup.tc_scopus and not alvo.tc_scopus:
        alvo.tc_scopus = dup.tc_scopus
        alvo.extras.append(('TCSC', dup.tc_scopus))
    if not _resumo(alvo)[0]:
        texto, origem = _resumo(dup)
        if texto:
            from .resumos import limpar, so_ingles
            texto = so_ingles(limpar(texto))
            if texto:
                # A duplicate whose abstract was itself filled keeps that source
                origem = origem or f"{NOME_BASE.get(dup.fonte, dup.fonte)} (duplicate record)"
                alvo.extras += [('AB', texto), ('ABS', origem)]
