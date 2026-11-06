"""
Scopus -> MEDLINE.

Sources:
  CSV export     scopus.com: Export > CSV, with "Abstract & keywords" and
                 "Affiliations" ticked. Best source: abstracts and each author's affiliations.
  RIS export     Export > RIS. Abstracts, but affiliations are not tied to authors.
  Search API     api.elsevier.com, key from dev.elsevier.com. Two kinds of access:
                 institutional (campus network or an institutional token): view=COMPLETE,
                 abstracts and all authors, cursor paging, no result limit;
                 personal (any free key, no institution): view=STANDARD only, no abstracts,
                 first author only, at most 5,000 results per search, so larger searches
                 are split by publication year.

Every source is turned into one intermediate dict (see _vazio), then into one
MEDLINE record by scopus_para_registro.

Scopus field -> MEDLINE tag:
  PubMed ID -> PMID ("SCOPUS" + EID when there is none)    EID -> EID (kept)
  Title -> TI    Abstract -> AB (copyright notice removed)    Author full names -> FAU
  Authors -> AU    Authors with affiliations -> AD (after its author)
  Source title -> JT    Abbreviated Source Title -> TA    Year -> DP    Volume -> VI
  Issue -> IP    Page start-Page end / Art. No. -> PG    DOI -> LID, AID    ISSN -> IS
  Language -> LA    Document Type -> PT    Author Keywords -> OT    Cited by -> TCSC
"""
import csv
import html
import io
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request

from .medline import Registro, id_sem_identificador


# =====================================================
# Intermediate record
# =====================================================
def _vazio():
    return {'eid': '', 'pmid': '', 'doi': '', 'titulo': '', 'resumo': '', 'ano': '', 'mes': '',
            'revista': '', 'revista_abrev': '', 'volume': '', 'fasciculo': '', 'paginas': '',
            'issn': [], 'idioma': '', 'tipo': '', 'palavras': [], 'citacoes': '',
            'autores': [],   # [(full name, short name, [affiliations])]
            'soltos': []}    # affiliations that name no author


# Scopus appends the publisher's copyright notice to the abstract. PubMed keeps it
# in its own tag (CI), so it is removed here: otherwise "elsevier", "rights" and
# "reserved" would be counted as abstract words of Scopus-only records only.
COPYRIGHT = re.compile(r'\s*(?:copyright\s*)?(?:©|copyright)\s*(?:\d{4}|the author).*$',
                       flags=re.IGNORECASE | re.DOTALL)


def limpar_resumo(ab):
    ab = (ab or '').strip()
    if re.fullmatch(r'\[?no abstract available\]?\.?', ab, flags=re.IGNORECASE):
        return ''
    return COPYRIGHT.sub('', ab).strip()


def _formatar_issn(issn):
    """Scopus writes '17563305'; MEDLINE writes '1756-3305'."""
    issn = re.sub(r'[^0-9Xx]', '', issn or '')
    return f"{issn[:4]}-{issn[4:]}".upper() if len(issn) == 8 else ''


def _curto_medline(curto):
    """Scopus 'Souza M.A.' or 'Souza, M.A.' -> MEDLINE 'Souza MA'."""
    curto = re.sub(r',\s*', ' ', curto.strip(), count=1)
    partes = curto.rsplit(' ', 1)
    if len(partes) == 2 and re.fullmatch(r'(?:[A-ZÀ-Þ]\.?-?)+', partes[1]):
        return f"{partes[0]} {partes[1].replace('.', '')}"
    return curto


# =====================================================
# CSV export
# =====================================================
def _coluna(linha, *nomes):
    """Value of the first column found among `nomes` (Scopus has changed the case of some headers)."""
    for n in nomes:
        for k, v in linha.items():
            if k and k.strip().lower() == n.lower():
                return (v or '').strip()
    return ''


def _separar(valor):
    """'A; B; C' (current exports) or 'A, B, C' (old exports without semicolons)."""
    if not valor:
        return []
    sep = ';' if ';' in valor else ','
    return [p.strip() for p in valor.split(sep) if p.strip()]


INICIAIS = re.compile(r'(?:[A-ZÀ-Þ]\.?[\s-]*)+')


