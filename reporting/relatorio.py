"""
--report: everything written into <input>_report/ next to the output table.

  network.html              interactive co-occurrence network
  network.xlsx              its nodes and links
  network.graphml           the same network for Cytoscape or Gephi
  trends.xlsx, trends.png   articles and terms per year
  prisma_flow.png / .svg    PRISMA 2020 flow diagram (when the PRISMA table is found)
  methods_en.txt            methods text (methods_pt.txt with --report-pt)
  context/                  with --context: files for a language model (see contexto.py)

The PRISMA table and the search log of a merge are found next to the input:
<merged>.txt, <merged>_screened.txt and <merged>_filled.txt all lead to
<merged>_prisma.xlsx and <merged>_search_log.json.
"""
import re
from pathlib import Path

from . import contexto, metodos, prisma_figura, rede, rede_html, tendencias
from .artigos import ler_artigos


def arquivos_da_mesclagem(entrada):
    """(PRISMA table, search log) of the merge an analysed file comes from, or None."""
    entrada = Path(entrada)
    base = re.sub(r'(_screened|_filled|_no_abstract)+$', '', entrada.stem)
    prisma = entrada.with_name(base + '_prisma.xlsx')
    log = entrada.with_name(base + '_search_log.json')
    return (prisma if prisma.is_file() else None), (log if log.is_file() else None)


def gerar(entrada, saida, opcoes, ferramentas):
    """
    opcoes: minimo, max_nos, manter_genericas, portugues, lemma, extra_stopwords,
            ws (list or None), grupos (dict), contexto (bool).
    ferramentas: normalizar, lematizar, stop (set), compilar_termo.
    Returns the folder written.
    """
    from databases.prisma import ler_contagens
    from databases.registro import ler_log

    destino = Path(saida).resolve().parent / (Path(entrada).stem + '_report')
    destino.mkdir(exist_ok=True)
    artigos = ler_artigos(entrada, ferramentas['normalizar'])
    print(f"\nReport of {len(artigos)} articles -> {destino}")

    # Network
    freq, art_termo, pares, art_par = rede.contar(artigos, ferramentas['stop'], ferramentas['lematizar'],
                                                  opcoes['manter_genericas'])
    G = rede.montar(freq, art_termo, pares, art_par, opcoes['minimo'], opcoes['max_nos'])
    rede_html.escrever(G, artigos, art_termo, destino / 'network.html',
                       {'source': Path(entrada).name, 'min': opcoes['minimo'], 'articles': len(artigos)})
    if G.number_of_nodes():
        rede.tabelas(G, destino)
        print(f"  network: {G.number_of_nodes()} words, {G.number_of_edges()} links "
              f"(pairs seen at least {opcoes['minimo']} times) -> network.html, network.xlsx, network.graphml")
    else:
        print(f"  network: no pair of words appears {opcoes['minimo']} times; lower --net-min")

    # Trends
    if opcoes['ws'] is not None:
        rotulos = {t.lower(): [t] for t in opcoes['ws']}
        rotulos.update({k: [k] + v for k, v in opcoes['grupos'].items()})
        termos = tendencias.termos_ws(artigos, rotulos, ferramentas['compilar_termo'])
    elif opcoes['grupos']:
        termos = tendencias.termos_grupos(opcoes['grupos'], art_termo, ferramentas['lematizar'],
                                          ferramentas['normalizar'])
    else:
        termos = tendencias.termos_padrao(art_termo, len(artigos))
    base, contagem, parte, janela = tendencias.tabela(artigos, termos)
    if base is not None:
        tendencias.escrever(base, contagem, parte, janela, destino)
        print(f"  trends: {len(termos)} terms per year -> trends.xlsx, trends.png")
    else:
        print("  trends: no publication year in the records")

    # PRISMA diagram and methods text
    caminho_prisma, caminho_log = arquivos_da_mesclagem(entrada)
    contagens = ler_contagens(caminho_prisma) if caminho_prisma else None
    if contagens and caminho_prisma:
        contagens.update(sugestoes_do_prisma(caminho_prisma))
    log = ler_log(caminho_log) if caminho_log else None
    if contagens:
        prisma_figura.desenhar(contagens, log, destino)
        print(f"  PRISMA 2020 flow diagram from {caminho_prisma.name} -> prisma_flow.png, prisma_flow.svg")
    else:
        print("  PRISMA flow diagram skipped: no <merged>_prisma.xlsx next to the input "
              "(the input is not the result of --merge or -p --db)")
    analise = {
        'n_articles': len(artigos), 'lemma': opcoes['lemma'], 'extra_stopwords': opcoes['extra_stopwords'],
        'terms': list(termos) if (opcoes['ws'] is not None or opcoes['grupos']) else None,
        'network': {'nodes': G.number_of_nodes(), 'links': G.number_of_edges(), 'min': opcoes['minimo']}
        if G.number_of_nodes() else None,
    }
    linguas = ['en', 'pt'] if opcoes['portugues'] else ['en']
    for lingua in linguas:
        (destino / f'methods_{lingua}.txt').write_text(metodos.texto(lingua, log, contagens, analise),
                                                      encoding='utf-8')
    print(f"  methods text -> {', '.join(f'methods_{l}.txt' for l in linguas)}"
          + ('' if log else ' (no search log found: databases, queries and dates are left in [brackets])'))

    if opcoes.get('contexto'):
        pasta, pendentes = contexto.escrever(destino, entrada, artigos, G, freq, art_termo, art_par, termos,
                                             (base, contagem, parte, janela), contagens, log, caminho_prisma,
                                             analise, opcoes)
        print(f"  context for a language model -> {pasta.name}/ ({len(artigos)} records, "
              f"{pendentes} not yet screened in suggestions_template.csv)")
    return destino


def sugestoes_do_prisma(caminho):
    """How many records have rule-based or AI screening suggestions in the PRISMA table."""
    from openpyxl import load_workbook
    wb = load_workbook(caminho, read_only=True)
    linhas = list(wb['records'].iter_rows(values_only=True))
    wb.close()
    cab = list(linhas[0])
    contar = lambda col: sum(1 for d in linhas[1:] if d[cab.index(col)]) if col in cab else 0  # noqa: E731
    modelos = sorted({str(d[cab.index('ai_model')]) for d in linhas[1:]
                      if 'ai_model' in cab and d[cab.index('ai_model')]})
    return {'sugestoes_regras': contar('rules_suggestion'), 'sugestoes_ia': contar('ai_suggestion'),
            'modelo_ia': ', '.join(modelos)}
