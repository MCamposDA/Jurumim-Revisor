"""
Fill in missing abstracts from open sources (--fill-abstracts).

For a record without AB, the first English abstract found is used, in this order:
  1. PubMed, by PMID           (same records the tool already downloads)
  2. Crossref, by DOI          (abstract deposited by the publisher)
  3. Semantic Scholar, by DOI  (optional key: S2_API_KEY)
  4. OpenAlex, by DOI          (optional key: OPENALEX_API_KEY); last, because some of its
                               abstracts are extracted from PDFs and have OCR errors
Europe PMC is not used: in the coverage test it added no abstract that the others missed.

No source needs an institution. Each filled record gains AB and ABS (the source),
so the origin of every abstract can be reported; records that already have an
abstract are never changed.

Language: Latin American journals often deposit the abstract in Portuguese or
Spanish, or in two languages at once. Sentences in Portuguese, Spanish or French
are dropped, and an abstract is used only if what is left is English and at least
MIN_RESUMO characters long; otherwise the next source is tried.
"""
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter

from .medline import _campos
from .scopus import limpar_resumo

MIN_RESUMO = 100
UA = {'User-Agent': 'JurumimRevisor/1.0 (https://github.com/MCamposDA/Jurumim-Revisor)'}
FONTES = ['PubMed', 'Crossref', 'Semantic Scholar', 'OpenAlex']


# =====================================================
# Language
# =====================================================
_STOP = None


def _stopwords():
    """
    Stopwords exclusive to each language. Short words shared by English and the
    others ('a', 'o', 'y', 'no', 'me') would otherwise make Spanish and Portuguese
    sentences look English.
    """
    global _STOP
    if _STOP is None:
        from nltk.corpus import stopwords
        todas = {l: set(stopwords.words(l)) for l in ('english', 'portuguese', 'spanish', 'french')}
        so = {l: s - set().union(*(o for k, o in todas.items() if k != l)) for l, s in todas.items()}
        _STOP = so.pop('english'), so
    return _STOP


def _nao_ingles(frase):
    """True when a sentence is clearly Portuguese, Spanish or French."""
    en, outras = _stopwords()
    w = re.findall(r'[a-zà-ÿ]+', frase.lower())
    n_en = sum(x in en for x in w)
    n_outra = max(sum(x in s for x in w) for s in outras.values())
    return n_outra >= 3 and n_outra > n_en


def so_ingles(texto):
    """Drop non-English sentences; return the English text or '' when too little is left."""
    frases = re.split(r'(?<=[.!?])\s+', texto)
    manter = [f for f in frases if not _nao_ingles(f)]
    resultado = ' '.join(manter).strip()
    en, _ = _stopwords()
    w = re.findall(r'[a-z]+', resultado.lower())
    if len(resultado) < MIN_RESUMO or sum(x in en for x in w) < 5:
        return ''
    return resultado


def limpar(texto, jats=False):
    """Remove JATS markup (Crossref), headings such as 'Abstract', HTML entities and the copyright notice."""
    if jats:
        texto = re.sub(r'<jats:title>.*?</jats:title>', ' ', texto or '', flags=re.S)
        texto = re.sub(r'</jats:p>|</jats:sec>', '. ', texto)
    texto = html.unescape(re.sub(r'<[^>]+>', ' ', texto or ''))
    texto = re.sub(r'\s+', ' ', texto).strip()
    texto = re.sub(r'^(?:abstract|summary)\s*[:.]?\s+', '', texto, flags=re.I)
    texto = re.sub(r'(\.\s*){2,}', '. ', texto)
    return limpar_resumo(texto)


# =====================================================
# HTTP
# =====================================================
class ErroHTTP(RuntimeError):
    def __init__(self, codigo, mensagem):
        super().__init__(mensagem)
        self.codigo = codigo


class FonteInterrompida(RuntimeError):
    """A source stopped (quota, network); `achados` keeps what it found before."""
    def __init__(self, erro, achados):
        super().__init__(str(erro))
        self.achados = achados


