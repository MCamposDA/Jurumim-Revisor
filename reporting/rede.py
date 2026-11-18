"""
Word co-occurrence network.

Each title and abstract is read as a sequence of tokens, tokenised as in the
frequency table. For every token, the token right before it and the one right
after it are counted. A pair is dropped when either side is a stopword (NLTK
and -sw), a generic word of scientific writing (RUIDO), a single letter or not
a word at all (punctuation, numbers), so a link only joins two words that
appear side by side. Sentence ends, commas and the boundary between title and
abstract break the sequence, since punctuation is never a word.

Node size: frequency (occurrences in titles and abstracts). Link weight: number
of times the two words appear side by side, in either order. Links below a
minimum weight (--net-min) are left out, and the --net-max-nodes most frequent
words of what remains are kept. Communities (Louvain) give each node a colour.
"""
import re
from collections import Counter, defaultdict

from nltk.tokenize import word_tokenize

# Words of scientific writing that link to everything: section headings of
# structured abstracts and filler verbs or adverbs. --net-keep-generic keeps them.
RUIDO = {
    'abstract', 'aim', 'aims', 'background', 'conclusion', 'conclusions', 'discussion',
    'findings', 'introduction', 'method', 'methods', 'methodology', 'objective', 'objectives',
    'purpose', 'result', 'results', 'summary',
    'al', 'also', 'although', 'among', 'based', 'could', 'et', 'fig', 'figure', 'first',
    'found', 'however', 'including', 'may', 'might', 'new', 'one', 'respectively', 'second',
    'show', 'showed', 'shown', 'shows', 'studies', 'study', 'therefore', 'thus', 'three',
    'total', 'two', 'use', 'used', 'using', 'well', 'whereas', 'within', 'would',
    # reporting verbs and connectives
    'according', 'compared', 'considered', 'demonstrate', 'demonstrated', 'demonstrates', 'described',
    'determined', 'due', 'evaluated', 'followed', 'indicate', 'indicated', 'indicates', 'investigated',
    'obtained', 'observed', 'performed', 'present', 'presented', 'regarding', 'report', 'reported',
    'reports', 'revealed', 'several', 'suggest', 'suggested', 'suggests', 'various', 'work',
    # Portuguese and Spanish function words left by place names ("Rio de Janeiro",
    # "Mato Grosso do Sul") and by abstracts in those languages
    'da', 'das', 'de', 'del', 'do', 'dos', 'el', 'la', 'las', 'los',
}


def sequencia(texto, stop, lematizar, manter_genericas=False):
    """Tokens of one text in order; None marks a token that cannot be part of a pair."""
    tokens = word_tokenize(re.sub(r"[/'‘’]", ' ', texto.lower()), language='english')
    saida = []
    for t in tokens:
        if not t.isalpha() or len(t) < 2 or t in stop or (not manter_genericas and t in RUIDO):
            saida.append(None)
            continue
        lema = lematizar(t)
        saida.append(None if lema in stop or (not manter_genericas and lema in RUIDO) else lema)
    return saida


def contar(artigos, stop, lematizar, manter_genericas=False):
    """
    Frequencies and adjacent pairs over all records.
    Returns (freq, artigos_por_termo, pares, artigos_por_par), where pares[(a, b)]
    counts a right before b and artigos_* hold record indices.
    """
    freq, pares = Counter(), Counter()
    artigos_por_termo, artigos_por_par = defaultdict(set), defaultdict(set)
    for i, art in enumerate(artigos):
        for texto in (art['ti'], art['ab']):
            seq = sequencia(texto, stop, lematizar, manter_genericas)
            for t in seq:
                if t:
                    freq[t] += 1
                    artigos_por_termo[t].add(i)
            for a, b in zip(seq, seq[1:]):
                if a and b and a != b:
                    pares[(a, b)] += 1
                    artigos_por_par[frozenset((a, b))].add(i)
    return freq, artigos_por_termo, pares, artigos_por_par


def montar(freq, artigos_por_termo, pares, artigos_por_par, minimo=3, max_nos=300):
    """networkx graph of the pairs seen at least `minimo` times, with layout and communities."""
    import networkx as nx

    ligacoes = defaultdict(lambda: [0, 0])          # {a, b} -> [a before b, b before a]
    for (a, b), n in pares.items():
        chave = tuple(sorted((a, b)))
        ligacoes[chave][0 if (a, b) == chave else 1] += n
    fortes = {k: v for k, v in ligacoes.items() if sum(v) >= minimo}

    termos = Counter()
    for a, b in fortes:
        termos[a] = freq[a]
        termos[b] = freq[b]
    manter = {t for t, _ in sorted(termos.items(), key=lambda x: (-x[1], x[0]))[:max_nos]}

    G = nx.Graph()
    for t in sorted(manter):
        G.add_node(t, frequency=freq[t], articles=len(artigos_por_termo[t]))
    for (a, b), (ab, ba) in sorted(fortes.items()):
        if a in manter and b in manter:
            G.add_edge(a, b, weight=ab + ba, term_a=a, a_before_b=ab, b_before_a=ba,
                       articles=len(artigos_por_par[frozenset((a, b))]))
    G.remove_nodes_from([n for n in list(G.nodes) if G.degree(n) == 0])
    if G.number_of_nodes() == 0:
        return G

    comunidades = nx.community.louvain_communities(G, weight='weight', seed=7)
    # largest community first, so colours keep the same order between runs
    for c, membros in enumerate(sorted(comunidades, key=lambda m: (-len(m), sorted(m)[0]))):
        for t in membros:
            G.nodes[t]['community'] = c
    for t in G.nodes:
        G.nodes[t]['degree'] = G.degree(t)
        G.nodes[t]['strength'] = G.degree(t, weight='weight')
    for t, (x, y) in posicoes(G).items():
        G.nodes[t]['x'], G.nodes[t]['y'] = float(x), float(y)
    return G


