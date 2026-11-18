"""
Articles and terms per publication year (trends.xlsx, trends.png).

Terms followed: the labels of --ws or of the -st groups when the analysis used
them, otherwise the words found in most articles (stopwords and generic words
left out, as in the network) among those present in at most half of the
articles: words of the search itself are in nearly every article every year.
Besides the number of articles, the share of the year's articles is given (the
literature grows every year, and a raw count would show that growth instead of
the term's own trend); the chart draws it only for years with at least
MIN_ARTIGOS_ANO articles, where a single article does not swing it from 0 to 100%.
"""
from collections import Counter

N_TERMOS = 8
MAX_COBERTURA = 0.5
MIN_ARTIGOS_ANO = 5
MIN_ARTIGOS_INICIO = 15   # the chart starts where every 3-year window has at least this many


def termos_padrao(artigos_por_termo, n_artigos, n=N_TERMOS):
    """Without --lemma, a plural next to its singular (parasite, parasites) is followed once."""
    limite = MAX_COBERTURA * n_artigos
    ordem = sorted(((t, a) for t, a in artigos_por_termo.items() if len(a) <= limite),
                   key=lambda x: (-len(x[1]), x[0]))
    escolhidos = {}
    for t, arts in ordem:
        if t + 's' in escolhidos or (t.endswith('s') and t[:-1] in escolhidos):
            continue
        escolhidos[t] = set(arts)
        if len(escolhidos) == n:
            break
    return escolhidos


def termos_ws(artigos, termos_por_rotulo, compilar_termo):
    """Literal search, as --ws: a label matches an article containing any of its terms."""
    achados = {}
    for rotulo, termos in termos_por_rotulo.items():
        padroes = [compilar_termo(t) for t in termos]
        achados[rotulo] = {i for i, a in enumerate(artigos)
                           if any(p.search(a['ti'].lower()) or p.search(a['ab'].lower()) for p in padroes)}
    return achados


def termos_grupos(grupos, artigos_por_termo, lematizar, normalizar):
    """-st groups: an article counts when it has the standard term or any synonym."""
    achados = {}
    for chave, sinonimos in grupos.items():
        formas = {lematizar(normalizar(t)) for t in [chave] + sinonimos}
        achados[chave] = set().union(*(artigos_por_termo.get(f, set()) for f in formas))
    return achados


def tabela(artigos, termos):
    """
    DataFrames: articles per year, articles with each term per year, share of the
    year's articles (%) and share over 3-year windows (%; the year, the one before
    and the one after), left empty when the window has fewer than MIN_ARTIGOS_ANO articles.
    """
    import pandas as pd

    anos = [a['ano'] for a in artigos if a['ano']]
    if not anos:
        return None, None, None, None
    por_ano = Counter(anos)
    faixa = list(range(min(anos), max(anos) + 1))
    base = pd.DataFrame({'year': faixa, 'articles': [por_ano.get(y, 0) for y in faixa]})
    contagem, parte, janela = (base[['year']].copy() for _ in range(3))
    for termo, indices in termos.items():
        c = Counter(artigos[i]['ano'] for i in indices if artigos[i]['ano'])
        contagem[termo] = [c.get(y, 0) for y in faixa]
        parte[termo] = [round(100 * c.get(y, 0) / por_ano[y], 1) if por_ano.get(y) else None for y in faixa]
        valores = []
        for y in faixa:
            total = sum(por_ano.get(k, 0) for k in (y - 1, y, y + 1))
            com = sum(c.get(k, 0) for k in (y - 1, y, y + 1))
            valores.append(round(100 * com / total, 1) if total >= MIN_ARTIGOS_ANO else None)
        janela[termo] = valores
    sem_ano = sum(1 for a in artigos if not a['ano'])
    if sem_ano:
        base = pd.concat([base, pd.DataFrame([{'year': 'no year', 'articles': sem_ano}])], ignore_index=True)
    return base, contagem, parte, janela


