"""
PRISMA 2020 flow diagram for new systematic reviews (databases only),
written as prisma_flow.png and prisma_flow.svg.

Identification and title/abstract screening come from the PRISMA table and the
search log. Retrieval, full-text assessment and inclusion happen outside the
tool: their boxes show "n = …", to be completed (the SVG text is editable).
"""
VAZIO = '…'


def _n(valor):
    return VAZIO if valor is None else f"{valor:,}"


def linhas_identificacao(contagens, log):
    """'Records identified from' lines: one per database when the search log says which."""
    if log and log.get('sources'):
        por_base = {}
        for o in log['sources']:
            por_base[o['database']] = por_base.get(o['database'], 0) + o['records']
        itens = list(por_base.items())
    else:
        itens = contagens['por_base']
    total = sum(n for _, n in itens)
    return total, [f"{nome} (n = {_n(n)})" for nome, n in itens]


def desenhar(contagens, log, destino):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.patches import FancyArrowPatch, Rectangle

    total, fontes = linhas_identificacao(contagens, log)
    c = contagens
    excluidos = c['sem_resumo'] + c['excluidos']
    triados = c['triados']

    caixas = {
        'identificados': ['Records identified from*:', f"Databases (n = {_n(total)})"] + ['    ' + f for f in fontes],
        'removidos': ['Records removed before screening:', f"    Duplicate records removed (n = {_n(c['duplicatas'])})",
                      '    Records marked as ineligible by', '    automation tools (n = 0)',
                      '    Records removed for other reasons (n = 0)'],
        'triados': ['Records screened', f"(n = {_n(triados)})"]
                   + ([f"Not yet screened (n = {_n(c['pendentes'])})"] if c['pendentes'] else []),
        'excluidos': [f"Records excluded (n = {_n(excluidos)})",
                      f"    No abstract available (n = {_n(c['sem_resumo'])})",
                      f"    Excluded on title/abstract (n = {_n(c['excluidos'])})"],
        'buscados': ['Reports sought for retrieval', f"(n = {_n(c['incluidos'])})"]
                    + ([f"+ {c['talvez']:,} marked maybe"] if c['talvez'] else []),
        'nao_obtidos': ['Reports not retrieved', f"(n = {VAZIO})"],
        'avaliados': ['Reports assessed for eligibility', f"(n = {VAZIO})"],
        'excl_texto': [f"Reports excluded (n = {VAZIO}):", f"    Reason 1 (n = {VAZIO})",
                       f"    Reason 2 (n = {VAZIO})", f"    Reason 3 (n = {VAZIO})"],
        'incluidos': ['Studies included in review', f"(n = {VAZIO})", 'Reports of included studies', f"(n = {VAZIO})"],
    }
    # x, y (top), width, height in figure units (0-100 wide)
    pos = {
        'identificados': (12, 92, 40, 3.1 + 2.4 * len(caixas['identificados'])),
        'removidos': (58, 92, 40, 15),
        'triados': (12, 66, 40, 9 if not c['pendentes'] else 11),
        'excluidos': (58, 66, 40, 11),
        'buscados': (12, 51, 40, 9 if not c['talvez'] else 11),
        'nao_obtidos': (58, 51, 40, 9),
        'avaliados': (12, 36, 40, 9),
        'excl_texto': (58, 36, 40, 13),
        'incluidos': (12, 17, 40, 13),
    }
    plt.rcParams['svg.fonttype'] = 'none'    # keep the SVG text as text, so it can be edited
    fig = plt.figure(figsize=(10, 11))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 105)
    ax.axis('off')
    tinta, borda, faixa = '#17251C', '#4A5A50', '#D7E7F2'

    ax.add_patch(Rectangle((12, 98.5), 86, 5, facecolor='#F6E7A6', edgecolor=borda, linewidth=1))
    ax.text(55, 101, 'Identification of studies via databases and registers', ha='center', va='center',
            fontsize=12, fontweight='bold', color=tinta)
    for rotulo, (y0, y1) in {'Identification': (77, 96), 'Screening': (24, 75), 'Included': (3, 22)}.items():
        ax.add_patch(Rectangle((2, y0), 7, y1 - y0, facecolor=faixa, edgecolor=borda, linewidth=1))
        ax.text(5.5, (y0 + y1) / 2, rotulo, rotation=90, ha='center', va='center', fontsize=11,
                fontweight='bold', color=tinta)

    def caixa(chave):
        x, topo, w, h = pos[chave]
        ax.add_patch(Rectangle((x, topo - h), w, h, facecolor='white', edgecolor=borda, linewidth=1))
        centro = chave in ('triados', 'buscados', 'nao_obtidos', 'avaliados', 'incluidos')
        for k, linha in enumerate(caixas[chave]):
            ax.text(x + (w / 2 if centro else 1.5), topo - 2.6 - 2.4 * k, linha, fontsize=9.5, color=tinta,
                    ha='center' if centro else 'left', va='center')
        return x, topo, w, h

    def seta(p1, p2):
        ax.add_patch(FancyArrowPatch(p1, p2, arrowstyle='-|>', mutation_scale=12, color=borda, linewidth=1))

    geo = {k: caixa(k) for k in caixas}

    def base(k):
        x, t, w, h = geo[k]
        return x + w / 2, t - h

    def topo(k):
        x, t, w, h = geo[k]
        return x + w / 2, t

    def lado(k, direita=True):
        x, t, w, h = geo[k]
        return (x + w if direita else x), t - h / 2

    for de, para in (('identificados', 'triados'), ('triados', 'buscados'), ('buscados', 'avaliados'),
                     ('avaliados', 'incluidos')):
        seta(base(de), topo(para))
    for de, para in (('identificados', 'removidos'), ('triados', 'excluidos'), ('buscados', 'nao_obtidos'),
                     ('avaliados', 'excl_texto')):
        y = lado(de)[1]
        seta((lado(de)[0], y), (lado(para, direita=False)[0], y))

    ax.text(2, 0.8, '*Records per database, as identified before duplicates were removed. '
                    '"…" marks counts of the full-text stage, to be completed.',
            fontsize=8, color='#5A6A60', va='bottom')
    fig.savefig(destino / 'prisma_flow.png', dpi=300)
    fig.savefig(destino / 'prisma_flow.svg')
    plt.close(fig)
