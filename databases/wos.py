"""
Web of Science -> MEDLINE.

Sources:
  export files   "Plain text file" or "Tab delimited file" saved from webofscience.com
                 (Export > Record Content: Full Record). Abstracts included.
  Expanded API   full records with abstracts; needs an institutional subscription key.
  Starter API    free key; no abstracts, records only have titles.

Every source is first turned into a dict of WoS field tags (TI, AB, AF, C1...),
then into one MEDLINE record by wos_para_registro.

WoS tag -> MEDLINE tag:
  PM -> PMID (UT without "WOS:" when there is no PMID)    UT -> UT (kept)
  TI -> TI    AB -> AB    AF -> FAU    AU -> AU    C1 -> AD (after its author)
  SO -> JT    J9 -> TA    PY + PD -> DP    VL -> VI    IS -> IP    BP-EP / AR -> PG
  DI -> LID, AID    SN / EI -> IS    LA -> LA    DT -> PT    DE -> OT    TC -> TC
"""
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from .medline import Registro, id_sem_identificador

# Tags that hold one value per line in the plain text export
TAGS_LISTA = {'AU', 'AF', 'BA', 'BF', 'BE', 'CA', 'GP', 'C1', 'CR'}
# Tags whose values are separated by "; " in the tab-delimited export
TAGS_LISTA_TAB = {'AU', 'AF', 'BA', 'BF', 'BE', 'CA', 'GP', 'CR'}


# =====================================================
# Export files
# =====================================================
def ler_texto(caminho):
    """
    WoS saves UTF-8 (with BOM) or, in older tab-delimited exports, UTF-16.
    A file opened and saved again in Excel on Windows is often cp1252.
    """
    dados = Path(caminho).read_bytes()
    if dados[:2] in (b'\xff\xfe', b'\xfe\xff'):
        return dados.decode('utf-16')
    try:
        return dados.decode('utf-8-sig')
    except UnicodeDecodeError:
        return dados.decode('cp1252', errors='replace')


def detectar_formato(texto):
    """'medline', 'wos_txt', 'wos_tab' or None."""
    inicio = texto.lstrip('﻿\r\n ')[:200]
    if re.search(r'^PMID- ', texto, flags=re.M):
        return 'medline'
    if inicio.startswith('FN ') or (re.search(r'^PT [A-Z]\s*$', texto, flags=re.M)
                                    and re.search(r'^ER\s*$', texto, flags=re.M)):
        return 'wos_txt'
    if re.match(r'PT\t(AU|AF)\t', inicio):
        return 'wos_tab'
    return None


def ler_wos_txt(texto):
    """Plain text export: 'XX value' lines, 3-space continuation lines, records end with 'ER'."""
    registros, campos, tag = [], {}, None
    for linha in texto.replace('\r\n', '\n').split('\n'):
        linha = linha.lstrip('﻿')
        if linha.startswith('ER'):
            if campos:
                registros.append(campos)
            campos, tag = {}, None
        elif linha.startswith(('FN ', 'VR ', 'EF')) and not campos:
            continue
        elif len(linha) >= 2 and linha[:2].strip() and (len(linha) == 2 or linha[2] == ' '):
            tag = linha[:2]
            campos.setdefault(tag, []).append(linha[3:].strip())
        elif linha.startswith('   ') and tag:
            valor = linha.strip()
            if tag in TAGS_LISTA:
                campos[tag].append(valor)
            else:
                campos[tag][-1] += ' ' + valor
    if campos:
        registros.append(campos)
    return registros


def ler_wos_tab(texto):
    """Tab-delimited export: header row of tags, one record per row."""
    linhas = texto.replace('\r\n', '\n').split('\n')
    cabecalho = linhas[0].lstrip('﻿').split('\t')
    registros = []
    for linha in linhas[1:]:
        if not linha.strip():
            continue
        campos = {}
        for tag, valor in zip(cabecalho, linha.split('\t')):
            valor = valor.strip()
            if not tag or not valor:
                continue
            if tag in TAGS_LISTA_TAB:
                campos[tag] = [v.strip() for v in valor.split(';') if v.strip()]
            elif tag == 'C1':
                # "[A; B] Addr 1; [C] Addr 2" (or "Addr 1; Addr 2" without names)
                sep = r';\s*(?=\[)' if valor.startswith('[') else r';\s*'
                campos[tag] = [v.strip() for v in re.split(sep, valor) if v.strip()]
            else:
                campos[tag] = [valor]
        registros.append(campos)
    return registros


