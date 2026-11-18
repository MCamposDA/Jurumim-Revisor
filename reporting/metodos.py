"""
Methods text of a review (methods_en.txt, and methods_pt.txt with --report-pt).

Built from the search log, the PRISMA table and the options of the analysis.
What the tool cannot know (the query and date of a file exported from a
website, the full-text stage) is written in [square brackets], to be completed.
"""
import re
from datetime import date

DB_NOME = {'en': {'Web of Science': 'Web of Science Core Collection'},
           'pt': {'Web of Science': 'Web of Science Core Collection'}}
FONTE_PT = {'PubMed': 'PubMed', 'Crossref': 'Crossref', 'Semantic Scholar': 'Semantic Scholar',
            'OpenAlex': 'OpenAlex'}
CHAVE_PT = {'title + year': 'título + ano'}
MESES_PT = ['janeiro', 'fevereiro', 'março', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro',
            'outubro', 'novembro', 'dezembro']


def _data(iso, lingua):
    if not iso:
        return '[date of the search]' if lingua == 'en' else '[data da busca]'
    d = date.fromisoformat(iso)
    if lingua == 'en':
        return f"{d.day} {d.strftime('%B')} {d.year}"
    return f"{d.day} de {MESES_PT[d.month - 1]} de {d.year}"


def _lista(itens, lingua):
    itens = list(itens)
    if len(itens) <= 1:
        return ''.join(itens)
    e = ' and ' if lingua == 'en' else ' e '
    return ', '.join(itens[:-1]) + e + itens[-1]


def _fontes(log, lingua):
    """One sentence per source: API searches with their query, exported files with placeholders."""
    frases = []
    for o in log.get('sources', []):
        nome = DB_NOME[lingua].get(o['database'], o['database'])
        if o['origin'] == 'api':
            chave = f" ({o['key']})" if o.get('key') else ''
            if lingua == 'en':
                frases.append(f"{nome} was searched through its API{chave} on {_data(o['date'], 'en')} with "
                              f"the query {o['query']} ({o['records']:,} records).")
            else:
                frases.append(f"A base {nome} foi consultada pela sua API{chave} em {_data(o['date'], 'pt')} "
                              f"com a busca {o['query']} ({o['records']:,} registros).")
        elif o['origin'] == 'file':
            if lingua == 'en':
                frases.append(f"Records from {nome} were obtained on [date] with the query [query] "
                              f"({o['records']:,} records, file {o['file']}).")
            else:
                frases.append(f"Os registros da base {nome} foram obtidos em [data] com a busca [busca] "
                              f"({o['records']:,} registros, arquivo {o['file']}).")
        else:
            if lingua == 'en':
                frases.append(f"The previously merged file {o['file']} ({nome}; {o['records']:,} records) "
                              f"was added.")
            else:
                frases.append(f"Foi incluído o arquivo já mesclado {o['file']} ({nome}; {o['records']:,} registros).")
    return ' '.join(frases)