def _separar_autores(valor):
    """
    'Souza M.A.; Lopez J.' (current), 'Souza M.A., Lopez J.' (old) or
    'Souza, M.A., Lopez, J.' (older): in the last one, a piece made only of
    initials belongs to the surname before it.
    """
    if ';' in (valor or ''):
        return _separar(valor)
    autores = []
    for p in _separar(valor):
        if autores and INICIAIS.fullmatch(p) and not INICIAIS.fullmatch(autores[-1].split(', ')[-1]):
            autores[-1] += ', ' + p
        else:
            autores.append(p)
    return autores


def _variantes(completo, curto):
    """Ways a name can open an entry of 'Authors with affiliations'."""
    v = {completo, curto, _curto_medline(curto)}
    if ',' in completo:
        sobrenome, nome = [p.strip() for p in completo.split(',', 1)]
        v |= {f"{nome} {sobrenome}", f"{sobrenome} {nome}"}
    if ' ' in curto and ',' not in curto:
        s, i = curto.rsplit(' ', 1)
        v.add(f"{s}, {i}")
    return sorted((x for x in v if x), key=len, reverse=True)


def _enderecos_csv(texto, autores):
    """
    Split 'Authors with affiliations' among the authors.

    Each ';'-separated entry should start with an author's name followed by ','.
    An entry that starts with no known name is another affiliation of the
    previous author. If no entry starts with a name, the affiliations are kept
    without an owner. Names are tried starting from the author
    after the current one, so two co-authors with the same name ('Silva M.')
    each get their own entries, in author order.
    """
    entradas = [e.strip() for e in texto.split(';') if e.strip()]
    por_autor = [[] for _ in autores]
    soltos, atual, achou = [], None, False
    for e in entradas:
        melhor = None
        inicio = 0 if atual is None else atual + 1
        ordem = list(range(inicio, len(autores))) + list(range(0, inicio))
        for i in ordem:
            completo, curto, _ = autores[i]
            for v in _variantes(completo, curto):
                # regex, not lower()+startswith: lower() can change the length ('İ' -> 'i̇')
                m = re.match(re.escape(v) + r'\s*,', e, flags=re.IGNORECASE)
                if m and (melhor is None or m.end() > melhor[1]):
                    melhor = (i, m.end())
        if melhor:
            atual, achou = melhor[0], True
            afil = e[melhor[1]:].strip()
            if afil:
                por_autor[atual].append(afil)
        elif atual is not None:
            por_autor[atual].append(e)
        else:
            soltos.append(e)
    if not achou:
        return [[] for _ in autores], entradas
    return por_autor, soltos


def ler_scopus_csv(texto):
    leitor = csv.DictReader(io.StringIO(texto.lstrip('﻿')))
    registros = []
    for linha in leitor:
        d = _vazio()
        d['eid'] = _coluna(linha, 'EID')
        d['pmid'] = re.sub(r'\D', '', _coluna(linha, 'PubMed ID'))
        d['doi'] = _coluna(linha, 'DOI')
        d['titulo'] = _coluna(linha, 'Title', 'Document title')
        d['resumo'] = limpar_resumo(_coluna(linha, 'Abstract'))
        d['ano'] = _coluna(linha, 'Year')
        d['revista'] = _coluna(linha, 'Source title', 'Source Title')
        d['revista_abrev'] = _coluna(linha, 'Abbreviated Source Title')
        d['volume'] = _coluna(linha, 'Volume')
        d['fasciculo'] = _coluna(linha, 'Issue')
        ini, fim = _coluna(linha, 'Page start'), _coluna(linha, 'Page end')
        d['paginas'] = f"{ini}-{fim}" if ini and fim else ini or _coluna(linha, 'Art. No.')
        d['issn'] = [_formatar_issn(i) for i in _separar(_coluna(linha, 'ISSN'))]
        d['idioma'] = _coluna(linha, 'Language of Original Document')
        d['tipo'] = _coluna(linha, 'Document Type')
        d['palavras'] = [k for k in _coluna(linha, 'Author Keywords').split(';') if k.strip()]
        d['citacoes'] = _coluna(linha, 'Cited by')

        curtos = _separar_autores(_coluna(linha, 'Authors'))
        # "Souza, Maria Aparecida (57190000000)": the Scopus author ID is dropped
        completos = [re.sub(r'\s*\(\d+\)\s*$', '', a)
                     for a in _coluna(linha, 'Author full names').split(';') if a.strip()]
        if len(completos) != len(curtos):
            completos = curtos
        autores = [(c, s, []) for c, s in zip(completos, curtos)]
        por_autor, d['soltos'] = _enderecos_csv(_coluna(linha, 'Authors with affiliations'), autores)
        d['autores'] = [(c, s, a) for (c, s, _), a in zip(autores, por_autor)]
        if not d['autores'] and not d['soltos']:
            d['soltos'] = _separar(_coluna(linha, 'Affiliations'))
        registros.append(d)
    return registros