def ler_arquivo_wos(caminho):
    """Return one Registro per record of a WoS export file."""
    texto = ler_texto(caminho)
    formato = detectar_formato(texto)
    if formato == 'wos_txt':
        brutos = ler_wos_txt(texto)
    elif formato == 'wos_tab':
        brutos = ler_wos_tab(texto)
    else:
        raise ValueError(f"{caminho} is not a Web of Science export (plain text or tab-delimited)")
    return [wos_para_registro(c) for c in brutos if c.get('TI') or c.get('UT')]


# =====================================================
# WoS fields -> MEDLINE record
# =====================================================
def _um(campos, tag):
    v = campos.get(tag)
    return v[0].strip() if v else ''


def _nome(n):
    """'Souza,  Maria A.' and 'souza, maria a' compare equal."""
    n = re.sub(r'\s*,\s*', ', ', n.replace('.', ' '))
    return re.sub(r'\s+', ' ', n).strip().lower()


def _autores_e_enderecos(campos):
    """
    [(full name, short name, [addresses])] plus the addresses that name no author.

    C1 lines "[Silva, Maria; Souza, Joao] Univ X, Brazil." give each author their
    own addresses. Old records (before ~2008) have C1 without names: those
    addresses are not given to anyone, as an author's country must come from
    that author's own address.
    """
    completos = campos.get('AF') or campos.get('AU') or []
    curtos = campos.get('AU') or []
    enderecos = {i: [] for i in range(len(completos))}
    indice = {}
    for i, n in enumerate(completos):
        indice.setdefault(_nome(n), []).append(i)
    # C1 brackets usually hold the full names (AF), but some records use the short ones (AU)
    for i, n in enumerate(curtos[:len(completos)]):
        if i not in indice.get(_nome(n), []):
            indice.setdefault(_nome(n), []).append(i)
    soltos = []
    for c1 in campos.get('C1', []):
        m = re.match(r'\[(.*?)\]\s*(.+)', c1)
        if not m:
            soltos.append(c1)
            continue
        for n in m.group(1).split(';'):
            for i in indice.get(_nome(n), []):
                if m.group(2).strip() not in enderecos[i]:
                    enderecos[i].append(m.group(2).strip())
    autores = [(n, curtos[i] if i < len(curtos) else n, enderecos[i]) for i, n in enumerate(completos)]
    return autores, soltos


def _curto_medline(au):
    """WoS 'Silva, MA' -> MEDLINE 'Silva MA'."""
    return re.sub(r',\s*', ' ', au, count=1).strip()


MESES = {m: m.title() for m in ('JAN', 'FEB', 'MAR', 'APR', 'MAY', 'JUN',
                                'JUL', 'AUG', 'SEP', 'OCT', 'NOV', 'DEC')}