def posicoes(G):
    """
    Layout by communities, with a fixed seed. Each community is laid out on its own
    (force layout, link weights as log(1 + weight) so a few very strong pairs do not
    collapse it) and fitted in a circle whose area grows with its number of words.
    The circles are then placed with a force layout of the communities themselves
    (communities with more links between them end up closer) and pushed apart until
    none overlaps. A single force layout of the whole graph gives a tangle where
    groups and labels cannot be told apart.
    """
    import math

    import networkx as nx

    for a, b, d in G.edges(data=True):
        d['_forca'] = math.log1p(d['weight'])
    grupos = defaultdict(list)
    for n, d in G.nodes(data=True):
        grupos[d['community']].append(n)

    # 1. Inside each community, centred on 0 and fitted in radius sqrt(n)
    locais, raios = {}, {}
    for c, nos in grupos.items():
        nos = sorted(nos)
        sub = G.subgraph(nos)
        if len(nos) > 2:
            local = nx.spring_layout(sub, weight='_forca', seed=7, iterations=300, k=1.6 / math.sqrt(len(nos)))
        else:
            local = {n: (i - (len(nos) - 1) / 2, 0.0) for i, n in enumerate(nos)}
        cx = sum(p[0] for p in local.values()) / len(local)
        cy = sum(p[1] for p in local.values()) / len(local)
        alcance = max(math.hypot(x - cx, y - cy) for x, y in local.values()) or 1.0
        raio = math.sqrt(len(nos))
        locais[c] = {n: ((x - cx) / alcance * raio, (y - cy) / alcance * raio) for n, (x, y) in local.items()}
        raios[c] = raio + 0.6

    # 2. Where each community goes: force layout of the communities, then no overlaps
    CG = nx.Graph()
    CG.add_nodes_from(grupos)
    for a, b, d in G.edges(data=True):
        ca, cb = G.nodes[a]['community'], G.nodes[b]['community']
        if ca != cb:
            peso = CG.get_edge_data(ca, cb, {'w': 0})['w'] + d['weight']
            CG.add_edge(ca, cb, w=peso)
    for a, b, d in CG.edges(data=True):
        d['w'] = math.log1p(d['w'])
    if len(grupos) > 1:
        bruto = nx.spring_layout(CG, weight='w', seed=7, iterations=300)
    else:
        bruto = {c: (0.0, 0.0) for c in grupos}
    escala = math.sqrt(sum(r * r for r in raios.values())) * 1.1
    centros = {c: [bruto[c][0] * escala, bruto[c][1] * escala] for c in grupos}
    ordem = sorted(grupos)
    for volta in range(600):
        moveu = False
        for i, a in enumerate(ordem):
            for b in ordem[i + 1:]:
                dx, dy = centros[b][0] - centros[a][0], centros[b][1] - centros[a][1]
                dist = math.hypot(dx, dy)
                if dist < 1e-9:
                    dx, dy, dist = 1e-3 * (i + 1), 1e-3, 1.5e-3 * (i + 1)
                falta = raios[a] + raios[b] + 0.8 - dist
                if falta > 0:
                    ux, uy = dx / dist, dy / dist
                    centros[a][0] -= ux * falta / 2
                    centros[a][1] -= uy * falta / 2
                    centros[b][0] += ux * falta / 2
                    centros[b][1] += uy * falta / 2
                    moveu = True
        if volta < 400:          # a pull towards the middle keeps the islands together
            mx = sum(p[0] for p in centros.values()) / len(centros)
            my = sum(p[1] for p in centros.values()) / len(centros)
            for p in centros.values():
                p[0] -= (p[0] - mx) * 0.03
                p[1] -= (p[1] - my) * 0.03
        elif not moveu:
            break

    for a, b, d in G.edges(data=True):
        del d['_forca']
    return {n: (centros[c][0] + x, centros[c][1] + y) for c, local in locais.items() for n, (x, y) in local.items()}


def tabelas(G, destino):
    """network.xlsx (nodes, links) and network.graphml (Cytoscape, Gephi)."""
    import networkx as nx
    import pandas as pd

    nos = pd.DataFrame([{'term': t, 'frequency': d['frequency'], 'articles': d['articles'],
                         'degree': d['degree'], 'strength': d['strength'], 'community': d['community'] + 1}
                        for t, d in G.nodes(data=True)],
                       columns=['term', 'frequency', 'articles', 'degree', 'strength', 'community'])
    nos = nos.sort_values(['frequency', 'term'], ascending=[False, True])
    arestas = pd.DataFrame([{'term_a': d['term_a'], 'term_b': b if a == d['term_a'] else a,
                             'cooccurrences': d['weight'], 'a_before_b': d['a_before_b'],
                             'b_before_a': d['b_before_a'], 'articles': d['articles']}
                            for a, b, d in G.edges(data=True)],
                           columns=['term_a', 'term_b', 'cooccurrences', 'a_before_b', 'b_before_a', 'articles'])
    arestas = arestas.sort_values(['cooccurrences', 'term_a'], ascending=[False, True])
    with pd.ExcelWriter(destino / 'network.xlsx', engine='openpyxl') as w:
        nos.to_excel(w, sheet_name='nodes', index=False)
        arestas.to_excel(w, sheet_name='links', index=False)
    nx.write_graphml(G, destino / 'network.graphml')
    return nos, arestas