# =====================================================
# RIS export
# =====================================================
def ler_scopus_ris(texto):
    """RIS: 'XX  - value' lines, records end with 'ER  -'. AD lines name no author."""
    registros, campos = [], {}
    for linha in texto.replace('\r\n', '\n').split('\n'):
        m = re.match(r'([A-Z][A-Z0-9])  -\s?(.*)', linha.lstrip('﻿'))
        if not m:
            continue
        tag, valor = m.group(1), m.group(2).strip()
        if tag == 'ER':
            if campos:
                registros.append(_ris_para_dict(campos))
            campos = {}
        else:
            campos.setdefault(tag, []).append(valor)
    if campos:
        registros.append(_ris_para_dict(campos))
    return registros


def _ris_para_dict(c):
    um = lambda *tags: next((c[t][0] for t in tags if c.get(t)), '')
    d = _vazio()
    url = ' '.join(c.get('UR', []))
    m = re.search(r'eid=(2-s2\.0-\d+)', url)
    d['eid'] = m.group(1) if m else ''
    notas = ' '.join(c.get('N1', []) + c.get('C2', []))
    m = re.search(r'PubMed ID:\s*(\d+)', notas)
    d['pmid'] = m.group(1) if m else ''
    m = re.search(r'Cited By:?\s*(\d+)', notas, flags=re.IGNORECASE)
    d['citacoes'] = m.group(1) if m else ''
    d['doi'] = um('DO')
    d['titulo'] = um('TI', 'T1')
    d['resumo'] = limpar_resumo(um('AB', 'N2'))
    d['ano'] = re.sub(r'\D.*', '', um('PY', 'Y1'))
    d['revista'] = um('T2', 'JF', 'JO')
    d['revista_abrev'] = um('J2', 'JA')
    d['volume'], d['fasciculo'] = um('VL'), um('IS')
    ini, fim = um('SP'), um('EP')
    d['paginas'] = f"{ini}-{fim}" if ini and fim else ini or um('C7')
    d['issn'] = [_formatar_issn(i) for i in re.findall(r'[0-9Xx]{4}-?[0-9Xx]{4}', um('SN'))]
    d['idioma'], d['tipo'] = um('LA'), um('M3')
    d['palavras'] = c.get('KW', [])
    autores = c.get('AU') or c.get('A1') or []
    d['autores'] = [(a, a, []) for a in autores]
    d['soltos'] = c.get('AD', [])
    return d


# =====================================================
# Search API
# =====================================================
SEARCH_URL = 'https://api.elsevier.com/content/search/scopus'
PAGINA = {'COMPLETE': 25, 'STANDARD': 200}   # max records per request
PESSOAL_MAX = 5000      # a personal (non-subscriber) key cannot page past this
PESSOAL_PAGINA = 25     # records per request with a personal key


def query_scopus(query):
    """Free text becomes TITLE-ABS-KEY(...); queries with Scopus field codes pass as is."""
    if re.search(r'\b(?:TITLE-ABS-KEY|TITLE-ABS|TITLE|ABS|KEY|AUTH|AUTHOR-NAME|AFFIL|SRCTITLE|'
                 r'PUBYEAR|DOI|PMID|DOCTYPE|LANGUAGE|ALL)\s*\(', query) or 'PUBYEAR' in query:
        return query
    if '[' in query:
        print("Warning: the query has PubMed field tags ([tiab], [mh]...), which Scopus does not "
              "understand; use --scopus-query to give a Scopus query (e.g. TITLE-ABS-KEY(...)).")
    return f"TITLE-ABS-KEY({query})"


class ErroAcesso(RuntimeError):
    """Key refused or query rejected: retrying or continuing is useless."""


class ErroTemporario(RuntimeError):
    """Quota, server or network problem: what was already downloaded can be kept."""