def wos_para_registro(campos):
    ut = _um(campos, 'UT')
    pm = re.sub(r'\D', '', _um(campos, 'PM'))
    id_ = pm or ut.replace(':', '') or id_sem_identificador(
        'WOS', _um(campos, 'TI'), _um(campos, 'PY'), _um(campos, 'AU'), _um(campos, 'SO'))
    doi = _um(campos, 'DI')
    ano = _um(campos, 'PY')
    pd_ = ' '.join(MESES.get(p.upper(), p) for p in _um(campos, 'PD').split())

    linhas = [('UT', ut)] if ut else []
    for tag, rotulo in (('SN', 'Print'), ('EI', 'Electronic')):
        if _um(campos, tag):
            linhas.append(('IS', f"{_um(campos, tag)} ({rotulo})"))
    for tag_wos, tag_med in (('VL', 'VI'), ('IS', 'IP')):
        if _um(campos, tag_wos):
            linhas.append((tag_med, _um(campos, tag_wos)))
    if ano:
        linhas.append(('DP', f"{ano} {pd_}".strip()))
    linhas.append(('TI', _um(campos, 'TI')))
    bp, ep = _um(campos, 'BP'), _um(campos, 'EP')
    pg = f"{bp}-{ep}" if bp and ep else bp or _um(campos, 'AR')
    if pg:
        linhas.append(('PG', pg))
    if doi:
        linhas.append(('LID', f"{doi} [doi]"))
    if _um(campos, 'AB'):
        linhas.append(('AB', _um(campos, 'AB')))

    autores, soltos = _autores_e_enderecos(campos)
    linhas += [('AD', a) for a in soltos]
    for completo, curto, enderecos in autores:
        linhas.append(('FAU', completo))
        linhas.append(('AU', _curto_medline(curto)))
        linhas += [('AD', a) for a in enderecos]

    if _um(campos, 'LA'):
        linhas.append(('LA', _um(campos, 'LA')))
    linhas += [('PT', t.strip()) for t in _um(campos, 'DT').split(';') if t.strip()]
    if _um(campos, 'J9') or _um(campos, 'JI'):
        linhas.append(('TA', _um(campos, 'J9') or _um(campos, 'JI')))
    if _um(campos, 'SO'):
        linhas.append(('JT', _um(campos, 'SO')))
    linhas += [('OT', k.strip()) for k in _um(campos, 'DE').split(';') if k.strip()]
    if doi:
        linhas.append(('AID', f"{doi} [doi]"))
    tc = _um(campos, 'TC')
    if tc:
        linhas.append(('TC', tc))

    return Registro('WOS', id_, linhas=linhas, pmid=pm or None, doi=doi,
                    titulo=_um(campos, 'TI'), ano=int(ano) if ano.isdigit() else None,
                    ut=ut or None, tc=tc or None)


# =====================================================
# APIs
# =====================================================
EXPANDED_URL = 'https://api.clarivate.com/api/wos'
STARTER_URL = 'https://api.clarivate.com/apis/wos-starter/v1/documents'
EXPANDED_PAGE = 100       # max records per request
EXPANDED_MAX = 100000     # firstRecord cannot go past this
STARTER_PAGE = 50


def query_wos(query):
    """PubMed-style free text becomes a WoS topic search; queries with field tags pass as is."""
    if re.search(r'\b[A-Z]{2,3}\s*=', query):
        return query
    if '[' in query:
        print("Warning: the query has PubMed field tags ([tiab], [mh]...), which WoS does not "
              "understand; use --wos-query to give a WoS query (e.g. TS=(...)).")
    return f"TS=({query})"


class ErroAcesso(RuntimeError):
    """Key refused or query rejected: retrying or continuing is useless."""


class ErroTemporario(RuntimeError):
    """Quota, server or network problem: what was already downloaded can be kept."""


