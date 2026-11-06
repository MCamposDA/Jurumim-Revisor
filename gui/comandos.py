"""
Interface state -> Jurumim_Revisor.py command line.

Every builder returns (argv, env, problems):
  argv      arguments after "python3 Jurumim_Revisor.py"
  env       extra environment variables; API keys go here rather than in argv,
            which shows in the command box and in the process list
  problems  messages that block the run (empty list = ready)
"""
import os
import re
import shlex
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
SCRIPT = RAIZ / 'Jurumim_Revisor.py'

# API keys accepted by Jurumim_Revisor.py through environment variables
VARIAVEIS_CHAVE = {
    'wos_apikey': 'WOS_API_KEY',
    'scopus_apikey': 'SCOPUS_API_KEY',
    'scopus_insttoken': 'SCOPUS_INSTTOKEN',
    's2_apikey': 'S2_API_KEY',
    'openalex_apikey': 'OPENALEX_API_KEY',
}


def chaves_salvas():
    """Keys saved by the terminal tool in ~/.jurumim_keys.json (databases/credenciais.py)."""
    try:
        from databases import credenciais
        return credenciais.carregar()
    except Exception:
        return {}


def _chave(estado, nome, salvas):
    """A key is available when typed, set in the environment, or saved."""
    return bool(estado.get(nome) or os.environ.get(VARIAVEIS_CHAVE.get(nome, ''), '') or salvas.get(nome))


def _env_chaves(estado):
    return {var: estado[k] for k, var in VARIAVEIS_CHAVE.items() if estado.get(k)}


def _comum(estado, argv):
    if estado.get('pasta'):
        argv += ['--outdir', estado['pasta']]
    argv.append('--no-prompt')      # the interface has no terminal to answer questions
    return argv


def _opcoes_resumo(estado, argv):
    if estado.get('preencher'):
        argv.append('--fill-abstracts')
    if estado.get('manter_sem_resumo'):
        argv.append('--keep-no-abstract')


# =====================================================
# 1. Search
# =====================================================
def comando_busca(estado, salvas=None):
    salvas = chaves_salvas() if salvas is None else salvas
    dbs = [d for d in ('pubmed', 'wos', 'scopus') if estado.get(f'db_{d}')]
    problemas = []
    if not dbs:
        problemas.append('Choose at least one database.')
    query = (estado.get('query') or '').strip()
    proprias = {'pubmed': None, 'wos': estado.get('wos_query'), 'scopus': estado.get('scopus_query')}
    if not query and not all((proprias[d] or '').strip() for d in dbs):
        problemas.append('Write the search query.')

    argv = ['-p']
    if query:
        argv += ['-q', query]
    argv += ['--db'] + dbs
    if 'pubmed' in dbs:
        if estado.get('email'):
            argv += ['--email', estado['email'].strip()]
        elif not salvas.get('email'):
            problemas.append('PubMed needs an e-mail (any e-mail of yours).')
        if estado.get('ncbi_apikey'):
            argv += ['--apikey', estado['ncbi_apikey'].strip()]
    if 'wos' in dbs:
        argv += ['--wos-api', estado.get('wos_api') or 'expanded']
        if (estado.get('wos_query') or '').strip():
            argv += ['--wos-query', estado['wos_query'].strip()]
        if not _chave(estado, 'wos_apikey', salvas):
            problemas.append('Web of Science needs an API key (Keys page or the field above).')
    if 'scopus' in dbs:
        acesso = estado.get('scopus_key') or 'institutional'
        argv += ['--scopus-key', acesso]
        if acesso == 'institutional' and estado.get('scopus_view') == 'standard':
            argv += ['--scopus-view', 'standard']
        if (estado.get('scopus_query') or '').strip():
            argv += ['--scopus-query', estado['scopus_query'].strip()]
        if not _chave(estado, 'scopus_apikey', salvas):
            problemas.append('Scopus needs an API key (Keys page or the field above).')
    _opcoes_resumo(estado, argv)
    return _comum(estado, argv), _env_chaves(estado), problemas


# =====================================================
# 2. Merge
# =====================================================
def comando_merge(estado):
    arquivos = [a for a in estado.get('arquivos', []) if a]
    problemas = [] if arquivos else ['Add the files exported from each database.']
    problemas += [f'File not found: {a}' for a in arquivos if not Path(a).is_file()]
    saida = (estado.get('merge_out') or '').strip() or 'Merged_records.txt'
    if not saida.lower().endswith('.txt'):
        problemas.append('The merged file name must end with .txt')
    argv = ['--merge'] + arquivos + ['--merge-out', saida]
    _opcoes_resumo(estado, argv)
    return _comum(estado, argv), _env_chaves(estado), problemas