def texto(lingua, log, contagens, analise):
    """
    lingua: 'en' or 'pt'. log: search log (or None). contagens: PRISMA counts
    (or None). analise: dict with n_articles, lemma, extra_stopwords, mode,
    terms, network (nodes, links, min, max_nodes, keep_generic).
    """
    en = lingua == 'en'
    p = []

    # 1. Search and merge
    if log:
        bases = _lista((DB_NOME[lingua].get(o['database'], o['database']) for o in log['sources']), lingua)
        if en:
            p.append(f"Records were identified in {bases}. " + _fontes(log, 'en'))
        else:
            p.append(f"Os registros foram identificados nas bases {bases}. " + _fontes(log, 'pt'))
        chaves = log['duplicates']['by_key']
        detalhe = _lista(((f"{n:,} by {k}" if en else f"{n:,} por {CHAVE_PT.get(k, k)}")
                          for k, n in chaves.items()), lingua) if chaves else ''
        if en:
            p.append(f"All records were converted to MEDLINE format and merged with Jurumim Revisor. Duplicates "
                     f"were identified, in this order, by PMID, Web of Science UT, Scopus EID, DOI, and title "
                     f"reduced to letters and digits combined with a publication year at most one year apart; "
                     f"records with different PMIDs, or with different DOIs in a title match, were never merged. "
                     f"The record from the database of highest priority was kept (PubMed > Web of Science > "
                     f"Scopus). Of {log['identified']:,} records identified, {log['duplicates']['total']:,} "
                     f"duplicates were removed" + (f" ({detalhe})" if detalhe else '') +
                     f", leaving {log['unique']:,} unique records.")
        else:
            p.append(f"Todos os registros foram convertidos para o formato MEDLINE e mesclados com o Jurumim "
                     f"Revisor. As duplicatas foram identificadas, nesta ordem, por PMID, UT do Web of Science, "
                     f"EID do Scopus, DOI e título reduzido a letras e dígitos combinado com ano de publicação "
                     f"com diferença de no máximo um ano; registros com PMIDs diferentes, ou com DOIs diferentes "
                     f"numa coincidência de título, nunca foram unidos. Manteve-se o registro da base de maior "
                     f"prioridade (PubMed > Web of Science > Scopus). Dos {log['identified']:,} registros "
                     f"identificados, {log['duplicates']['total']:,} duplicatas foram removidas" +
                     (f" ({detalhe})" if detalhe else '') + f", restando {log['unique']:,} registros únicos.")

        # 2. Abstracts
        r = log['abstracts']
        frases = []
        if r['taken_from_duplicates']:
            frases.append(f"{r['taken_from_duplicates']:,} records without an abstract received the abstract of "
                          f"one of their duplicates." if en else
                          f"{r['taken_from_duplicates']:,} registros sem resumo receberam o resumo de uma de suas "
                          f"duplicatas.")
        if r['fill_requested']:
            total = sum(r['filled'].values())
            fontes = _lista(((f"{n:,} from {s}" if en else f"{n:,} de {FONTE_PT.get(s, s)}")
                             for s, n in r['filled'].items()), lingua) or ('none' if en else 'nenhum')
            if en:
                frases.append(f"Missing abstracts were then searched, in this order, in PubMed (by PMID), Crossref, "
                              f"Semantic Scholar and OpenAlex (by DOI), keeping the first English abstract found; "
                              f"sentences in Portuguese, Spanish or French were removed. {total:,} abstracts were "
                              f"retrieved ({fontes}).")
            else:
                frases.append(f"Os resumos ausentes foram então buscados, nesta ordem, no PubMed (por PMID), "
                              f"Crossref, Semantic Scholar e OpenAlex (por DOI), mantendo o primeiro resumo em "
                              f"inglês encontrado; frases em português, espanhol ou francês foram removidas. "
                              f"{total:,} resumos foram recuperados ({fontes}).")
        if log['without_abstract'] and not log['kept_without_abstract']:
            frases.append(f"{log['without_abstract']:,} records still without an abstract were excluded from "
                          f"the analysis." if en else
                          f"{log['without_abstract']:,} registros ainda sem resumo foram excluídos da análise.")
        if frases:
            p.append(' '.join(frases))
    else:
        p.append("[Databases searched, queries and dates of the searches.]" if en else
                 "[Bases consultadas, buscas e datas das buscas.]")

    # 3. Screening
    if contagens:
        c = contagens
        if en:
            s = (f"Titles and abstracts of {c['triados']:,} records were screened; "
                 f"{c['sem_resumo'] + c['excluidos']:,} were excluded ({c['sem_resumo']:,} without an abstract) "
                 f"and {c['incluidos']:,} were included" + (f", with {c['talvez']:,} left as uncertain" if c['talvez']
                                                            else '') + ".")
            if c['pendentes']:
                s += f" {c['pendentes']:,} records had not been screened when this text was generated."
            s += (" Records sought for retrieval, assessed in full text and excluded with reasons: "
                  "[full-text stage].")
        else:
            s = (f"Os títulos e resumos de {c['triados']:,} registros foram triados; "
                 f"{c['sem_resumo'] + c['excluidos']:,} foram excluídos ({c['sem_resumo']:,} sem resumo) e "
                 f"{c['incluidos']:,} foram incluídos" + (f", com {c['talvez']:,} mantidos como incertos"
                                                          if c['talvez'] else '') + ".")
            if c['pendentes']:
                s += f" {c['pendentes']:,} registros ainda não haviam sido triados quando este texto foi gerado."
            s += (" Registros buscados para leitura, avaliados no texto completo e excluídos com motivos: "
                  "[etapa de texto completo].")
        if c.get('sugestoes_regras') or c.get('sugestoes_ia'):
            if en:
                s += (" Screening was supported by suggestions" +
                      (f" from predefined criteria ({c['sugestoes_regras']:,} records)" if c.get('sugestoes_regras') else '') +
                      (" and" if c.get('sugestoes_regras') and c.get('sugestoes_ia') else '') +
                      (f" from a language model ({c['sugestoes_ia']:,} records{', ' + c['modelo_ia'] if c.get('modelo_ia') else ''})"
                       if c.get('sugestoes_ia') else '') +
                      "; every decision was made by the reviewers.")
            else:
                s += (" A triagem contou com sugestões" +
                      (f" de critérios predefinidos ({c['sugestoes_regras']:,} registros)" if c.get('sugestoes_regras') else '') +
                      (" e" if c.get('sugestoes_regras') and c.get('sugestoes_ia') else '') +
                      (f" de um modelo de linguagem ({c['sugestoes_ia']:,} registros{', ' + c['modelo_ia'] if c.get('modelo_ia') else ''})"
                       if c.get('sugestoes_ia') else '') +
                      "; todas as decisões foram tomadas pelos revisores.")
        p.append(s)

    # 4. Text analysis
    a = analise
    if en:
        s = (f"Titles and abstracts of the {a['n_articles']:,} records analysed were lowercased and tokenised "
             f"with NLTK; English stopwords" + (f" and {a['extra_stopwords']:,} additional words" if a['extra_stopwords'] else '') +
             " were removed" + ("; words were reduced to their noun lemma (WordNet)" if a['lemma'] else '') + ".")
        if a.get('terms'):
            s += f" The terms analysed were {_lista(a['terms'], 'en')}."
        n = a.get('network')
        if n:
            s += (f" A word co-occurrence network was built from pairs of adjacent words: for each word, the word "
                  f"immediately before and after it was counted, and pairs including a stopword, a generic term of "
                  f"scientific writing or a non-word token were discarded. Pairs occurring at least {n['min']} times "
                  f"were kept ({n['nodes']:,} words, {n['links']:,} links), and communities were detected with the "
                  f"Louvain method.")
    else:
        s = (f"Os títulos e resumos dos {a['n_articles']:,} registros analisados foram convertidos para minúsculas "
             f"e tokenizados com o NLTK; foram removidas as stopwords do inglês" +
             (f" e {a['extra_stopwords']:,} palavras adicionais" if a['extra_stopwords'] else '') +
             ("; as palavras foram reduzidas ao lema de substantivo (WordNet)" if a['lemma'] else '') + ".")
        if a.get('terms'):
            s += f" Os termos analisados foram {_lista(a['terms'], 'pt')}."
        n = a.get('network')
        if n:
            s += (f" Uma rede de coocorrência de palavras foi construída a partir de pares de palavras adjacentes: "
                  f"para cada palavra, contou-se a palavra imediatamente anterior e a posterior, descartando os "
                  f"pares com stopwords, termos genéricos da escrita científica ou tokens que não são palavras. "
                  f"Mantiveram-se os pares com pelo menos {n['min']} coocorrências ({n['nodes']:,} palavras, "
                  f"{n['links']:,} ligações), e as comunidades foram detectadas pelo método de Louvain.")
    p.append(s)
    saida = '\n\n'.join(p) + '\n'
    # Portuguese thousands separator: 1,234 -> 1.234
    return saida if en else re.sub(r'(?<=\d),(?=\d{3}\b)', '.', saida)