def _get(url, params, apikey, tentativas=4):
    url = f"{url}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(url, headers={'X-ApiKey': apikey, 'Accept': 'application/json'})
    for n in range(1, tentativas + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode('utf-8'))
        except urllib.error.HTTPError as e:
            corpo = e.read().decode('utf-8', errors='replace')[:300]
            if e.code in (401, 403):
                raise ErroAcesso(f"WoS refused the API key (HTTP {e.code}): {corpo}") from None
            if e.code == 400:
                raise ErroAcesso(f"WoS rejected the query (HTTP 400): {corpo}") from None
            if n == tentativas:
                raise ErroTemporario(f"WoS error HTTP {e.code}: {corpo}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            if n == tentativas:
                raise ErroTemporario(f"WoS connection error: {e}") from None
        print(f"  WoS busy; retrying in {2 * n}s...")
        time.sleep(2 * n)


def _lista(x):
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def _achar_recs(resp):
    """REC list of an Expanded API response (search and /query pages nest it differently)."""
    for base in (resp.get('Data', {}), resp):
        recs = base.get('Records', {}).get('records', {})
        if isinstance(recs, dict) and recs.get('REC'):
            return _lista(recs['REC'])
    return []


def _texto(x):
    if isinstance(x, dict):
        return str(x.get('content', ''))
    return str(x or '')


def expanded_para_campos(rec):
    """One Expanded API REC (JSON) -> WoS tag dict, as in a plain text export."""
    st = rec.get('static_data', {})
    resumo = st.get('summary', {})
    full = st.get('fullrecord_metadata', {})
    campos = {'UT': [rec.get('UID', '')]}

    for t in _lista(resumo.get('titles', {}).get('title')):
        tag = {'item': 'TI', 'source': 'SO', 'source_abbrev': 'J9', 'abbrev_iso': 'JI'}.get(t.get('type'))
        if tag:
            campos[tag] = [_texto(t)]

    autores = sorted((n for n in _lista(resumo.get('names', {}).get('name')) if n.get('role') == 'author'),
                     key=lambda n: int(n.get('seq_no', 0) or 0))
    campos['AF'] = [n.get('full_name') or n.get('display_name') or n.get('wos_standard', '') for n in autores]
    campos['AU'] = [n.get('wos_standard') or n.get('display_name') or n.get('full_name', '') for n in autores]

    # Address number -> authors, rebuilt as C1 lines "[A; B] address"
    por_endereco = {}
    for n, af in zip(autores, campos['AF']):
        for num in str(n.get('addr_no', '')).split():
            por_endereco.setdefault(num, []).append(af)
    c1 = []
    for a in _lista(full.get('addresses', {}).get('address_name')):
        spec = a.get('address_spec', {})
        nomes = por_endereco.get(str(spec.get('addr_no', '')), [])
        endereco = spec.get('full_address', '')
        c1.append(f"[{'; '.join(nomes)}] {endereco}" if nomes else endereco)
    campos['C1'] = c1

    paragrafos = []
    for ab in _lista(full.get('abstracts', {}).get('abstract')):
        paragrafos += [_texto(p) for p in _lista(ab.get('abstract_text', {}).get('p'))]
        break  # first abstract only (others are translations)
    if paragrafos:
        campos['AB'] = [' '.join(paragrafos)]

    pub = resumo.get('pub_info', {})
    for chave, tag in (('pubyear', 'PY'), ('pubmonth', 'PD'), ('vol', 'VL'), ('issue', 'IS')):
        if pub.get(chave):
            campos[tag] = [str(pub[chave])]
    pagina = pub.get('page', {})
    if isinstance(pagina, dict):
        if pagina.get('begin'):
            campos['BP'] = [str(pagina['begin'])]
        if pagina.get('end'):
            campos['EP'] = [str(pagina['end'])]

    campos['DT'] = ['; '.join(_texto(d) for d in _lista(resumo.get('doctypes', {}).get('doctype')))]
    idiomas = [_texto(l) for l in _lista(full.get('languages', {}).get('language'))]
    if idiomas:
        campos['LA'] = [idiomas[0]]
    chaves = [_texto(k) for k in _lista(full.get('keywords', {}).get('keyword'))]
    if chaves:
        campos['DE'] = ['; '.join(chaves)]

    ids = rec.get('dynamic_data', {}).get('cluster_related', {}).get('identifiers', {})
    for i in _lista(ids.get('identifier')):
        tipo, valor = i.get('type'), str(i.get('value', ''))
        if tipo in ('doi', 'xref_doi') and 'DI' not in campos:
            campos['DI'] = [valor]
        elif tipo == 'pmid':
            campos['PM'] = [valor.split(':')[-1]]
        elif tipo == 'issn':
            campos['SN'] = [valor]
        elif tipo == 'eissn':
            campos['EI'] = [valor]

    tc = rec.get('dynamic_data', {}).get('citation_related', {}).get('tc_list', {})
    for silo in _lista(tc.get('silo_tc')):
        if silo.get('coll_id') == 'WOS':
            campos['TC'] = [str(silo.get('local_count', ''))]
    return campos


def starter_para_campos(doc):
    """One Starter API document -> WoS tag dict (no abstract, no addresses)."""
    src = doc.get('source', {})
    ids = doc.get('identifiers', {})
    autores = doc.get('names', {}).get('authors', [])
    campos = {
        'UT': [doc.get('uid', '')],
        'TI': [doc.get('title', '')],
        'AF': [a.get('displayName') or a.get('wosStandard', '') for a in autores],
        'AU': [a.get('wosStandard') or a.get('displayName', '') for a in autores],
        'SO': [src.get('sourceTitle', '')],
        'DT': ['; '.join(doc.get('types', []))],
        'DE': ['; '.join(doc.get('keywords', {}).get('authorKeywords', []))],
    }
    for chave, tag in (('publishYear', 'PY'), ('publishMonth', 'PD'), ('volume', 'VL'),
                       ('issue', 'IS'), ('articleNumber', 'AR')):
        if src.get(chave):
            campos[tag] = [str(src[chave])]
    pg = src.get('pages', {})
    if pg.get('begin'):
        campos['BP'] = [pg['begin']]
    if pg.get('end'):
        campos['EP'] = [pg['end']]
    for chave, tag in (('doi', 'DI'), ('pmid', 'PM'), ('issn', 'SN'), ('eissn', 'EI')):
        if ids.get(chave):
            campos[tag] = [str(ids[chave]).split(':')[-1] if tag == 'PM' else str(ids[chave])]
    for c in doc.get('citations', []):
        if c.get('db') == 'WOS':
            campos['TC'] = [str(c.get('count', ''))]
    return campos


def _parcial(registros, total, erro):
    """A temporary error after some pages: keep them, with a loud warning."""
    if not registros:
        raise erro
    print(f"Warning: Web of Science stopped after {len(registros)} of {total} records ({erro}).\n"
          f"  The records fetched so far are kept, but THIS SEARCH IS INCOMPLETE: run it again "
          f"later (daily quota?) or export the rest from webofscience.com.")


def baixar_wos(query, apikey, api='expanded', db='WOS'):
    """
    Download a WoS query as Registro objects.
    api='expanded' gets full records with abstracts (subscription);
    api='starter' gets titles and metadata only.
    """
    q = query_wos(query)
    print(f"Searching Web of Science ({api} API) for: {q}")
    registros = []
    if api == 'starter':
        print("Warning: the Starter API returns no abstracts; WoS-only records will "
              "be counted by title only. Add --fill-abstracts to fill them from open sources.")
        pagina, total = 1, None
        while total is None or len(registros) < total:
            try:
                resp = _get(STARTER_URL, {'db': db, 'q': q, 'limit': STARTER_PAGE, 'page': pagina}, apikey)
            except ErroTemporario as e:
                _parcial(registros, total, e)
                break
            total = resp.get('metadata', {}).get('total', 0)
            if pagina == 1:
                print(f"Records found: {total}")
            hits = resp.get('hits', [])
            if not hits:
                break
            registros += [wos_para_registro(starter_para_campos(d)) for d in hits]
            print(f"  Fetched {len(registros)} of {total}")
            pagina += 1
            time.sleep(1.1)  # free plan: 1 request per second
        return registros

    params = {'databaseId': db, 'usrQuery': q, 'count': EXPANDED_PAGE, 'firstRecord': 1}
    resp = _get(EXPANDED_URL, params, apikey)
    info = resp.get('QueryResult', {})
    total, query_id = int(info.get('RecordsFound', 0)), info.get('QueryID')
    print(f"Records found: {total}")
    if total > EXPANDED_MAX:
        print(f"Warning: the API can only page through the first {EXPANDED_MAX} records.")
    recs = _achar_recs(resp)
    while True:
        registros += [wos_para_registro(expanded_para_campos(r)) for r in recs]
        print(f"  Fetched {len(registros)} of {total}")
        proximo = len(registros) + 1
        if not recs or proximo > min(total, EXPANDED_MAX) or not query_id:
            break
        time.sleep(0.5)  # 2 requests per second
        try:
            resp = _get(f"{EXPANDED_URL}/query/{query_id}",
                        {'count': EXPANDED_PAGE, 'firstRecord': proximo}, apikey)
        except ErroTemporario as e:
            _parcial(registros, total, e)
            break
        recs = _achar_recs(resp)
    return registros