def comando_preencher(estado):
    arquivo = (estado.get('arquivo_preencher') or '').strip()
    problemas = []
    if not arquivo:
        problemas.append('Choose the file whose abstracts should be filled.')
    elif not Path(arquivo).is_file():
        problemas.append(f'File not found: {arquivo}')
    argv = ['--fill-abstracts', arquivo]
    if (estado.get('fill_out') or '').strip():
        argv += ['--fill-out', estado['fill_out'].strip()]
    if estado.get('manter_sem_resumo'):
        argv.append('--keep-no-abstract')
    if estado.get('email'):
        argv += ['--email', estado['email'].strip()]
    return _comum(estado, argv), _env_chaves(estado), problemas


# =====================================================
# 3. Screen
# =====================================================
def comando_triagem(estado):
    mesclado = (estado.get('mesclado') or '').strip()
    prisma = (estado.get('prisma') or '').strip()
    manter = [d for d in ('include', 'maybe', 'exclude') if estado.get(f'keep_{d}')]
    problemas = []
    for rotulo, caminho in (('merged file', mesclado), ('PRISMA table', prisma)):
        if not caminho:
            problemas.append(f'Choose the {rotulo}.')
        elif not Path(caminho).is_file():
            problemas.append(f'File not found: {caminho}')
    if not manter:
        problemas.append('Choose which decisions to keep.')
    argv = ['--screen', mesclado, prisma, '--keep'] + manter
    if (estado.get('screen_out') or '').strip():
        argv += ['--screen-out', estado['screen_out'].strip()]
    return _comum(estado, argv), {}, problemas


# =====================================================
# 4. Analyse
# =====================================================
def grupos_de_texto(texto):
    """
    'sandfly: phlebotomine, phlebotomines' (one group per line) ->
    ['-st', 'sandfly', '-so', 'phlebotomine', '-so', 'phlebotomines'].
    """
    argv, problemas = [], []
    for n, linha in enumerate((texto or '').splitlines(), 1):
        linha = linha.strip()
        if not linha:
            continue
        if ':' not in linha:
            problemas.append(f'Group line {n} needs "term: synonym, synonym".')
            continue
        termo, resto = linha.split(':', 1)
        sinonimos = [s.strip() for s in resto.split(',') if s.strip()]
        if not termo.strip():
            problemas.append(f'Group line {n} has no standard term before ":".')
            continue
        argv += ['-st', termo.strip()]
        for s in sinonimos:
            argv += ['-so', s]
    return argv, problemas


def termos_de_texto(texto):
    """One search term per line (phrases and hyphenated terms allowed)."""
    return [t.strip() for t in (texto or '').splitlines() if t.strip()]


def comando_analise(estado):
    entrada = (estado.get('entrada') or '').strip()
    saida = (estado.get('saida') or '').strip()
    modo = estado.get('modo') or 'frequency'
    problemas = []
    if not entrada:
        problemas.append('Choose the file to analyse (the screened or merged .txt).')
    elif not Path(entrada).is_file():
        problemas.append(f'File not found: {entrada}')
    so_artigos = estado.get('articles') and not estado.get('viewer') and modo == 'frequency' \
        and not saida
    if not so_artigos and not saida.lower().endswith('.xlsx'):
        problemas.append('The table name must end with .xlsx')

    argv = [entrada] + ([saida] if saida else [])
    grupos, prob = grupos_de_texto(estado.get('grupos')) if modo in ('groups', 'search') else ([], [])
    problemas += prob
    if modo == 'search':
        termos = termos_de_texto(estado.get('termos'))
        if not termos and not grupos:
            problemas.append('Write at least one search term or group.')
        argv += ['--ws'] + termos + grupos
    elif modo == 'groups':
        if not grupos:
            problemas.append('Write at least one group.')
        argv += grupos
    stop = [w for w in re.split(r'[,\s]+', estado.get('stopwords') or '') if w]
    if estado.get('stopword_file'):
        stop.append(estado['stopword_file'])
    if stop:
        argv += ['-sw'] + stop
    for chave, flag in (('lemma', '--lemma'), ('articles', '--articles'), ('viewer', '--viewer')):
        if estado.get(chave):
            argv.append(flag)
    return _comum(estado, argv), {}, problemas


# =====================================================
# Keys
# =====================================================
def comando_esquecer():
    return ['--forget-keys'], {}, []


# =====================================================
# Display
# =====================================================
OCULTAR_DEPOIS = {'--apikey'}


