"""
Jurumim Revisor - term frequency analysis of PubMed (MEDLINE) records.

Modes:
  default           word frequency table (TI, AB, TI+AB, articles)
  -st / -so         merge synonyms into a standard term
  --ws              literal search for words, phrases, hyphenated terms
  --articles        one folder per PMID with its own frequency table
  --pubmed          download a query from NCBI in MEDLINE format

Run with -h for the full syntax.
"""
import argparse
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


COLUNAS = ['palavra', 'frequencia_tiab', 'frequencia_ti', 'frequencia_ab', 'art']
COLUNAS_WS = ['termo', 'frequencia_tiab', 'frequencia_ti', 'frequencia_ab', 'artigos_com_termo']


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
    Frequencies are summed; 'art' is the number of distinct articles containing
    any term of the group (set union), so an article is never counted twice.
    """
    for chave, sinonimos in grupos.items():
        relacionados = list(dict.fromkeys(lematizar(normalizar(t)) for t in [chave] + sinonimos))
        subset = df[df['palavra'].isin(relacionados)]
        if subset.empty:
            print(f"Warning: no occurrence of group '{chave}'.")
            continue
        uniao = set().union(*(artigos_por_palavra.get(t, set()) for t in relacionados))
        linha = [chave,
                 int(subset['frequencia_tiab'].sum()),
                 int(subset['frequencia_ti'].sum()),
                 int(subset['frequencia_ab'].sum()),
                 len(uniao)]
        df = df[~df['palavra'].isin(relacionados)]
        df = pd.concat([df, pd.DataFrame([linha], columns=COLUNAS)])
    return df.sort_values(by='frequencia_tiab', ascending=False).reset_index(drop=True)


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
    'artigos_com_termo' counts articles containing at least one of its terms.
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
        df = pd.DataFrame(dados, columns=['palavra', 'frequencia_tiab', 'frequencia_ti', 'frequencia_ab'])
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
  python3 Jurumim_Revisor.py -p -q "Nyssomyia" --email you@example.org

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
    parser.add_argument('--lemma', action='store_true',
                        help='count noun lemmas (viruses -> virus); does not affect --ws')
    parser.add_argument('-p', '--pubmed', action='store_true', help='download a PubMed query')
    parser.add_argument('-q', '--query', help='PubMed query (with --pubmed)')
    parser.add_argument('--email', help='e-mail sent to NCBI (required with --pubmed)')
    parser.add_argument('--apikey', help='NCBI API key (optional, raises the request rate)')
    return parser


def main(argv=None):
    global stop_words, lemmatizer
    parser = criar_parser()
    args = parser.parse_intermixed_args(argv)

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

    if args.articles:
        modo_articles(args.entrada)
        return 0

    if not args.saida or not args.saida.lower().endswith('.xlsx'):
        dica = ''
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
    except ValueError as e:
        parser.error(str(e))
    return 0


if __name__ == '__main__':
    sys.exit(main())