def _http(url, data=None, headers=None, tentativas=6):
    cab = dict(UA, **(headers or {}))
    for n in range(tentativas):
        try:
            req = urllib.request.Request(url, data=data, headers=cab)
            with urllib.request.urlopen(req, timeout=90) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and n < tentativas - 1:
                time.sleep(3 * (n + 1))
                continue
            raise ErroHTTP(e.code, f"HTTP {e.code}") from None
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            if n < tentativas - 1:
                time.sleep(3)
                continue
            raise ErroHTTP(None, str(e)) from None


def _em_lotes(chaves, tamanho, buscar, pausa=0.5):
    """
    Call buscar(batch) -> {key: abstract} over all keys.
    A batch rejected with HTTP 400 (usually one malformed DOI, e.g. with a comma
    that breaks the filter syntax) is split in halves until the bad key is
    isolated and skipped. Any other error stops the source and keeps what was
    already found (FonteInterrompida).
    """
    achados = {}
    pendentes = [chaves[i:i + tamanho] for i in range(0, len(chaves), tamanho)]
    while pendentes:
        lote = pendentes.pop(0)
        try:
            achados.update(buscar(lote))
        except ErroHTTP as e:
            if e.codigo == 400 and len(lote) > 1:
                meio = len(lote) // 2
                pendentes[:0] = [lote[:meio], lote[meio:]]
            elif e.codigo != 400:
                raise FonteInterrompida(e, achados) from None
        time.sleep(pausa)
    return achados


# =====================================================
# Sources: each returns {key: raw abstract} for the keys it found
# =====================================================
def _pubmed(pmids, email):
    from Bio import Entrez
    Entrez.email, Entrez.tool = email, 'JurumimRevisor'

    def buscar(lote):
        try:
            h = Entrez.efetch(db='pubmed', id=','.join(lote), rettype='medline', retmode='text')
            texto = h.read()
            h.close()
        except urllib.error.HTTPError as e:
            raise ErroHTTP(e.code, f"HTTP {e.code}") from None
        except (urllib.error.URLError, OSError) as e:
            raise ErroHTTP(None, str(e)) from None
        achados = {}
        for bloco in re.split(r'\n(?=PMID-)', texto):
            c = _campos(bloco.strip('\n'))
            if c.get('PMID') and c.get('AB'):
                achados[c['PMID'][0]] = ' '.join(c['AB'])
        return achados
    return _em_lotes(pmids, 200, buscar, pausa=0.4)


def _crossref(dois):
    def buscar(lote):
        q = urllib.parse.urlencode({'filter': ','.join(f'doi:{d}' for d in lote),
                                    'rows': 100, 'select': 'DOI,abstract'})
        r = _http(f'https://api.crossref.org/works?{q}')
        return {it['DOI'].lower(): it['abstract']
                for it in r.get('message', {}).get('items', []) if it.get('abstract')}
    return _em_lotes(dois, 50, buscar)


def _semantic_scholar(dois, chave=None):
    cab = {'Content-Type': 'application/json'}
    if chave:
        cab['x-api-key'] = chave

    def buscar(lote):
        corpo = json.dumps({'ids': [f'DOI:{d}' for d in lote]}).encode()
        r = _http('https://api.semanticscholar.org/graph/v1/paper/batch?fields=abstract',
                  data=corpo, headers=cab, tentativas=10)
        return {d: p['abstract'] for d, p in zip(lote, r or []) if p and p.get('abstract')}
    return _em_lotes(dois, 500, buscar, pausa=1.1)


def _openalex(dois, chave=None):
    def buscar(lote):
        params = {'filter': 'doi:' + '|'.join(lote), 'per-page': 50,
                  'select': 'doi,abstract_inverted_index'}
        if chave:
            params['api_key'] = chave
        r = _http('https://api.openalex.org/works?' + urllib.parse.urlencode(params))
        achados = {}
        for w in r.get('results', []):
            inv = w.get('abstract_inverted_index')
            if inv:
                pos = sorted((p, t) for t, ps in inv.items() for p in ps)
                achados[(w.get('doi') or '').lower().replace('https://doi.org/', '')] = \
                    ' '.join(t for _, t in pos)
        return achados
    return _em_lotes(dois, 50, buscar)


