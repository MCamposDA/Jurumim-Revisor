"""
Jurumim Revisor - term frequency analysis of PubMed (MEDLINE) records.

Modes:
  default           word frequency table (TI, AB, TI+AB, articles)
  -st / -so         merge synonyms into a standard term
  --ws              literal search for words, phrases, hyphenated terms
  --articles        one folder per PMID with its own frequency table
  --viewer          open the results in the Streamlit viewer
  --pubmed          download a query from NCBI in MEDLINE format
  --db              databases searched by --pubmed (pubmed, wos, scopus, all), merged without duplicates
  --merge           merge PubMed, Web of Science and Scopus export files without duplicates
  --screen          keep only the records marked include (or --keep ...) in the PRISMA table

Run with -h for the full syntax.
"""
import argparse
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path

import nltk
import pandas as pd
from nltk.tokenize import word_tokenize

# =====================================================
# NLTK resources
# =====================================================
NLTK_BASE = {
    'punkt': 'tokenizers/punkt',
    'punkt_tab': 'tokenizers/punkt_tab',  # required by word_tokenize on NLTK >= 3.8.2
    'stopwords': 'corpora/stopwords',
}
NLTK_LEMMA = {
    'wordnet': 'corpora/wordnet',
    'omw-1.4': 'corpora/omw-1.4',
}


def ensure_nltk(resources):
    """Download only the NLTK resources that are missing."""
    for name, path in resources.items():
        try:
            nltk.data.find(path)
        except LookupError:
            nltk.download(name, quiet=True)


ensure_nltk(NLTK_BASE)
from nltk.corpus import stopwords  # noqa: E402  (needs the corpus downloaded above)

stop_words = set(stopwords.words('english'))

# Set by --lemma. None means no lemmatization.
lemmatizer = None

# Words WordNet would turn into something wrong: proper nouns, Latin,
# acronyms, and verbs it reads as plural nouns (serves -> serf, doses -> dos).
# Built from the lemmas that changed in real Leishmania/Nyssomyia corpora.
LEMMA_EXCEPTIONS = {
    'aedes', 'anopheles', 'chagas', 'culex', 'data', 'diptera', 'glossina',
    'leishmania', 'leishmaniasis', 'lutzomyia', 'nyssomyia', 'phlebotomus',
    'trypanosoma', 'minas', 'gerais', 'pylori', 'acari', 'latu', 'lato',
    'aids', 'doses', 'discuss', 'serves', 'proves', 'delves', 'motives',
    'capita', 'syringes', 'stamina', 'reis', 'lens', 'less', 'mars', 'media',
    'series', 'species', 'status', 'various', 'thus', 'bias', 'analysis',
    'diagnosis', 'basis', 'sinus', 'virus', 'corpus', 'focus', 'nucleus', 'fungus',
}


