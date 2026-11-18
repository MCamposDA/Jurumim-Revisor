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
    manter = [d for d in ('include', 'maybe', 'unmarked', 'exclude') if estado.get(f'keep_{d}')]
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


def _arquivos_triagem(estado, problemas, outro=None):
    """Check the files of a screening action: (label, path) pairs plus the PRISMA table."""
    prisma = (estado.get('prisma') or '').strip()
    for rotulo, caminho in ([outro] if outro else []) + [('PRISMA table', prisma)]:
        if not caminho:
            problemas.append(f'Choose the {rotulo}.')
        elif not Path(caminho).is_file():
            problemas.append(f'File not found: {caminho}')
    return prisma


def comando_sugerir(estado):
    """--suggest: default criteria plus the researcher's terms, years and criteria file."""
    problemas = []
    mesclado = (estado.get('mesclado') or '').strip()
    prisma = _arquivos_triagem(estado, problemas, ('merged file', mesclado))
    argv = ['--suggest', mesclado, prisma]
    criterios = (estado.get('criterios') or '').strip()
    if criterios:
        if not Path(criterios).is_file():
            problemas.append(f'Criteria file not found: {criterios}')
        argv += ['--criteria', criterios]
    incluir, excluir = termos_de_texto(estado.get('incluir')), termos_de_texto(estado.get('excluir'))
    if incluir:
        argv += ['--include-terms'] + incluir
    if excluir:
        argv += ['--exclude-terms'] + excluir
    anos = (estado.get('anos') or '').strip()
    if anos:
        if not re.fullmatch(r'(\d{4})?\s*-\s*(\d{4})?', anos) or anos.strip() == '-':
            problemas.append('Years look like 2000-2026, 2000- or -2026.')
        argv += ['--years', anos]
    return _comum(estado, argv), {}, problemas


def comando_importar_ia(estado):
    """--import-suggestions: CSV written by a language model -> ai_* columns."""
    problemas = []
    csv_ia = (estado.get('csv_ia') or '').strip()
    prisma = _arquivos_triagem(estado, problemas, ('suggestions CSV', csv_ia))
    argv = ['--import-suggestions', csv_ia, prisma]
    if (estado.get('modelo_ia') or '').strip():
        argv += ['--ai-model', estado['modelo_ia'].strip()]
    return _comum(estado, argv), {}, problemas


def comando_ia(estado):
    """AI assistant page: prepare the files for the assistant (step 4 analysis + --context) or load its CSV."""
    if estado.get('acao_ia') == 'importar':
        return comando_importar_ia(estado)
    return comando_analise(dict(estado, contexto=True))


def comando_tela_triagem(estado):
    """Screen page: keep the screened records, suggest from criteria, or import AI suggestions."""
    acao = estado.get('acao_triagem') or 'keep'
    if acao == 'suggest':
        return comando_sugerir(estado)
    if acao == 'import':
        return comando_importar_ia(estado)
    return comando_triagem(estado)


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
    _opcoes_relatorio(estado, argv, problemas, so_artigos)
    return _comum(estado, argv), {}, problemas


def _opcoes_relatorio(estado, argv, problemas, so_artigos):
    """--report / --context and the network options (only written when they differ from the default)."""
    relatorio, contexto = estado.get('relatorio'), estado.get('contexto')
    if not (relatorio or contexto):
        return
    if so_artigos:
        problemas.append('The report needs the table name (.xlsx).')
    argv.append('--context' if contexto else '--report')
    if estado.get('relatorio_pt'):
        argv.append('--report-pt')
    for chave, flag, padrao, minimo in (('rede_min', '--net-min', 3, 1), ('rede_max', '--net-max-nodes', 300, 2)):
        valor = str(estado.get(chave) or '').strip()
        if not valor:
            continue
        if not valor.isdigit() or int(valor) < minimo:
            problemas.append(f'{flag} must be a whole number of at least {minimo}.')
        elif int(valor) != padrao:
            argv += [flag, valor]
    if estado.get('rede_genericas'):
        argv.append('--net-keep-generic')


def pasta_relatorio(estado, pasta):
    """<topic folder>/<input name>_report, where --report writes (next to the table)."""
    entrada = (estado.get('entrada') or '').strip()
    return Path(pasta) / (Path(entrada).stem + '_report') if entrada else None


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
    """PRISMA counts of a _prisma.xlsx (see databases/prisma.py: ler_contagens)."""
    from databases.prisma import ler_contagens
    return ler_contagens(caminho)


def resumo_sugestoes(caminho):
    """{'rules': Counter, 'ai': Counter} of the suggestion columns of a _prisma.xlsx (empty when absent)."""
    from collections import Counter
    from openpyxl import load_workbook
    wb = load_workbook(caminho, read_only=True)
    linhas = list(wb['records'].iter_rows(values_only=True))
    wb.close()
    cab = list(linhas[0]) if linhas else []
    saida = {}
    for chave, coluna in (('rules', 'rules_suggestion'), ('ai', 'ai_suggestion')):
        if coluna in cab:
            i = cab.index(coluna)
            saida[chave] = Counter(str(d[i]).strip().lower() for d in linhas[1:] if d[i])
    return saida


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


# =====================================================
# AI assistant page
# =====================================================
REPOSITORIO = 'MCamposDA/Jurumim-Revisor'
SKILL = RAIZ / 'skills' / 'jurumim-review'


def comandos_instalacao():
    """(tool, commands) to install the jurumim-review skill, from GitHub and from this copy."""
    url = f'https://github.com/{REPOSITORIO}'
    return [
        ('Claude Code', [f'claude plugin marketplace add {REPOSITORIO}',
                         'claude plugin install jurumim-revisor@jurumim'],
         [f'claude plugin marketplace add {shlex.quote(str(RAIZ))}',
          'claude plugin install jurumim-revisor@jurumim']),
        ('Gemini CLI', [f'gemini extensions install {url}'],
         [f'gemini extensions link {shlex.quote(str(RAIZ))}']),
        ('Antigravity CLI', [f'agy plugin install {url}'],
         [f'agy plugin install {shlex.quote(str(RAIZ))}']),
    ]


def instrucoes_gem():
    """Instructions of a Gemini Gem, as written in the skill (references/web.md), in one paragraph."""
    try:
        linhas = (SKILL / 'references' / 'web.md').read_text(encoding='utf-8').splitlines()
    except OSError:
        return ''
    bloco, dentro = [], False
    for linha in linhas:
        if linha.startswith('    You help'):
            dentro = True
        if dentro:
            if not linha.startswith('    '):
                break
            bloco.append(linha.strip())
    return ' '.join(bloco)