def _get(params, apikey, insttoken=None, tentativas=4):
    url = f"{SEARCH_URL}?{urllib.parse.urlencode(params)}"
    cab = {'X-ELS-APIKey': apikey, 'Accept': 'application/json'}
    if insttoken:
        cab['X-ELS-Insttoken'] = insttoken
    req = urllib.request.Request(url, headers=cab)
    for n in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            corpo = e.read().decode('utf-8', errors='replace')[:300]
            if e.code in (401, 403):
                raise ErroAcesso(
                    f"Scopus denied access (HTTP {e.code}): {corpo}\n"
                    "Full records (COMPLETE view) need institutional access: run from the "
                    "institution's network or pass --scopus-insttoken. With a personal key "
                    "(no institution), use --scopus-key personal (titles only).") from None
            if e.code == 400:
                raise ErroAcesso(f"Scopus rejected the query (HTTP 400): {corpo}") from None
            if n == tentativas:
                raise ErroTemporario(f"Scopus error HTTP {e.code}: {corpo}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if n == tentativas:
                raise ErroTemporario(f"Scopus connection error: {e}") from None
        print(f"  Scopus busy; retrying in {2 * n}s...")
        time.sleep(2 * n)


def _lista(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _sem_html(texto):
    """API titles and abstracts can carry markup (H<inf>2</inf>O, &amp;)."""
    return html.unescape(re.sub(r'<[^>]+>', '', texto or '')).strip()


def api_para_dict(e):
    """One Scopus Search API entry (JSON) -> intermediate dict."""
    d = _vazio()
    d['eid'] = e.get('eid', '')
    d['pmid'] = re.sub(r'\D', '', str(e.get('pubmed-id', '') or ''))
    d['doi'] = e.get('prism:doi', '') or ''
    d['titulo'] = _sem_html(e.get('dc:title'))
    d['resumo'] = limpar_resumo(_sem_html(e.get('dc:description')))
    data = e.get('prism:coverDate', '') or ''
    if isinstance(data, list):
        data = data[0].get('$', '') if data else ''
    d['ano'] = data[:4]
    d['revista'] = e.get('prism:publicationName', '') or ''
    d['volume'] = e.get('prism:volume', '') or ''
    d['fasciculo'] = e.get('prism:issueIdentifier', '') or ''
    d['paginas'] = e.get('prism:pageRange') or e.get('article-number') or ''
    d['issn'] = [_formatar_issn(e.get(k)) for k in ('prism:issn', 'prism:eIssn')]
    d['tipo'] = e.get('subtypeDescription', '') or ''
    d['palavras'] = [k.strip() for k in (e.get('authkeywords') or '').split('|') if k.strip()]
    d['citacoes'] = str(e.get('citedby-count', '') or '')

    afiliacoes = {}
    for a in _lista(e.get('affiliation')):
        partes = [a.get('affilname'), a.get('affiliation-city'), a.get('affiliation-country')]
        afiliacoes[str(a.get('afid', ''))] = ', '.join(p for p in partes if p)
    autores = sorted(_lista(e.get('author')), key=lambda a: int(a.get('@seq', 0) or 0))
    for a in autores:
        sobrenome, nome = a.get('surname') or '', a.get('given-name') or ''
        completo = f"{sobrenome}, {nome}" if nome else sobrenome or a.get('authname', '')
        curto = f"{sobrenome} {a.get('initials') or ''}".strip() or a.get('authname', '')
        afs = [afiliacoes.get(str(x.get('$', '')), '') for x in _lista(a.get('afid'))]
        d['autores'].append((completo, curto, [x for x in afs if x]))
    if not autores and e.get('dc:creator'):
        # STANDARD view: first author only
        d['autores'] = [(e['dc:creator'], e['dc:creator'], [])]
    return d


def _parcial(registros, total, erro):
    """A temporary error after some pages: keep them, with a loud warning."""
    if not registros:
        raise erro
    print(f"Warning: Scopus stopped after {len(registros)} of {total} records ({erro}).\n"
          f"  The records fetched so far are kept, but THIS SEARCH IS INCOMPLETE: run it again "
          f"later (weekly quota?) or export the rest from scopus.com.")


def _total(q, apikey):
    resp = _get({'query': q, 'view': 'STANDARD', 'count': 1, 'start': 0}, apikey)
    return int(resp.get('search-results', {}).get('opensearch:totalResults', 0) or 0)


def _paginas_start(q, n, apikey, registros, vistos):
    """Personal key: pages by position ('start'), up to PESSOAL_MAX records."""
    for inicio in range(0, min(n, PESSOAL_MAX), PESSOAL_PAGINA):
        resp = _get({'query': q, 'view': 'STANDARD', 'count': PESSOAL_PAGINA, 'start': inicio},
                    apikey).get('search-results', {})
        entradas = [e for e in resp.get('entry', []) if 'error' not in e]
        if not entradas:
            break
        for e in entradas:
            if e.get('eid') not in vistos:
                vistos.add(e.get('eid'))
                registros.append(scopus_para_registro(api_para_dict(e)))
        if len(registros) % 500 < PESSOAL_PAGINA:
            print(f"  Fetched {len(registros)}")
        time.sleep(0.2)


def _por_ano(base, ini, fim, apikey, registros, vistos, cortados):
    """
    Split the search by publication year until each slice has at most PESSOAL_MAX records.
    A single year above the limit gives its first PESSOAL_MAX records; the rest is
    added to cortados[year].
    """
    q = f"({base}) AND PUBYEAR > {ini - 1} AND PUBYEAR < {fim + 1}"
    n = _total(q, apikey)
    if n == 0:
        return
    if n <= PESSOAL_MAX or ini == fim:
        periodo = str(ini) if ini == fim else f"{ini}-{fim}"
        if n > PESSOAL_MAX:
            cortados[ini] = n - PESSOAL_MAX
            print(f"  {periodo}: {n} records; only the first {PESSOAL_MAX} can be retrieved "
                  f"with a personal key")
        else:
            print(f"  {periodo}: {n} records")
        _paginas_start(q, n, apikey, registros, vistos)
        return
    meio = (ini + fim) // 2
    _por_ano(base, ini, meio, apikey, registros, vistos, cortados)
    _por_ano(base, meio + 1, fim, apikey, registros, vistos, cortados)


def baixar_scopus_pessoal(q, apikey):
    """Personal key (no institution): STANDARD view, 'start' paging, split by year above 5,000."""
    from datetime import date
    print("Warning: a personal Scopus key returns no abstracts and only the first author; "
          "Scopus-only records will be counted by title only. Add --fill-abstracts to fill them from open sources.")
    total = _total(q, apikey)
    print(f"Records found: {total}")
    registros, vistos, cortados = [], set(), {}
    try:
        if total <= PESSOAL_MAX:
            _paginas_start(q, total, apikey, registros, vistos)
        else:
            print(f"More than {PESSOAL_MAX} records: splitting the search by publication year...")
            _por_ano(q, 1800, date.today().year + 1, apikey, registros, vistos, cortados)
    except ErroTemporario as e:
        _parcial(registros, total, e)
        return registros
    print(f"  Fetched {len(registros)} of {total}")
    if len(registros) < total:
        print(f"Warning: Scopus reports {total} records, {len(registros)} were retrieved.")
        for ano, n in sorted(cortados.items()):
            print(f"  {n} from {ano}, which alone has more than {PESSOAL_MAX} records: narrow the "
                  f"query (e.g. DOCTYPE(ar), SUBJAREA(...)) or use an institutional key.")
        resto = total - len(registros) - sum(cortados.values())
        if resto > 0 and total > PESSOAL_MAX:
            print(f"  {resto} without a publication year (left out when the search is split).")
        elif resto > 0:
            print(f"  {resto} not returned by Scopus (repeated or changed while paging); "
                  f"run again to check.")
    return registros


def baixar_scopus(query, apikey, insttoken=None, view='complete', acesso='institutional'):
    """
    Download a Scopus query as Registro objects.
    acesso='institutional': cursor paging, COMPLETE (or STANDARD) view.
    acesso='personal': a key without institutional access (see baixar_scopus_pessoal).
    """
    q = query_scopus(query)
    if acesso == 'personal':
        print(f"Searching Scopus (personal key, STANDARD view) for: {q}")
        return baixar_scopus_pessoal(q, apikey)
    view = view.upper()
    print(f"Searching Scopus ({view} view) for: {q}")
    if view == 'STANDARD':
        print("Warning: the STANDARD view returns no abstracts and only the first author; "
              "Scopus-only records will be counted by title only. Add --fill-abstracts to fill them from open sources.")
    registros, cursor, total = [], '*', None
    while True:
        try:
            resp = _get({'query': q, 'view': view, 'count': PAGINA[view], 'cursor': cursor},
                        apikey, insttoken).get('search-results', {})
        except ErroTemporario as e:
            _parcial(registros, total, e)
            break
        if total is None:
            total = int(resp.get('opensearch:totalResults', 0) or 0)
            print(f"Records found: {total}")
        entradas = [e for e in resp.get('entry', []) if 'error' not in e]
        if not entradas:
            break
        registros += [scopus_para_registro(api_para_dict(e)) for e in entradas]
        print(f"  Fetched {len(registros)} of {total}")
        proximo = resp.get('cursor', {}).get('@next')
        if len(registros) >= total or not proximo or proximo == cursor:
            break
        cursor = proximo
        time.sleep(0.2)
    return registros


# =====================================================
# Files and conversion
# =====================================================
def detectar_formato_scopus(texto):
    """'scopus_csv', 'scopus_ris' or None."""
    inicio = texto.lstrip('﻿')
    cabecalho = inicio.split('\n', 1)[0]
    try:
        colunas = {c.strip().lower() for c in next(csv.reader([cabecalho]))}
    except (csv.Error, StopIteration):
        colunas = set()
    # EID may be unticked in the export; any of these Scopus-only headers is enough
    if 'title' in colunas and colunas & {'eid', 'source title', 'author full names',
                                         'authors with affiliations', 'author(s) id'}:
        return 'scopus_csv'
    if re.search(r'^TY  - ', inicio, flags=re.M) and (
            re.search(r'^DB  - Scopus', inicio, flags=re.M) or 'scopus.com' in inicio):
        return 'scopus_ris'
    return None


def ler_arquivo_scopus(texto):
    formato = detectar_formato_scopus(texto)
    if formato == 'scopus_csv':
        brutos = ler_scopus_csv(texto)
    elif formato == 'scopus_ris':
        brutos = ler_scopus_ris(texto)
    else:
        raise ValueError("not a Scopus export (CSV or RIS)")
    return [scopus_para_registro(d) for d in brutos if d['titulo'] or d['eid']]


def scopus_para_registro(d):
    eid = d['eid']
    primeiro = d['autores'][0][1] if d['autores'] else ''
    id_ = d['pmid'] or ('SCOPUS' + re.sub(r'\W', '', eid) if eid else id_sem_identificador(
        'SCOPUS', d['titulo'], d['ano'], primeiro, d['revista']))
    linhas = [('EID', eid)] if eid else []
    rotulos = ['Print', 'Electronic']
    for n, issn in enumerate(i for i in d['issn'] if i):
        linhas.append(('IS', f"{issn} ({rotulos[min(n, 1)]})"))
    if d['volume']:
        linhas.append(('VI', d['volume']))
    if d['fasciculo']:
        linhas.append(('IP', d['fasciculo']))
    if d['ano']:
        linhas.append(('DP', d['ano']))
    linhas.append(('TI', d['titulo']))
    if d['paginas']:
        linhas.append(('PG', d['paginas']))
    if d['doi']:
        linhas.append(('LID', f"{d['doi']} [doi]"))
    if d['resumo']:
        linhas.append(('AB', d['resumo']))
    linhas += [('AD', a) for a in d['soltos']]
    for completo, curto, enderecos in d['autores']:
        linhas.append(('FAU', completo))
        linhas.append(('AU', _curto_medline(curto)))
        linhas += [('AD', a) for a in enderecos]
    if d['idioma']:
        linhas.append(('LA', d['idioma']))
    if d['tipo']:
        linhas.append(('PT', d['tipo']))
    if d['revista_abrev']:
        linhas.append(('TA', d['revista_abrev']))
    if d['revista']:
        linhas.append(('JT', d['revista']))
    linhas += [('OT', k.strip()) for k in d['palavras'] if k.strip()]
    if d['doi']:
        linhas.append(('AID', f"{d['doi']} [doi]"))
    if d['citacoes']:
        linhas.append(('TCSC', d['citacoes']))

    return Registro('Scopus', id_, linhas=linhas, pmid=d['pmid'] or None, doi=d['doi'],
                    titulo=d['titulo'], ano=int(d['ano']) if str(d['ano']).isdigit() else None,
                    eid=eid or None, tc_scopus=d['citacoes'] or None)