def texto_comando(argv, python='python3'):
    """The command as typed in a terminal, with the NCBI key masked."""
    partes, ocultar = [], False
    for a in argv:
        partes.append('********' if ocultar else a)
        ocultar = a in OCULTAR_DEPOIS
    return f"{python} Jurumim_Revisor.py " + ' '.join(shlex.quote(p) for p in partes)


# =====================================================
# Files of a topic folder
# =====================================================
def arquivos_do_topico(pasta):
    """Newest merged file, its PRISMA table and its screened file in a topic folder."""
    pasta = Path(pasta) if pasta else None
    if not pasta or not pasta.is_dir():
        return {}
    def recentes(padrao, excluir=()):
        achados = [p for p in pasta.glob(padrao) if not any(p.name.endswith(e) for e in excluir)]
        return sorted(achados, key=lambda p: p.stat().st_mtime, reverse=True)
    mesclados = recentes('*.txt', ('_no_abstract.txt', '_screened.txt', '_filled.txt'))
    mesclados = [p for p in mesclados if p.with_name(p.stem + '_prisma.xlsx').is_file()]
    achado = {}
    if mesclados:
        m = mesclados[0]
        achado['mesclado'] = str(m)
        achado['prisma'] = str(m.with_name(m.stem + '_prisma.xlsx'))
        triado = m.with_name(m.stem + '_screened.txt')
        achado['triado'] = str(triado) if triado.is_file() else ''
    brutos = recentes('*.txt', ('_no_abstract.txt', '_screened.txt'))
    achado['brutos'] = [str(p) for p in brutos if p.name.startswith(('Pubmed_', 'WOS_', 'Scopus_'))]
    return achado


def resumo_prisma(caminho):
    """
    PRISMA counts of a _prisma.xlsx, read from its sheets (the screening counts
    are recomputed here, as the Excel formulas have no stored value until Excel opens the file).
    """
    from openpyxl import load_workbook
    wb = load_workbook(caminho, read_only=True)
    identificados, duplicatas, por_base = 0, 0, []
    for estagio, item, n in wb['summary'].iter_rows(min_row=2, values_only=True):
        if item and item.startswith('Records identified from'):
            por_base.append((item.replace('Records identified from ', ''), n))
        elif item == 'Records identified (total)':
            identificados = n
        elif item == 'Duplicate records removed':
            duplicatas = n
    linhas = list(wb['records'].iter_rows(values_only=True))
    wb.close()
    cab, dados = list(linhas[0]), linhas[1:]
    i_dec, i_mot = cab.index('screening_decision'), cab.index('exclusion_reason')
    decisoes = [((d[i_dec] or '').strip().lower(), (d[i_mot] or '').strip()) for d in dados]
    sem_resumo = sum(1 for dec, mot in decisoes if dec == 'exclude' and mot == 'No abstract available')
    return {
        'por_base': por_base, 'identificados': identificados, 'duplicatas': duplicatas,
        'triados': len(dados), 'sem_resumo': sem_resumo,
        'excluidos': sum(1 for dec, _ in decisoes if dec == 'exclude') - sem_resumo,
        'incluidos': sum(1 for dec, _ in decisoes if dec == 'include'),
        'talvez': sum(1 for dec, _ in decisoes if dec == 'maybe'),
        'pendentes': sum(1 for dec, _ in decisoes if dec not in ('include', 'exclude', 'maybe')),
    }


def formato_arquivo(caminho):
    """'PubMed', 'Web of Science', 'Scopus CSV'... for the list of files to merge."""
    nomes = {'WOS': 'Web of Science', 'Scopus': 'Scopus', 'PubMed': 'PubMed'}
    formatos = {'wos_txt': 'Web of Science (plain text)', 'wos_tab': 'Web of Science (tab-delimited)',
                'scopus_csv': 'Scopus CSV', 'scopus_ris': 'Scopus RIS'}
    try:
        from databases.scopus import detectar_formato_scopus
        from databases.wos import detectar_formato, ler_texto
        texto = ler_texto(caminho)
        formato = detectar_formato(texto)
        if formato != 'medline':
            return formatos.get(formato) or formatos.get(detectar_formato_scopus(texto), 'unknown format')
        linhas_db = set(re.findall(r'^DB  - (.+)$', texto, flags=re.M))
        if not linhas_db:
            return 'PubMed'
        bases = {n.strip() for linha in linhas_db for n in linha.split(';')}
        if len(linhas_db) > 1 or len(bases) > 1:
            return 'merged: ' + ', '.join(sorted(nomes.get(b, b) for b in bases))
        return nomes.get(bases.pop(), 'MEDLINE')
    except Exception:
        return 'unreadable'