def escrever(base, contagem, parte, janela, destino):
    """
    trends.xlsx with the four tables, and trends.png: articles per year on top,
    then one small panel per term (3-year share), all on the same vertical scale.
    """
    import math

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.ticker
    import matplotlib.pyplot as plt
    import pandas as pd

    with pd.ExcelWriter(destino / 'trends.xlsx', engine='openpyxl') as w:
        base.to_excel(w, sheet_name='articles_per_year', index=False)
        contagem.to_excel(w, sheet_name='terms_articles', index=False)
        parte.to_excel(w, sheet_name='terms_share_percent', index=False)
        janela.to_excel(w, sheet_name='terms_share_3yr_percent', index=False)

    termos = [c for c in janela.columns if c != 'year']
    # The panels start where the 3-year windows stop being sparse: from the first year
    # after which every window has enough articles. Early years with a handful of
    # articles would draw loose fragments (0% or 100%) cut by gaps.
    anos_lista = [int(y) for y in base['year'] if y != 'no year']
    por_ano = dict(zip(anos_lista, [int(v) for v, y in zip(base['articles'], base['year']) if y != 'no year']))
    limite_inicio = MIN_ARTIGOS_INICIO
    for limite_inicio in (MIN_ARTIGOS_INICIO, MIN_ARTIGOS_ANO, 0):     # small searches: lower the bar
        validos = [sum(por_ano.get(y + d, 0) for d in (-1, 0, 1)) >= limite_inicio for y in janela['year']]
        inicio_k = len(validos)
        while inicio_k > 0 and validos[inicio_k - 1]:
            inicio_k -= 1
        if len(validos) - inicio_k >= min(5, len(validos)):
            break
    ano_inicio = int(janela['year'][inicio_k]) if inicio_k < len(janela) else None
    colunas = 4
    linhas = max(1, math.ceil(len(termos) / colunas))
    anos = base[base['year'] != 'no year']
    tinta, suave, grade, cor = '#17251C', '#5A6A60', '#E3E9E4', '#2B7A4B'

    fig = plt.figure(figsize=(11, 3.2 + 2.3 * linhas))
    grid = fig.add_gridspec(1 + linhas, colunas, height_ratios=[1.25] + [1] * linhas, hspace=0.75, wspace=0.18)
    topo = fig.add_subplot(grid[0, :])
    topo.bar(anos['year'].astype(int), anos['articles'], color=cor, width=0.8)
    topo.set_title('Articles per year', loc='left', fontsize=11, color=tinta)
    recorte = janela.iloc[inicio_k:]
    teto = max([v for c in termos for v in recorte[c] if v is not None and v == v] or [1])
    primeiro = None
    for k, termo in enumerate(termos):
        ax = fig.add_subplot(grid[1 + k // colunas, k % colunas], sharex=primeiro, sharey=primeiro)
        primeiro = primeiro or ax
        ax.plot(recorte['year'], recorte[termo], color=cor, linewidth=2)
        ax.set_ylim(0, min(100, teto * 1.1))
        if len(recorte):
            ax.set_xlim(int(recorte['year'].iloc[0]) - 0.5, int(recorte['year'].iloc[-1]) + 0.5)
        ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(4, integer=True))
        ax.set_title(termo, loc='left', fontsize=10, color=tinta)
        if k % colunas:
            ax.tick_params(labelleft=False)
        else:
            ax.set_ylabel('% of articles', fontsize=8, color=suave)
    for ax in fig.axes:
        ax.spines[['top', 'right']].set_visible(False)
        ax.spines[['left', 'bottom']].set_color('#B9C6BD')
        ax.tick_params(colors=suave, labelsize=8)
        ax.grid(axis='y', color=grade, linewidth=0.8)
        ax.set_axisbelow(True)
        if ax is topo:
            ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(8, integer=True))
    desde = (f" Panels start in {ano_inicio}: before it, some 3-year windows have fewer than {limite_inicio} "
             f"articles." if ano_inicio and inicio_k > 0 and limite_inicio else '')
    fig.text(0.01, 0.005, f"Each panel: share of the articles of a 3-year window (the year, the one before and the "
                          f"one after) containing the term.{desde} Values per year: trends.xlsx.",
             fontsize=8, color=suave)
    fig.savefig(destino / 'trends.png', dpi=200, bbox_inches='tight')
    plt.close(fig)