# =====================================================
# Normalization
# =====================================================
def normalizar_sandfly(texto):
    """
    Merge the spelling variants 'sand fly', 'sand flies', 'sand-fly',
    'sand-flies' and 'sandflies' into 'sandfly'.

    Deliberate choice: the tool was built for Lutzomyia/Nyssomyia literature,
    where these variants refer to the same thing.
    """
    texto = re.sub(r'\bsand[\s-]+fl(?:y|ies)\b', 'sandfly', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\bsandflies\b', 'sandfly', texto, flags=re.IGNORECASE)
    return texto


def normalizar_hifens(texto):
    """
    Unicode hyphens (U+2010-2012, U+2212) become '-'; en and em dashes become spaces.
    Without this, 'case\u2012control' and 'case-control' would be counted differently,
    and differently again depending on the NLTK version.
    """
    texto = re.sub('[\u2010\u2011\u2012\u2212]', '-', texto)
    return re.sub('[\u2013\u2014]', ' ', texto)


def normalizar(texto):
    return normalizar_sandfly(normalizar_hifens(texto))


def lematizar(palavra):
    """
    Noun lemma of a lowercase word. Words of up to 3 letters (mostly acronyms:
    lps, ros, dcs) and LEMMA_EXCEPTIONS are returned unchanged.
    """
    if lemmatizer is None or len(palavra) <= 3 or palavra in LEMMA_EXCEPTIONS:
        return palavra
    return lemmatizer.lemmatize(palavra)


# =====================================================
# MEDLINE parsing
# =====================================================
def extrair_artigos_completo(texto):
    """
    Parse every MEDLINE tag of every record.

    Returns one dict per article; repeated tags (FAU, AD...) are joined with spaces.
    TI and AB go through normalizar (hyphens and sandfly variants).
    """
    artigos = []
    for artigo in re.split(r'\n(?=PMID-)', texto):
        if not artigo.strip():
            continue
        campos = defaultdict(str)
        chave = None
        for linha in artigo.strip().split('\n'):
            linha = linha.rstrip('\r')
            if len(linha) > 5 and linha[4] == '-':
                chave = linha[:4].strip()
                campos[chave] += linha[6:].strip() + ' '
            elif linha.startswith('      ') and chave:
                campos[chave] += linha.strip() + ' '
        campos['TI'] = normalizar(campos.get('TI', '').strip())
        campos['AB'] = normalizar(campos.get('AB', '').strip())
        artigos.append(campos)
    return artigos


def extrair_artigos(texto):
    """Return a list of (title, abstract) pairs, one per record."""
    artigos = []
    for artigo in re.split(r'\n(?=PMID-)', texto):
        if not artigo.strip():
            continue
        bloco_ti, bloco_ab, buffer, tipo = [], [], '', None
        for linha in artigo.strip().split('\n'):
            linha = linha.rstrip('\r')
            if linha.startswith('TI  -') or linha.startswith('AB  -'):
                if tipo and buffer:
                    (bloco_ti if tipo == 'TI' else bloco_ab).append(buffer.strip())
                tipo = linha[:2]
                buffer = linha[6:].strip()
            elif linha.startswith('      ') and tipo:
                buffer += ' ' + linha.strip()
            else:
                if tipo and buffer:
                    (bloco_ti if tipo == 'TI' else bloco_ab).append(buffer.strip())
                buffer, tipo = '', None
        if tipo and buffer:
            (bloco_ti if tipo == 'TI' else bloco_ab).append(buffer.strip())
        artigos.append((normalizar(' '.join(bloco_ti)),
                        normalizar(' '.join(bloco_ab))))
    return artigos


# =====================================================
# Tokenization and counting
# =====================================================
def tokenizar_e_filtrar(texto):
    """
    Lowercase, tokenize, keep alphabetic tokens that are not stopwords.
    Tokens with digits or hyphens (covid-19, t-cell) are dropped here; use --ws for them.
    Slashes and single quotes are replaced by spaces first, so "rural/wild" and
    'rural' give the same tokens on every NLTK version.
    """
    tokens = word_tokenize(re.sub(r"[/'\u2018\u2019]", ' ', texto.lower()), language='english')
    return [lematizar(p) for p in tokens if p.isalpha() and p not in stop_words]


def contar_por_artigo(artigos):
    """
    Count tokens over all articles.

    Returns (cont_tiab, cont_ti, cont_ab, artigos_por_palavra), where
    artigos_por_palavra maps each word to the set of article indices containing it.
    """
    cont_ti, cont_ab, cont_tiab = Counter(), Counter(), Counter()
    artigos_por_palavra = defaultdict(set)
    for i, (ti, ab) in enumerate(artigos):
        tokens_ti = tokenizar_e_filtrar(ti)
        tokens_ab = tokenizar_e_filtrar(ab)
        cont_ti.update(tokens_ti)
        cont_ab.update(tokens_ab)
        cont_tiab.update(tokens_ti + tokens_ab)
        for palavra in set(tokens_ti + tokens_ab):
            artigos_por_palavra[palavra].add(i)
    return cont_tiab, cont_ti, cont_ab, artigos_por_palavra


# Column names of the Excel outputs
COLUNAS = ['word', 'tiab_frequency', 'ti_frequency', 'ab_frequency', 'articles']
COLUNAS_WS = ['term', 'tiab_frequency', 'ti_frequency', 'ab_frequency', 'articles']
COLUNAS_ARTIGO = ['word', 'tiab_frequency', 'ti_frequency', 'ab_frequency']


def tabela_frequencia(artigos):
    """Frequency table for all words, sorted by TI+AB count. Also returns the article index."""
    cont_tiab, cont_ti, cont_ab, artigos_por_palavra = contar_por_artigo(artigos)
    dados = [
        [p, f, cont_ti.get(p, 0), cont_ab.get(p, 0), len(artigos_por_palavra[p])]
        for p, f in cont_tiab.most_common()
    ]
    return pd.DataFrame(dados, columns=COLUNAS), artigos_por_palavra


# =====================================================
# Grouping (-st / -so)
# =====================================================
class GroupAction(argparse.Action):
    """Store -st and -so in one ordered list so each synonym stays tied to its term."""

    def __call__(self, parser, namespace, values, option_string=None):
        itens = getattr(namespace, self.dest) or []
        itens.append((option_string, values))
        setattr(namespace, self.dest, itens)


def agrupar_termos(itens):
    """
    Turn [('-st', 'virus'), ('-so', 'viral'), ...] into {'virus': ['viral', ...]}.
    Raises ValueError for a -so that comes before any -st.
    """
    grupos = {}
    atual = None
    for flag, termo in itens or []:
        termo = termo.lower().strip()
        if flag == '-st':
            atual = termo
            grupos.setdefault(atual, [])
        else:
            if atual is None:
                raise ValueError(f"-so '{termo}' has no -st before it.")
            grupos[atual].append(termo)
    return grupos


def aplicar_grupos(df, grupos, artigos_por_palavra):
    """
    Merge each group into one row named after the standard term.
    Frequencies are summed; 'articles' is the number of distinct articles containing
    any term of the group (set union), so an article is never counted twice.
    """
    for chave, sinonimos in grupos.items():
        relacionados = list(dict.fromkeys(lematizar(normalizar(t)) for t in [chave] + sinonimos))
        subset = df[df['word'].isin(relacionados)]
        if subset.empty:
            print(f"Warning: no occurrence of group '{chave}'.")
            continue
        uniao = set().union(*(artigos_por_palavra.get(t, set()) for t in relacionados))
        linha = [chave,
                 int(subset['tiab_frequency'].sum()),
                 int(subset['ti_frequency'].sum()),
                 int(subset['ab_frequency'].sum()),
                 len(uniao)]
        df = df[~df['word'].isin(relacionados)]
        df = pd.concat([df, pd.DataFrame([linha], columns=COLUNAS)])
    return df.sort_values(by='tiab_frequency', ascending=False).reset_index(drop=True)


# =====================================================
# Word search (--ws)
# =====================================================
def compilar_termo(termo):
    """
    Regex for a literal term: case-insensitive, any whitespace between words,
    and not glued to letters, digits or hyphens on either side
    ('virus' does not match inside 'viruses' or 'virus-like').
    """
    termo = normalizar(termo.lower().strip())
    partes = [re.escape(p) for p in termo.split()]
    return re.compile(r'(?<![\w-])' + r'\s+'.join(partes) + r'(?![\w-])')


def contar_termos_ws(artigos, termos_por_rotulo):
    """
    Count every occurrence of each label's terms in the raw text (no stopword
    removal, no tokenization). For a group, counts are summed and
    'articles' counts articles containing at least one of its terms.
    """
    textos = [(ti.lower(), ab.lower()) for ti, ab in artigos]
    resultados = []
    for rotulo, termos in termos_por_rotulo.items():
        padroes = {}
        for t in termos:
            p = compilar_termo(t)
            padroes[p.pattern] = p  # drops terms that become identical after normalization
        freq_ti = freq_ab = n_artigos = 0
        for ti, ab in textos:
            c_ti = sum(len(p.findall(ti)) for p in padroes.values())
            c_ab = sum(len(p.findall(ab)) for p in padroes.values())
            freq_ti += c_ti
            freq_ab += c_ab
            if c_ti + c_ab:
                n_artigos += 1
        resultados.append([rotulo, freq_ti + freq_ab, freq_ti, freq_ab, n_artigos])
    return pd.DataFrame(resultados, columns=COLUNAS_WS)


# =====================================================
# Custom stopwords
# =====================================================
def carregar_stopwords(itens):
    """
    Each item is either a file (words separated by spaces, commas or new lines)
    or a word. The path keeps its case; only the words are lowercased.
    """
    extra = set()
    for item in itens or []:
        p = Path(item)
        if p.is_file():
            try:
                for w in re.split(r'[,\s]+', p.read_text(encoding='utf-8')):
                    if w:
                        extra.add(w.lower())
            except (OSError, UnicodeDecodeError) as e:
                print(f"Warning: could not read stopwords from {item}: {e}")
        else:
            if p.suffix in ('.txt', '.csv'):
                print(f"Warning: '{item}' looks like a file but was not found; used as a word.")
            extra.add(item.lower())
    return extra


# =====================================================
# PubMed download
# =====================================================
ESEARCH_MAX = 9999   # ESearch cannot return more UIDs than this for one query
EFETCH_BATCH = 500


def _entrez_call(func, tentativas=3, **kwargs):
    """Call an Entrez function with retries; returns the open handle's content."""
    from Bio import Entrez
    for n in range(1, tentativas + 1):
        try:
            handle = func(**kwargs)
            try:
                if func is Entrez.efetch:
                    return handle.read()
                return Entrez.read(handle)
            finally:
                handle.close()
        except Exception as e:
            if n == tentativas:
                raise
            print(f"  NCBI error ({e}); retrying in {3 * n}s...")
            time.sleep(3 * n)


def _contar(query):
    from Bio import Entrez
    rec = _entrez_call(Entrez.esearch, db='pubmed', term=query, retmax=0)
    return int(rec['Count'])


def _ids(query, n):
    from Bio import Entrez
    rec = _entrez_call(Entrez.esearch, db='pubmed', term=query, retmax=min(n, ESEARCH_MAX))
    return rec['IdList']


def _coletar_ids(query, inicio, fim, ids):
    """Split the query by publication date until each slice fits in one ESearch."""
    q = f'({query}) AND ("{inicio:%Y/%m/%d}"[dp] : "{fim:%Y/%m/%d}"[dp])'
    n = _contar(q)
    if n == 0:
        return
    if n <= ESEARCH_MAX or inicio == fim:
        if n > ESEARCH_MAX:
            print(f"Warning: {n} records on {inicio}; only {ESEARCH_MAX} can be retrieved.")
        ids.update(_ids(q, n))
        return
    meio = inicio + (fim - inicio) // 2
    _coletar_ids(query, inicio, meio, ids)
    _coletar_ids(query, meio + timedelta(days=1), fim, ids)


def nome_arquivo_query(query):
    """File-system safe name for a query."""
    nome = re.sub(r'[^\w.-]+', '_', query).strip('_.')[:80]
    return f"Pubmed_{nome or 'query'}.txt"


def baixar_pubmed(query, email, apikey=None):
    """
    Download every record of a PubMed query in MEDLINE format.

    Queries above 9,999 records are split by publication date, since ESearch
    does not return more than that per search.
    Returns the saved filename, or None when nothing was found.
    """
    from Bio import Entrez
    Entrez.email = email
    Entrez.tool = 'JurumimRevisor'
    if apikey:
        Entrez.api_key = apikey

    print(f"Searching PubMed for: {query}")
    total = _contar(query)
    print(f"Records found: {total}")
    if total == 0:
        return None

    if total <= ESEARCH_MAX:
        ids = set(_ids(query, total))
    else:
        print("More than 9,999 records: splitting the search by publication date...")
        ids = set()
        _coletar_ids(query, date(1700, 1, 1), date(date.today().year + 1, 12, 31), ids)

    ids = sorted(ids, key=int, reverse=True)
    partes = []
    for i in range(0, len(ids), EFETCH_BATCH):
        lote = ids[i:i + EFETCH_BATCH]
        print(f"  Fetching {i + 1}-{i + len(lote)} of {len(ids)}")
        partes.append(_entrez_call(Entrez.efetch, db='pubmed', id=','.join(lote),
                                   rettype='medline', retmode='text').strip('\n'))
    data = '\n\n'.join(partes) + '\n'

    n_baixados = len(re.findall(r'^PMID- ', data, flags=re.M))
    if n_baixados != total:
        print(f"Warning: PubMed reports {total} records, {n_baixados} were downloaded.")

    fname = nome_arquivo_query(query)
    Path(fname).write_text(data, encoding='utf-8')
    print(f"Saved: {fname} ({n_baixados} records)")
    return fname


# =====================================================
# Several databases (--db, --merge)
# =====================================================
def carregar_arquivo(caminho):
    """Registro list of a PubMed (MEDLINE), Web of Science or Scopus export file."""
    from databases.medline import ler_medline
    from databases.scopus import detectar_formato_scopus, ler_arquivo_scopus
    from databases.wos import detectar_formato, ler_arquivo_wos, ler_texto
    texto = ler_texto(caminho)
    formato = detectar_formato(texto)
    if formato == 'medline':
        return ler_medline(texto)
    if formato in ('wos_txt', 'wos_tab'):
        return ler_arquivo_wos(caminho)
    if detectar_formato_scopus(texto):
        return ler_arquivo_scopus(texto)
    raise ValueError(f"{caminho}: unknown format (expected PubMed MEDLINE, a Web of Science "
                     f"plain text / tab-delimited export, or a Scopus CSV / RIS export)")


def preencher_resumos(registros, args):
    """--fill-abstracts: missing abstracts from PubMed / Crossref / Semantic Scholar / OpenAlex."""
    from databases.resumos import preencher
    if not args.email and any(r.pmid for r in registros):
        from databases.credenciais import completar
        completar(args, ['pubmed'])
    return preencher(registros, email=args.email, s2_chave=args.s2_apikey,
                     openalex_chave=args.openalex_apikey)


def separar_sem_resumo(registros, manter_todos=False):
    """(records without abstract, records with abstract); with manter_todos nothing is set apart."""
    from databases.resumos import sem_resumo
    if manter_todos:
        return [], list(registros)
    sem_ab = [r for r in registros if sem_resumo(r)]
    fora = {id(r) for r in sem_ab}
    return sem_ab, [r for r in registros if id(r) not in fora]


def gravar_sem_resumo(sem_ab, destino):
    """
    Write <destino>_no_abstract.txt. When there is nothing to write, an old file
    of a previous run is removed, so --screen never reads stale records.
    """
    from databases.medline import escrever_medline
    arquivo = Path(destino).with_name(Path(destino).stem + '_no_abstract.txt')
    if sem_ab:
        escrever_medline(sem_ab, arquivo)
    elif arquivo.is_file():
        arquivo.unlink()
        print(f"Removed {arquivo} of a previous run (every record now has an abstract).")
    return arquivo


def combinar(grupos, destino, args=None):
    """
    Merge [(label, records), ...] into one MEDLINE file without duplicates.
    Groups are given in priority order (PubMed first). Also writes
    <destino>_prisma.xlsx: PRISMA counts, one row per article with its IDs,
    and every duplicate removed and why. With --fill-abstracts, the unique
    records without abstract are filled before writing.

    Records still without abstract are not analysed: they go to
    <destino>_no_abstract.txt instead of <destino>, and are pre-marked in the
    PRISMA table as excluded, reason "No abstract available"
    (--keep-no-abstract keeps them in <destino>, counted by title).
    """
    from databases.dedup import remover_duplicatas
    from databases.medline import escrever_medline, garantir_ids_unicos
    from databases.prisma import escrever_prisma

    todos = [r for _, regs in grupos for r in regs]
    # Duplicates first (a kept record without abstract takes its duplicate's),
    # then --fill-abstracts for the unique records still without one
    mantidos, relatorio = remover_duplicatas(todos)
    garantir_ids_unicos(mantidos)
    herdados = sum(any(t == 'ABS' and v.endswith('(duplicate record)') for t, v in r.extras)
                   for r in mantidos)
    if herdados:
        print(f"Abstracts taken from a duplicate record: {herdados}")
    resumos = preencher_resumos(mantidos, args) if args is not None and args.fill_abstracts else None

    manter_todos = args is not None and getattr(args, 'keep_no_abstract', False)
    sem_ab, com_ab = separar_sem_resumo(mantidos, manter_todos)
    escrever_medline(com_ab, destino)
    arquivo_sem_ab = gravar_sem_resumo(sem_ab, destino)

    rel = Path(destino).with_name(Path(destino).stem + '_prisma.xlsx')
    escrever_prisma(grupos, mantidos, relatorio, rel, resumos, sem_resumo=sem_ab)

    print("\nRecords identified:")
    for rotulo, regs in grupos:
        print(f"  {rotulo}: {len(regs)}")
    print(f"  total: {len(todos)}")
    motivos = Counter(d['matched_on'] for d in relatorio)
    detalhe = ', '.join(f"{m}: {n}" for m, n in motivos.most_common())
    print(f"Duplicates removed: {len(relatorio)}" + (f" ({detalhe})" if detalhe else ''))
    fontes = Counter('; '.join(r.fontes) for r in mantidos)
    print(f"Unique records: {len(mantidos)} (" +
          ', '.join(f"{f}: {n}" for f, n in fontes.most_common()) + ')')
    if sem_ab:
        dica = '' if resumos is not None else '; --fill-abstracts can recover many of them'
        print(f"Without abstract, left out of the analysis: {len(sem_ab)} -> {arquivo_sem_ab} "
              f"(marked excluded in the PRISMA table{dica})")
        if not com_ab:
            print(f"Warning: no record has an abstract, so {destino} is empty; "
                  f"use --fill-abstracts or --keep-no-abstract.")
    print(f"Saved: {destino} ({len(com_ab)} records with abstract)\nPRISMA table: {rel}")
    return destino


def baixar_varias(dbs, query, args):
    """
    --db: download from each database, keep each raw file, then merge (also with
    a single database: duplicates inside it, PRISMA table, records without abstract).
    A database that fails is reported and the others still run.
    """
    from databases.medline import escrever_medline, ler_medline

    def pubmed():
        fname = baixar_pubmed(query, args.email, args.apikey)
        return ler_medline(Path(fname).read_text(encoding='utf-8')) if fname else []

    def wos():
        from databases.wos import baixar_wos
        return baixar_wos(args.wos_query or query, args.wos_apikey, api=args.wos_api)

    def scopus():
        from databases.scopus import baixar_scopus
        return baixar_scopus(args.scopus_query or query, args.scopus_apikey,
                             insttoken=args.scopus_insttoken, view=args.scopus_view,
                             acesso=args.scopus_key)

    etapas = [('pubmed', 'PubMed', pubmed, None), ('wos', 'Web of Science', wos, 'WOS_'),
              ('scopus', 'Scopus', scopus, 'Scopus_')]
    grupos, falhas = [], []
    for db, rotulo, baixar, prefixo in etapas:
        if db not in dbs:
            continue
        try:
            regs = baixar()
        except Exception as e:
            print(f"{rotulo} failed: {e}\n  Going on with the other databases.")
            falhas.append(rotulo)
            continue
        if regs and prefixo:
            nome = nome_arquivo_query(query).replace('Pubmed_', prefixo, 1)
            escrever_medline(regs, nome)
            print(f"Saved: {nome} ({len(regs)} records, MEDLINE format)")
        grupos.append((rotulo, regs))

    if not any(regs for _, regs in grupos):
        print("Nothing found in any database." if not falhas else
              f"No records: {', '.join(falhas)} failed.")
        return 1
    combinar(grupos, nome_arquivo_query(query).replace('Pubmed_', 'Merged_', 1), args)
    if falhas:
        print(f"\nWarning: merged WITHOUT {', '.join(falhas)} (failed above). Fix the problem and "
              f"run again, or add that database later with --merge.")
        return 1
    return 0


def modo_preencher(entrada, destino, args):
    """
    --fill-abstracts FILE: fill the abstracts of a file on disk into a new file.
    As in a merge, records still without abstract go to <destino>_no_abstract.txt
    (unless --keep-no-abstract). For a PRISMA table, use --merge FILE --fill-abstracts.
    """
    from databases.medline import escrever_medline, garantir_ids_unicos
    registros = garantir_ids_unicos(carregar_arquivo(entrada))
    preencher_resumos(registros, args)
    sem_ab, com_ab = separar_sem_resumo(registros, args.keep_no_abstract)
    escrever_medline(com_ab, destino)
    arquivo_sem_ab = gravar_sem_resumo(sem_ab, destino)
    print(f"Saved: {destino} ({len(com_ab)} records with abstract; the input file is not changed)")
    if sem_ab:
        print(f"Without abstract, left out of the analysis: {len(sem_ab)} -> {arquivo_sem_ab}")


def modo_merge(arquivos, destino, args=None):
    """
    --merge: combine PubMed, WoS and Scopus files already on disk.
    Files are merged in a fixed priority, PubMed > WoS > Scopus (then by file name),
    whatever the order they are given in, so the same files always give the same result.
    """
    carregados = [(Path(a).name, carregar_arquivo(a)) for a in arquivos]
    nomes = {Path(a).resolve() for a in arquivos}
    for a, (nome, regs) in zip(arquivos, carregados):
        if len({f for r in regs for f in r.fontes}) > 1 or any(len(r.fontes) > 1 for r in regs):
            irmao = Path(a).with_name(Path(a).stem + '_no_abstract.txt')
            falta = irmao.is_file() and irmao.resolve() not in nomes
            print(f"Note: {nome} is already a merged file: its records are counted as identified "
                  f"from it. For the PRISMA counts per database, merge the raw files of each "
                  f"database instead." + (f" Its records without abstract are in {irmao.name}, "
                                          f"which was not given." if falta else ''))
    ordem = {'PubMed': 0, 'WOS': 1, 'Scopus': 2}
    carregados.sort(key=lambda g: (ordem.get(g[1][0].fonte, 3) if g[1] else 4, g[0]))
    combinar(carregados, destino, args)


DECISOES = ('include', 'exclude', 'maybe')


def modo_screen(entrada, planilha, manter, destino):
    """
    --screen: copy to `destino` only the records whose screening_decision in the
    PRISMA table is one of `manter`. Records are matched by record_id, the PMID-
    line of the merged file. Records without a decision are left out.
    The merged file itself is not changed.

    Records without abstract live in <entrada>_no_abstract.txt, pre-marked
    exclude in the table; one changed to include there is brought back.
    """
    try:
        df = pd.read_excel(planilha, sheet_name='records', dtype=str, keep_default_na=False)
    except ValueError:
        df = pd.DataFrame()
    if 'record_id' not in df.columns or 'screening_decision' not in df.columns:
        raise ValueError(f"{planilha} has no 'records' sheet with record_id and screening_decision; "
                         f"use the _prisma.xlsx written by --merge")
    # Excel can turn numeric IDs into 42788600.0
    ids = df['record_id'].str.strip().str.replace(r'\.0$', '', regex=True)
    decisoes = df['screening_decision'].str.strip().str.lower()
    decisao_por_id = dict(zip(ids, decisoes))

    texto = Path(entrada).read_text(encoding='utf-8')
    blocos = [b for b in re.split(r'\n(?=PMID-)', texto) if b.strip()]
    sem_ab_arq = Path(entrada).with_name(Path(entrada).stem + '_no_abstract.txt')
    blocos_sem_ab = []
    if sem_ab_arq.is_file():
        blocos_sem_ab = [b for b in re.split(r'\n(?=PMID-)', sem_ab_arq.read_text(encoding='utf-8'))
                         if b.strip()]
    sem_ab_inicio = len(blocos)
    blocos += blocos_sem_ab
    id_do_bloco = [re.match(r'PMID- *(\S+)', b).group(1) for b in blocos]

    repetidos = ids[ids.duplicated()].unique()
    if len(repetidos):
        print(f"Warning: {len(repetidos)} record_id repeated in the table; the last row counts "
              f"(e.g. {', '.join(repetidos[:3])}).")
    fora_do_arquivo = sorted(set(ids) - set(id_do_bloco))
    if fora_do_arquivo:
        print(f"Warning: {len(fora_do_arquivo)} record_id of the table are not in {entrada} "
              f"(e.g. {', '.join(fora_do_arquivo[:3])}): is it the table of another merge?")
    invalidas = sorted({d for d in decisoes if d and d not in DECISOES})
    if invalidas:
        print(f"Warning: unknown decisions treated as not screened: {', '.join(invalidas)}")

    contagem = Counter()
    mantidos = []
    sem_ab_mantidos = 0
    for i, (bloco, id_) in enumerate(zip(blocos, id_do_bloco)):
        d = decisao_por_id.get(id_, '')
        d = d if d in DECISOES else 'not screened'
        contagem[d] += 1
        if d in manter:
            mantidos.append(bloco.rstrip('\n'))
            sem_ab_mantidos += i >= sem_ab_inicio

    extra = f" + {len(blocos_sem_ab)} without abstract in {sem_ab_arq.name}" if blocos_sem_ab else ''
    print(f"Records in {entrada}: {sem_ab_inicio}{extra}")
    if sem_ab_mantidos:
        print(f"Note: {sem_ab_mantidos} record(s) without abstract were marked {' / '.join(manter)} "
              f"in the table; they are kept and counted by title only.")
    for d in DECISOES + ('not screened',):
        print(f"  {d}: {contagem[d]}")
    if contagem['not screened']:
        print(f"Warning: {contagem['not screened']} records have no decision and were left out.")
    if not mantidos:
        print(f"No record marked {' / '.join(manter)}; nothing written.")
        return 1
    Path(destino).write_text('\n\n'.join(mantidos) + '\n', encoding='utf-8')
    print(f"Kept ({' + '.join(manter)}): {len(mantidos)}\nSaved: {destino}")
    return 0


def rodar_modo(entrada, saida, ws, grupos):
    if ws is not None:
        modo_ws(entrada, saida, ws, grupos)
    elif grupos:
        modo_grupos(entrada, saida, grupos)
    else:
        modo_padrao(entrada, saida)


COLUNAS_POR_BASE = [('PubMed', 'articles_pubmed'), ('WOS', 'articles_wos'),
                    ('Scopus', 'articles_scopus')]


def colunas_por_base(entrada, saida, ws, grupos):
    """
    For a merged file (records with DB lines), add one articles_<database> column
    per database present in the file, next to 'articles' in the table just written.

    Each column comes from running the same mode on only that database's records,
    so it is counted exactly like 'articles'. An article found in several databases
    counts in each of their columns, so the columns can add up to more than 'articles'.
    """
    import contextlib
    import io
    import tempfile

    texto = Path(entrada).read_text(encoding='utf-8')
    if not re.search(r'^DB  - ', texto, flags=re.M):
        return
    blocos = [b for b in re.split(r'\n(?=PMID-)', texto) if b.strip()]

    def bases(bloco):
        m = re.search(r'^DB  - (.*)$', bloco, flags=re.M)
        return {f.strip() for f in m.group(1).split(';')} if m else set()

    presentes = set().union(*(bases(b) for b in blocos))
    colunas = [(b, c) for b, c in COLUNAS_POR_BASE if b in presentes]
    if not colunas:
        return

    df = pd.read_excel(saida, keep_default_na=False, na_values=[])
    chave = df.columns[0]
    pos = list(df.columns).index('articles') + 1
    with tempfile.TemporaryDirectory() as tmp:
        for base, coluna in colunas:
            sub = [b for b in blocos if base in bases(b)]
            contagem = {}
            if sub:
                arq, out = Path(tmp) / f'{base}.txt', Path(tmp) / f'{base}.xlsx'
                arq.write_text('\n'.join(b.rstrip('\n') + '\n' for b in sub), encoding='utf-8')
                with contextlib.redirect_stdout(io.StringIO()):
                    rodar_modo(arq, out, ws, grupos)
                sdf = pd.read_excel(out, keep_default_na=False, na_values=[])
                contagem = dict(zip(sdf[chave].astype(str), sdf['articles']))
            df.insert(pos, coluna, [int(contagem.get(str(k), 0)) for k in df[chave]])
            pos += 1
    df.to_excel(saida, index=False)
    print(f"Added {', '.join(c for _, c in colunas)} (merged input).")


# =====================================================
# Modes
# =====================================================
def modo_articles(entrada):
    """One folder per PMID with <PMID>.xlsx (word counts) and <PMID>_info.txt (all tags)."""
    artigos = extrair_artigos_completo(Path(entrada).read_text(encoding='utf-8'))
    base_dir = Path('PMID')
    base_dir.mkdir(exist_ok=True)

    for n, artigo in enumerate(artigos, 1):
        pmid = artigo.get('PMID', '').strip() or f'NO_PMID_{n}'
        pasta = base_dir / pmid
        pasta.mkdir(exist_ok=True)

        tokens_ti = tokenizar_e_filtrar(artigo.get('TI', ''))
        tokens_ab = tokenizar_e_filtrar(artigo.get('AB', ''))
        cont_ti, cont_ab = Counter(tokens_ti), Counter(tokens_ab)
        dados = [[p, f, cont_ti.get(p, 0), cont_ab.get(p, 0)]
                 for p, f in Counter(tokens_ti + tokens_ab).most_common()]
        df = pd.DataFrame(dados, columns=COLUNAS_ARTIGO)
        df.to_excel(pasta / f"{pmid}.xlsx", index=False)

        with open(pasta / f"{pmid}_info.txt", 'w', encoding='utf-8') as f:
            for chave, valor in artigo.items():
                f.write(f"{chave}: {valor.strip()}\n")

    print(f"{len(artigos)} article folders written to: {base_dir.resolve()}")


def modo_ws(entrada, saida, termos_soltos, grupos):
    """--ws: loose terms get one row each; each -st group gets one merged row."""
    termos_por_rotulo = {t.lower(): [t] for t in termos_soltos}
    for chave, sinonimos in grupos.items():
        termos_por_rotulo[chave] = [chave] + sinonimos
    if not termos_por_rotulo:
        raise ValueError("--ws needs at least one term or an -st group.")
    artigos = extrair_artigos(Path(entrada).read_text(encoding='utf-8'))
    df = contar_termos_ws(artigos, termos_por_rotulo)
    df.to_excel(saida, index=False)
    print(f"Word search written to: {saida}")


def modo_grupos(entrada, saida, grupos):
    """-st/-so without --ws: full table with each group merged into one row."""
    for termo in [t for ch, s in grupos.items() for t in [ch] + s]:
        if not termo.isalpha():
            print(f"Warning: '{termo}' is not a single alphabetic word and never appears "
                  f"in the token table; use --ws for phrases or hyphenated terms.")
    artigos = extrair_artigos(Path(entrada).read_text(encoding='utf-8'))
    df, artigos_por_palavra = tabela_frequencia(artigos)
    df = aplicar_grupos(df, grupos, artigos_por_palavra)
    df.to_excel(saida, index=False)
    print(f"Grouped frequency table written to: {saida}")


def modo_padrao(entrada, saida):
    artigos = extrair_artigos(Path(entrada).read_text(encoding='utf-8'))
    df, _ = tabela_frequencia(artigos)
    df.to_excel(saida, index=False)
    print(f"Frequency table written to: {saida} ({len(artigos)} articles, {len(df)} words)")


# =====================================================
# Viewer (--viewer)
# =====================================================
VIEWER_APP = Path(__file__).resolve().parent / 'viewer' / 'JR_Phleb.view.py'
PMID_DIR = Path('PMID')


def pmid_dir_completo(entrada):
    """True when ./PMID already has a table for every PMID of the input file."""
    texto = Path(entrada).read_text(encoding='utf-8', errors='ignore')
    pmids = re.findall(r'^PMID- *(\S+)', texto, flags=re.M)
    return bool(pmids) and all((PMID_DIR / p / f"{p}.xlsx").is_file() for p in pmids)


def abrir_viewer(entrada, tabela):
    """Start the Streamlit viewer on the input file, the general table and ./PMID."""
    import importlib.util
    import os
    import subprocess

    if not VIEWER_APP.is_file():
        print(f"Viewer app not found: {VIEWER_APP}")
        return 1
    if importlib.util.find_spec('streamlit') is None:
        print("Streamlit is not installed in this environment: pip install -r requirements.txt")
        return 1

    env = dict(os.environ,
               VIEWER_PUBMED_FILE=str(Path(entrada).resolve()),
               VIEWER_GENERAL_XLSX=str(Path(tabela).resolve()),
               VIEWER_PMID_DIR=str(PMID_DIR.resolve()))
    print("Starting viewer (Ctrl+C to stop)...", flush=True)
    try:
        # Same interpreter as this script, so this environment's Streamlit is used
        return subprocess.run([sys.executable, '-m', 'streamlit', 'run', str(VIEWER_APP)],
                              env=env).returncode
    except KeyboardInterrupt:
        return 0


# =====================================================
# CLI
# =====================================================
EXEMPLOS = """examples:
  python3 Jurumim_Revisor.py input.txt output.xlsx
  python3 Jurumim_Revisor.py input.txt output.xlsx --lemma
  python3 Jurumim_Revisor.py input.txt output.xlsx -sw study results MyStopwords.txt
  python3 Jurumim_Revisor.py input.txt output.xlsx -st virus -so viral -so virome
  python3 Jurumim_Revisor.py input.txt output.xlsx --ws "science park" covid-19 t-cell
  python3 Jurumim_Revisor.py input.txt output.xlsx --ws -st "sandfly" -so "phlebotomine"
  python3 Jurumim_Revisor.py input.txt --articles
  python3 Jurumim_Revisor.py input.txt output.xlsx --viewer
  python3 Jurumim_Revisor.py -p -q "Nyssomyia" --email you@example.org
  python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db all --email you@example.org --wos-apikey KEY --scopus-apikey KEY
  python3 Jurumim_Revisor.py --merge Pubmed_Nyssomyia.txt savedrecs.txt --merge-out Nyssomyia_all.txt
  python3 Jurumim_Revisor.py --screen Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx --keep include maybe

Input and output files go first; flags that take several values
(--ws, -sw) consume every word after them until the next flag.
"""


def criar_parser():
    parser = argparse.ArgumentParser(
        prog='Jurumim_Revisor.py',
        description='Term frequency analysis of PubMed (MEDLINE format) files.',
        epilog=EXEMPLOS,
        formatter_class=argparse.RawDescriptionHelpFormatter,
        allow_abbrev=False,
    )
    parser.add_argument('entrada', nargs='?', metavar='input.txt', help='PubMed file in MEDLINE format')
    parser.add_argument('saida', nargs='?', metavar='output.xlsx', help='Excel output (not used by --articles)')
    parser.add_argument('-sw', '--stopword', nargs='+', metavar='WORD_OR_FILE',
                        help='extra stopwords: words and/or text files')
    parser.add_argument('--ws', '--wordsearch', dest='ws', nargs='*', metavar='TERM',
                        help='literal search for words, phrases or hyphenated terms')
    parser.add_argument('-st', dest='grupos', action=GroupAction, metavar='TERM',
                        help='standard term of a group')
    parser.add_argument('-so', dest='grupos', action=GroupAction, metavar='SYNONYM',
                        help='synonym added to the last -st')
    parser.add_argument('-art', '--articles', action='store_true',
                        help='write one folder per PMID into ./PMID')
    parser.add_argument('-v', '--viewer', action='store_true',
                        help='after writing output.xlsx, build ./PMID if needed and open the viewer')
    parser.add_argument('--lemma', action='store_true',
                        help='count noun lemmas (viruses -> virus); does not affect --ws')
    parser.add_argument('-p', '--pubmed', action='store_true', help='download a PubMed query')
    parser.add_argument('-q', '--query', help='PubMed query (with --pubmed)')
    parser.add_argument('--email', help='e-mail sent to NCBI (required with --pubmed)')
    parser.add_argument('--apikey', help='NCBI API key (optional, raises the request rate)')
    parser.add_argument('--db', nargs='+', choices=['pubmed', 'wos', 'scopus', 'all'], default=['pubmed'],
                        help='databases searched by --pubmed (default: pubmed); several are merged '
                             'without duplicates')
    parser.add_argument('--wos-apikey', default=os.environ.get('WOS_API_KEY'),
                        help='Clarivate API key for --db wos (or set WOS_API_KEY)')
    parser.add_argument('--wos-api', choices=['expanded', 'starter'], default=None,
                        help='expanded: full records with abstracts (subscription); '
                             'starter: free key, titles only (default: expanded, or the type saved with the key)')
    parser.add_argument('--wos-query', help='query in WoS syntax, e.g. TS=(Nyssomyia) '
                                            '(default: -q wrapped as TS=(...))')
    parser.add_argument('--scopus-apikey', default=os.environ.get('SCOPUS_API_KEY'),
                        help='Elsevier API key for --db scopus (or set SCOPUS_API_KEY)')
    parser.add_argument('--scopus-insttoken', default=os.environ.get('SCOPUS_INSTTOKEN'),
                        help='Elsevier institutional token, for COMPLETE view outside the '
                             'institution network (or set SCOPUS_INSTTOKEN)')
    parser.add_argument('--scopus-key', choices=['institutional', 'personal'], default=None,
                        help='institutional: full records with abstracts (institution network or '
                             'token); personal: free key without institution, titles only, '
                             'searches above 5,000 split by year (default: institutional, or the '
                             'type saved with the key)')
    parser.add_argument('--scopus-view', choices=['complete', 'standard'], default='complete',
                        help='complete: abstracts and all authors (institutional access); '
                             'standard: titles and first author only (default: complete)')
    parser.add_argument('--scopus-query', help='query in Scopus syntax, e.g. TITLE-ABS-KEY(Nyssomyia) '
                                               '(default: -q wrapped as TITLE-ABS-KEY(...))')
    parser.add_argument('--merge', nargs='+', metavar='FILE',
                        help='merge PubMed, Web of Science and Scopus export files without duplicates')
    parser.add_argument('--merge-out', default='Merged_records.txt', metavar='OUT.txt',
                        help='output of --merge (default: Merged_records.txt)')
    parser.add_argument('--screen', nargs=2, metavar=('MERGED.txt', 'PRISMA.xlsx'),
                        help='keep only the records screened in the PRISMA table (see --keep)')
    parser.add_argument('--keep', nargs='+', choices=list(DECISOES), default=['include'],
                        help='screening decisions kept by --screen (default: include)')
    parser.add_argument('--screen-out', metavar='OUT.txt',
                        help='output of --screen (default: <MERGED>_screened.txt)')
    parser.add_argument('--fill-abstracts', nargs='?', const=True, default=None, metavar='FILE',
                        help='fill missing abstracts from PubMed (PMID), Crossref, Semantic Scholar '
                             'and OpenAlex (DOI), English only. Alone with a FILE: writes '
                             '<FILE>_filled.txt; with --merge or -p --db: fills the merged file')
    parser.add_argument('--outdir', metavar='DIR',
                        help='write every output of this run into DIR (created if needed), e.g. '
                             'one folder per topic: --outdir results/Nyssomyia. Input files are '
                             'looked up where you run the command, then in DIR')
    parser.add_argument('--keep-no-abstract', action='store_true',
                        help='with --merge / -p --db: keep records without abstract in the merged '
                             'file (counted by title) instead of <OUT>_no_abstract.txt, and do not '
                             'pre-mark them as excluded in the PRISMA table')
    parser.add_argument('--fill-out', metavar='OUT.txt',
                        help='output of --fill-abstracts FILE (default: <FILE>_filled.txt)')
    parser.add_argument('--s2-apikey', default=os.environ.get('S2_API_KEY'),
                        help='Semantic Scholar API key, optional (or set S2_API_KEY)')
    parser.add_argument('--openalex-apikey', default=os.environ.get('OPENALEX_API_KEY'),
                        help='OpenAlex API key, optional (or set OPENALEX_API_KEY)')
    parser.add_argument('--no-prompt', action='store_true',
                        help='never ask for a missing e-mail / API key in the terminal; '
                             'give them with flags or environment variables')
    parser.add_argument('--show-keys', action='store_true',
                        help='show the saved e-mail / API keys (masked) and exit')
    parser.add_argument('--forget-keys', action='store_true',
                        help='delete the saved e-mail / API keys and exit')
    return parser


def preparar_outdir(args):
    """
    --outdir: every file written by this run goes into that folder (created if
    needed), e.g. one folder per review topic. Input files are looked up first
    where the command is run, then inside the folder, so the steps of one topic
    can be chained: -p ... --outdir results/X, then --merge Pubmed_X.txt ... --outdir results/X.
    """
    base = Path.cwd()
    pasta = Path(args.outdir).expanduser()
    pasta = pasta if pasta.is_absolute() else base / pasta
    pasta.mkdir(parents=True, exist_ok=True)

    def achar(caminho):
        c = Path(caminho).expanduser()
        if c.is_absolute():
            return str(c)
        for raiz in (base, pasta):
            if (raiz / c).exists():
                return str((raiz / c).resolve())
        return str(base / c)

    if args.entrada:
        args.entrada = achar(args.entrada)
    if args.merge:
        args.merge = [achar(a) for a in args.merge]
    if args.screen:
        args.screen = [achar(a) for a in args.screen]
    if isinstance(args.fill_abstracts, str):
        args.fill_abstracts = achar(args.fill_abstracts)
    if args.stopword:
        args.stopword = [achar(s) if (base / s).is_file() or (pasta / s).is_file() else s
                         for s in args.stopword]
    os.chdir(pasta)
    print(f"Output folder: {pasta}")


def main(argv=None):
    global stop_words, lemmatizer
    parser = criar_parser()
    args = parser.parse_intermixed_args(argv)

    if args.show_keys or args.forget_keys:
        from databases import credenciais
        credenciais.mostrar() if args.show_keys else credenciais.esquecer()
        return 0

    arquivo_para_preencher = args.fill_abstracts if isinstance(args.fill_abstracts, str) else None
    if arquivo_para_preencher and (args.merge or args.pubmed):
        parser.error('with --merge or -p, use --fill-abstracts without a file name '
                     '(the merged file is filled)')
    if args.fill_abstracts is True and not (args.merge or args.pubmed):
        parser.error('--fill-abstracts needs a file (--fill-abstracts FILE.txt), '
                     'or --merge / -p to fill the merged file')
    if args.outdir:
        preparar_outdir(args)

    if args.merge:
        for a in args.merge:
            if not Path(a).is_file():
                parser.error(f"file not found: {a}")
        try:
            modo_merge(args.merge, args.merge_out, args)
        except ValueError as e:
            parser.error(str(e))
        return 0

    if arquivo_para_preencher:
        if not Path(arquivo_para_preencher).is_file():
            parser.error(f"file not found: {arquivo_para_preencher}")
        nome = Path(arquivo_para_preencher).stem + '_filled.txt'
        destino = args.fill_out or (nome if args.outdir else
                                    str(Path(arquivo_para_preencher).with_name(nome)))
        try:
            modo_preencher(arquivo_para_preencher, destino, args)
        except ValueError as e:
            parser.error(str(e))
        return 0

    if args.screen:
        entrada, planilha = args.screen
        for a in args.screen:
            if not Path(a).is_file():
                parser.error(f"file not found: {a}")
        nome = Path(entrada).stem + '_screened.txt'
        destino = args.screen_out or (nome if args.outdir else str(Path(entrada).with_name(nome)))
        try:
            return modo_screen(entrada, planilha, list(dict.fromkeys(args.keep)), destino)
        except ValueError as e:
            parser.error(str(e))

    dbs = ['pubmed', 'wos', 'scopus'] if 'all' in args.db else list(dict.fromkeys(args.db))
    # The multi-database pipeline (PRISMA table, records without abstract set apart) is used
    # when several databases were asked for, even if the user then skips some, and with
    # --fill-abstracts; PubMed alone without it keeps the original download.
    pipeline = dbs != ['pubmed'] or bool(args.fill_abstracts)
    if args.pubmed:
        # Missing e-mail / keys: saved file, then one question at a time (see databases/credenciais.py)
        proprias = {'pubmed': None, 'wos': args.wos_query, 'scopus': args.scopus_query}
        if not args.query and not all(proprias[db] for db in dbs):
            parser.error('--pubmed needs --query' if dbs == ['pubmed'] else
                         '--pubmed needs --query (or --wos-query / --scopus-query for those databases)')
        from databases.credenciais import completar
        dbs = completar(args, dbs)
        args.wos_api = args.wos_api or 'expanded'
        args.scopus_key = args.scopus_key or 'institutional'
        if not dbs:
            print("No database left to search.")
            return 1
    if args.pubmed and pipeline:
        proprias = {'pubmed': None, 'wos': args.wos_query, 'scopus': args.scopus_query}
        if not args.query and not all(proprias[db] for db in dbs):
            parser.error('--pubmed needs --query (or --wos-query / --scopus-query for those databases)')
        if 'pubmed' in dbs and not args.email:
            parser.error('--db pubmed needs --email (or run in a terminal without --no-prompt to be asked)')
        if 'wos' in dbs and not args.wos_apikey:
            parser.error('--db wos needs --wos-apikey, the WOS_API_KEY variable, or a terminal without --no-prompt to be asked')
        if 'scopus' in dbs and not args.scopus_apikey:
            parser.error('--db scopus needs --scopus-apikey, the SCOPUS_API_KEY variable, or a terminal without --no-prompt to be asked')
        try:
            return baixar_varias(dbs, args.query or args.wos_query or args.scopus_query, args)
        except Exception as e:
            print(f"Download error: {e}")
            return 1

    if args.pubmed:
        if not args.query or not args.email:
            parser.error('--pubmed needs --query and --email')
        try:
            baixar_pubmed(args.query, args.email, args.apikey)
        except Exception as e:
            print(f"PubMed error: {e}")
            return 1
        return 0

    if not args.entrada:
        engolidos = [t for t in (args.stopword or []) + (args.ws or []) if t.lower().endswith('.xlsx')]
        dica = f" ('{engolidos[0]}' was read by -sw/--ws: put input and output first)" if engolidos else ''
        parser.error(f'missing input file{dica}')
    if not Path(args.entrada).is_file():
        parser.error(f"input file not found: {args.entrada}")
    if not re.search(r'^PMID- ', Path(args.entrada).read_text(encoding='utf-8', errors='ignore'), flags=re.M):
        parser.error(f"{args.entrada} has no 'PMID- ' lines; export it from PubMed in "
                     f"PubMed/MEDLINE format (Save > Format: PubMed)")

    stop_words |= carregar_stopwords(args.stopword)

    if args.lemma:
        ensure_nltk(NLTK_LEMMA)
        from nltk.stem import WordNetLemmatizer
        lemmatizer = WordNetLemmatizer()

    try:
        grupos = agrupar_termos(args.grupos)
    except ValueError as e:
        parser.error(str(e))

    if args.articles and not args.viewer:
        modo_articles(args.entrada)
        return 0

    if not args.saida or not args.saida.lower().endswith('.xlsx'):
        dica = ' (--viewer needs the general table as output)' if args.viewer else ''
        if args.ws and any(t.lower().endswith('.xlsx') for t in args.ws):
            dica = ' (it was read as a search term: put input and output before --ws)'
        parser.error(f'output file must end with .xlsx{dica}')

    try:
        if args.ws is not None:
            modo_ws(args.entrada, args.saida, args.ws, grupos)
        elif grupos:
            modo_grupos(args.entrada, args.saida, grupos)
        else:
            modo_padrao(args.entrada, args.saida)
        colunas_por_base(args.entrada, args.saida, args.ws, grupos)
    except ValueError as e:
        parser.error(str(e))

    if args.viewer:
        if args.articles or not pmid_dir_completo(args.entrada):
            modo_articles(args.entrada)
        else:
            print(f"Reusing {PMID_DIR}/ (delete it to rebuild the per-article tables).")
        return abrir_viewer(args.entrada, args.saida)
    return 0


if __name__ == '__main__':
    sys.exit(main())