# =====================================================
# Filling
# =====================================================
def sem_resumo(r):
    c = _campos(r.to_medline())
    return not ''.join(c.get('AB', [])).strip()


def preencher(registros, email=None, s2_chave=None, openalex_chave=None):
    """
    Fill AB (+ ABS) in the records that have none. Returns the report
    {'without': n, 'filled': Counter(source), 'only_other_language': n,
     'not_found': n, 'no_id': n, 'errors': [...]}.
    """
    faltam = [r for r in registros if sem_resumo(r)]
    rel = {'without': len(faltam), 'filled': Counter(), 'only_other_language': 0,
           'not_found': 0, 'no_id': 0, 'errors': []}
    print(f"\nFilling abstracts: {len(faltam)} of {len(registros)} records have none.")
    if not faltam:
        return rel

    outro_idioma = set()
    pendentes = list(faltam)

    def aplicar(fonte, achados, chave_de, jats=False):
        nonlocal pendentes
        resto = []
        for r in pendentes:
            bruto = achados.get(chave_de(r))
            texto = so_ingles(limpar(bruto, jats)) if bruto else ''
            if texto:
                r.extras += [('AB', texto), ('ABS', fonte)]
                rel['filled'][fonte] += 1
                outro_idioma.discard(id(r))
            else:
                if bruto and len(limpar(bruto, jats)) >= MIN_RESUMO:
                    outro_idioma.add(id(r))
                resto.append(r)
        pendentes = resto

    etapas = [
        # A record that came from PubMed without abstract has none there: not asked again
        ('PubMed', lambda: _pubmed(sorted({r.pmid for r in pendentes
                                           if r.pmid and 'PubMed' not in r.fontes}), email),
         lambda r: r.pmid, False,
         lambda: any(r.pmid and 'PubMed' not in r.fontes for r in pendentes) and email),
        ('Crossref', lambda: _crossref(sorted({r.doi for r in pendentes if r.doi})),
         lambda r: r.doi, True, lambda: any(r.doi for r in pendentes)),
        ('Semantic Scholar', lambda: _semantic_scholar(sorted({r.doi for r in pendentes if r.doi}), s2_chave),
         lambda r: r.doi, False, lambda: any(r.doi for r in pendentes)),
        ('OpenAlex', lambda: _openalex(sorted({r.doi for r in pendentes if r.doi}), openalex_chave),
         lambda r: r.doi, False, lambda: any(r.doi for r in pendentes)),
    ]
    for fonte, buscar, chave_de, jats, precisa in etapas:
        if not pendentes:
            break
        if not precisa():
            if fonte == 'PubMed' and not email and any(r.pmid and 'PubMed' not in r.fontes
                                                       for r in pendentes):
                print("  PubMed skipped (no e-mail); records with a PMID go on to the DOI sources.")
            continue
        antes = len(pendentes)
        try:
            aplicar(fonte, buscar(), chave_de, jats)
        except FonteInterrompida as e:
            aplicar(fonte, e.achados, chave_de, jats)   # keep what it found before stopping
            rel['errors'].append(f"{fonte}: {e}")
            print(f"  {fonte}: stopped early ({e}); going on with the next source")
        except Exception as e:
            rel['errors'].append(f"{fonte}: {e}")
            print(f"  {fonte}: not available ({e}); going on with the next source")
        print(f"  {fonte}: {antes - len(pendentes)} filled, {len(pendentes)} still without abstract")

    for r in pendentes:
        if not (r.pmid or r.doi):
            rel['no_id'] += 1
        elif id(r) in outro_idioma:
            rel['only_other_language'] += 1
        else:
            rel['not_found'] += 1
    feitos = sum(rel['filled'].values())
    print(f"Abstracts filled: {feitos} of {len(faltam)} ("
          + ', '.join(f"{f}: {rel['filled'][f]}" for f in FONTES if rel['filled'][f]) + ')')
    if pendentes:
        print(f"Still without abstract: {len(pendentes)} ({rel['not_found']} not found, "
              f"{rel['only_other_language']} only in another language, {rel['no_id']} without DOI or PMID)")
    return rel
