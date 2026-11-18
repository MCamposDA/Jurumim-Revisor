"""
Interactive page of the co-occurrence network (network.html).

A single file with its data, style and script inside: it opens offline in any
browser. The layout is computed in Python (fixed seed), so the same input
always draws the same picture; the page only filters, highlights and zooms.
"""
import json
from datetime import date

# Eight categorical hues in a fixed order, checked for colour-vision deficiency
# (adjacent pairs); communities after the eighth are grey. The legend and the
# highlight on click identify a community without relying on colour alone.
CORES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#6250d6', '#e34948']
MAX_ARTIGOS_POR_TERMO = 30


def _dados(G, artigos, artigos_por_termo, meta):
    nos = sorted(G.nodes, key=lambda t: -G.nodes[t]['frequency'])
    indice = {t: i for i, t in enumerate(nos)}
    usados = {}

    def ref(i):
        if i not in usados:
            usados[i] = len(usados)
        return usados[i]

    lista_nos = []
    for t in nos:
        d = G.nodes[t]
        recentes = sorted(artigos_por_termo[t], key=lambda i: -(artigos[i]['ano'] or 0))[:MAX_ARTIGOS_POR_TERMO]
        lista_nos.append({'t': t, 'f': d['frequency'], 'a': d['articles'], 'c': d['community'],
                          'x': round(d['x'], 4), 'y': round(d['y'], 4),
                          'r': [ref(i) for i in recentes]})
    # ab: times the word of s comes right before the word of t; ba: the other way round
    lista_arestas = []
    for a, b, d in G.edges(data=True):
        a, b = (a, b) if a == d['term_a'] else (b, a)
        lista_arestas.append({'s': indice[a], 't': indice[b], 'w': d['weight'],
                              'ab': d['a_before_b'], 'ba': d['b_before_a']})
    referidos = [None] * len(usados)
    for i, j in usados.items():
        referidos[j] = {'id': artigos[i]['id'], 'y': artigos[i]['ano'], 'ti': artigos[i]['titulo'][:220]}
    comunidades = {}
    for t in nos:
        comunidades.setdefault(G.nodes[t]['community'], []).append(t)
    legenda = [{'c': c, 'n': len(m), 'top': m[:3]} for c, m in sorted(comunidades.items())]
    return {'nodes': lista_nos, 'links': lista_arestas, 'articles': referidos,
            'communities': legenda, 'colors': CORES, 'meta': meta}


def escrever(G, artigos, artigos_por_termo, caminho, meta):
    meta = dict(meta, generated=date.today().isoformat())
    dados = json.dumps(_dados(G, artigos, artigos_por_termo, meta), ensure_ascii=False, separators=(',', ':'))
    html = PAGINA.replace('__TITULO__', _escapar(meta.get('source', 'network'))) \
                 .replace('__DADOS__', dados.replace('</', '<\\/'))
    caminho.write_text(html, encoding='utf-8')


def _escapar(texto):
    return str(texto).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')


PAGINA = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Co-occurrence network · __TITULO__</title>
<style>
  :root {
    --fundo: #EEF2EE; --superficie: #FFFFFF; --tinta: #17251C; --suave: #5A6A60;
    --linha: #CBD6CE; --folha: #2B7A4B; --folha-clara: #DCEDE2; --aresta: #8FA197;
    --ui: "Segoe UI", "SF Pro Text", "Helvetica Neue", "Noto Sans", Ubuntu, "DejaVu Sans", sans-serif;
    --mono: "Cascadia Mono", Consolas, "SF Mono", Menlo, "DejaVu Sans Mono", monospace;
  }
  * { box-sizing: border-box; }
  html, body { height: 100%; margin: 0; }
  body { background: var(--fundo); color: var(--tinta); font: 14px/1.45 var(--ui);
         display: grid; grid-template-rows: auto 1fr; }
  header { display: flex; flex-wrap: wrap; align-items: flex-end; gap: 8px 28px;
           padding: 14px 18px 10px; border-bottom: 1px solid var(--linha); }
  header h1 { font-size: 18px; margin: 0; font-weight: 650; }
  header .fonte { font-family: var(--mono); font-size: 12px; color: var(--suave); }
  .resumo { color: var(--suave); font-size: 13px; font-variant-numeric: tabular-nums; }
  main { display: grid; grid-template-columns: minmax(0, 1fr) 340px; min-height: 0; }
  #palco { position: relative; min-width: 0; min-height: 0; background: var(--superficie); }
  svg { width: 100%; height: 100%; display: block; cursor: grab; touch-action: none; }
  svg.arrastando { cursor: grabbing; }
  line { stroke-linecap: round; stroke-opacity: .28; vector-effect: non-scaling-stroke; }
  line.realce { stroke-opacity: .85; }
  circle { stroke: #FFFFFF; stroke-width: 1; vector-effect: non-scaling-stroke; cursor: pointer;
           transition: opacity .15s; }
  circle.foco { stroke: var(--tinta); stroke-width: 2.5; }
  text.rot, text.grupo { font-family: var(--ui); fill: var(--tinta); pointer-events: none;
                         paint-order: stroke; stroke: rgba(255,255,255,.9); stroke-linejoin: round; }
  text.grupo { font-weight: 700; }
  text.rot.destaque { font-weight: 700; }
  .apagado { opacity: .1; }
  #balao { position: absolute; transform: translate(-50%, -100%); background: var(--tinta); color: #fff;
           font: 12px var(--ui); padding: 3px 8px; border-radius: 4px; pointer-events: none; white-space: nowrap; }
  .ferramentas { position: absolute; left: 12px; top: 12px; display: flex; gap: 6px; }
  .ferramentas button { width: 32px; height: 32px; border: 1px solid var(--linha); background: var(--superficie);
                        color: var(--tinta); font: 16px var(--ui); cursor: pointer; }
  .ferramentas button:hover, .ferramentas button:focus-visible { background: var(--folha-clara); outline: none; }
  aside { border-left: 1px solid var(--linha); overflow-y: auto; padding: 14px 16px 24px;
          display: flex; flex-direction: column; gap: 18px; }
  .rotulo { font-size: 11px; font-weight: 650; letter-spacing: .06em; text-transform: uppercase; color: var(--suave); }
  label.rotulo { display: block; margin-bottom: 4px; }
  input[type=range] { width: 100%; accent-color: var(--folha); }
  input[type=search] { width: 100%; padding: 6px 8px; border: 1px solid var(--linha); font: 14px var(--ui);
                       background: var(--superficie); color: var(--tinta); }
  input[type=search]:focus { outline: 2px solid var(--folha); outline-offset: -1px; }
  .valor { font-variant-numeric: tabular-nums; font-weight: 650; color: var(--folha); }
  #legenda button { display: flex; gap: 8px; align-items: baseline; width: 100%; text-align: left; padding: 4px 6px;
                    border: 0; background: none; color: var(--tinta); font: 13px var(--ui); cursor: pointer; }
  #legenda button:hover, #legenda button.ativo { background: var(--folha-clara); }
  .amostra { width: 10px; height: 10px; border-radius: 50%; flex: none; transform: translateY(1px); }
  #detalhe h2 { font-size: 17px; margin: 2px 0 4px; }
  #detalhe .numeros { color: var(--suave); font-size: 13px; font-variant-numeric: tabular-nums; }
  table { width: 100%; border-collapse: collapse; font-size: 13px; font-variant-numeric: tabular-nums; }
  td { padding: 3px 4px; border-bottom: 1px solid var(--fundo); vertical-align: top; }
  td.n { text-align: right; white-space: nowrap; color: var(--suave); }
  td a { color: inherit; text-decoration: none; border-bottom: 1px dotted var(--suave); cursor: pointer; }
  ol.artigos { padding-left: 18px; margin: 6px 0 0; font-size: 13px; }
  ol.artigos li { margin-bottom: 6px; }
  ol.artigos .id { font-family: var(--mono); font-size: 11px; color: var(--suave); }
  .dica { color: var(--suave); font-size: 13px; }
  .vazio { padding: 40px; color: var(--suave); }
  @media (max-width: 760px) {
    main { grid-template-columns: 1fr; grid-template-rows: 60vh auto; }
    aside { border-left: 0; border-top: 1px solid var(--linha); }
  }
</style>
</head>
<body>
<header>
  <div>
    <h1>Word co-occurrence network</h1>
    <div class="fonte" id="fonte"></div>
  </div>
  <div class="resumo" id="resumo"></div>
</header>
<main>
  <div id="palco">
    <svg id="svg" role="img" aria-label="Network of words that appear side by side"><g id="mundo"><g id="camada-arestas"></g><g id="camada-nos"></g><g id="camada-grupos"></g><g id="camada-rotulos"></g></g></svg>
    <div id="balao" hidden></div>
    <div class="ferramentas">
      <button id="mais" title="Zoom in" aria-label="Zoom in">+</button>
      <button id="menos" title="Zoom out" aria-label="Zoom out">−</button>
      <button id="ajustar" title="Fit the network" aria-label="Fit the network">⤢</button>
    </div>
  </div>
  <aside>
    <div>
      <label class="rotulo" for="minimo">Minimum co-occurrences: <span class="valor" id="minimo-valor"></span></label>
      <input type="range" id="minimo" step="1">
      <div class="dica" id="minimo-dica"></div>
    </div>
    <div>
      <label class="rotulo" for="busca">Find a word</label>
      <input type="search" id="busca" list="termos" placeholder="type a word and press Enter">
      <datalist id="termos"></datalist>
    </div>
    <div id="detalhe"></div>
    <div>
      <div class="rotulo">Groups of words that appear together</div>
      <div id="legenda"></div>
    </div>
  </aside>
</main>
<script>
const D = __DADOS__;
const NS = 'http://www.w3.org/2000/svg';
const $ = id => document.getElementById(id);
const cor = c => c < D.colors.length ? D.colors[c] : '#8A948E';
const fmt = n => n.toLocaleString('en-US');

$('fonte').textContent = D.meta.source + '  ·  ' + D.meta.generated;
if (!D.nodes.length) {
  $('palco').innerHTML = '<div class="vazio">No pair of words reaches ' + D.meta.min +
    ' co-occurrences. Run again with a lower --net-min.</div>';
} else {

// Geometry. Positions come from Python (one island per community). Text keeps the
// same size on screen at any zoom; circles grow slower than the zoom, so zooming in
// opens room between words instead of only enlarging them.
const W = 1000, H = 760, M = 30;
const fmax = Math.max(1, ...D.nodes.map(n => n.f));
const wmax = Math.max(1, ...D.links.map(l => l.w));
const xs = D.nodes.map(n => n.x), ys = D.nodes.map(n => n.y);
const [x0, x1, y0, y1] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
const esc = Math.min((W - 2 * M) / Math.max(x1 - x0, 1e-9), (H - 2 * M) / Math.max(y1 - y0, 1e-9));
const dx = (W - (x1 - x0) * esc) / 2, dy = (H - (y1 - y0) * esc) / 2;
D.nodes.forEach((n, i) => {
  n.i = i; n.px = dx + (n.x - x0) * esc; n.py = dy + (n.y - y0) * esc;
  n.raio = 3 + 15 * Math.sqrt(n.f / fmax); n.viz = new Map();
});
D.links.forEach(l => { D.nodes[l.s].viz.set(l.t, l); D.nodes[l.t].viz.set(l.s, l); });

// Islands: centre, extent and name (two most frequent words) of each community
const ilhas = new Map();
D.nodes.forEach(n => {
  if (!ilhas.has(n.c)) ilhas.set(n.c, {c: n.c, nos: []});
  ilhas.get(n.c).nos.push(n);
});
ilhas.forEach(g => {
  g.cx = g.nos.reduce((s, n) => s + n.px, 0) / g.nos.length;
  g.cy = g.nos.reduce((s, n) => s + n.py, 0) / g.nos.length;
  g.x0 = Math.min(...g.nos.map(n => n.px - n.raio)); g.x1 = Math.max(...g.nos.map(n => n.px + n.raio));
  g.y0 = Math.min(...g.nos.map(n => n.py - n.raio)); g.y1 = Math.max(...g.nos.map(n => n.py + n.raio));
  g.nome = g.nos.slice(0, 2).map(n => n.t).join(' · ');
});

function el(tag, attrs, pai) {
  const e = document.createElementNS(NS, tag);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  pai.appendChild(e);
  return e;
}
const linhas = D.links.map(l => {
  const a = D.nodes[l.s], b = D.nodes[l.t];
  return el('line', {x1: a.px, y1: a.py, x2: b.px, y2: b.py,
                     stroke: a.c === b.c ? cor(a.c) : '#8FA197',
                     'stroke-width': (0.5 + 3.5 * Math.sqrt(l.w / wmax)).toFixed(2)}, $('camada-arestas'));
});
const circulos = D.nodes.map(n => {
  const c = el('circle', {cx: n.px, cy: n.py, r: n.raio.toFixed(1), fill: cor(n.c)}, $('camada-nos'));
  c.addEventListener('click', ev => { ev.stopPropagation(); selecionar(n.i, true); });
  c.addEventListener('pointerenter', () => { sobre = n.i; aplicar(); dica(n); });
  c.addEventListener('pointerleave', () => { sobre = null; aplicar(); $('balao').hidden = true; });
  return c;
});
const rotulos = D.nodes.map(n => {
  const t = el('text', {x: n.px, y: n.py, class: 'rot'}, $('camada-rotulos'));
  t.textContent = n.t;
  return t;
});
const nomesIlhas = [...ilhas.values()].map(g => {
  const t = el('text', {x: g.cx, y: g.cy, class: 'grupo', 'text-anchor': 'middle'}, $('camada-grupos'));
  t.textContent = g.nome;
  t.style.fill = g.c < D.colors.length ? 'var(--tinta)' : 'var(--suave)';
  return [g, t];
});

let minimo = D.meta.min, selecionado = null, comunidade = null, sobre = null, zoom = 1, tx = 0, ty = 0;
const visivelNo = new Array(D.nodes.length).fill(false);
const PERTO = 1.7;     // from this zoom on, words have names; below it, islands do

function dica(n) {
  const b = $('balao');
  b.textContent = n.t + '  ·  ' + fmt(n.f) + ' times in ' + fmt(n.a) + ' articles';
  const p = $('palco').getBoundingClientRect(), r = circulos[n.i].getBoundingClientRect();
  b.style.left = (r.left - p.left + r.width / 2) + 'px';
  b.style.top = (r.top - p.top - 8) + 'px';
  b.hidden = false;
}

function aplicar() {
  visivelNo.fill(false);
  D.links.forEach((l, k) => {
    const v = l.w >= minimo;
    linhas[k].style.display = v ? '' : 'none';
    if (v) { visivelNo[l.s] = true; visivelNo[l.t] = true; }
  });
  const ativo = selecionado !== null ? selecionado : sobre;
  const foco = ativo !== null ? new Set([ativo, ...[...D.nodes[ativo].viz.entries()]
                                         .filter(([, l]) => l.w >= minimo).map(([j]) => j)]) : null;
  const fator = 1 / Math.sqrt(zoom);
  let nos = 0;
  D.nodes.forEach((n, i) => {
    const v = visivelNo[i];
    nos += v;
    const c = circulos[i];
    c.style.display = v ? '' : 'none';
    c.setAttribute('r', (n.raio * fator).toFixed(2));
    const apagado = (foco && !foco.has(i)) || (!foco && comunidade !== null && n.c !== comunidade);
    c.classList.toggle('apagado', !!apagado);
    c.classList.toggle('foco', i === ativo);
  });
  D.links.forEach((l, k) => {
    const ligada = foco ? (l.s === ativo || l.t === ativo)
                        : comunidade === null || (D.nodes[l.s].c === comunidade && D.nodes[l.t].c === comunidade);
    linhas[k].classList.toggle('apagado', !ligada);
    linhas[k].classList.toggle('realce', !!foco && ligada);
  });

  // Names. Focus (a word clicked or under the mouse): only its own name.
  // Otherwise, close up or inside a chosen group: as many names as fit without
  // touching, most frequent first. Far away: the name of each island.
  const tam = 12 / zoom;
  rotulos.forEach(t => { t.style.display = 'none'; t.classList.remove('destaque'); });
  if (foco) {
    const n = D.nodes[ativo], t = rotulos[ativo];
    t.setAttribute('x', n.px); t.setAttribute('y', n.py);
    t.setAttribute('font-size', (16 / zoom).toFixed(3)); t.setAttribute('dx', (n.raio * fator + 4 / zoom).toFixed(3));
    t.setAttribute('dy', (5 / zoom).toFixed(3)); t.style.strokeWidth = (4 / zoom) + 'px';
    t.classList.add('destaque'); t.style.display = '';
  } else if (zoom >= PERTO || comunidade !== null) {
    const ocupado = [];
    let postos = 0;
    for (const n of D.nodes) {            // already ordered by frequency
      if (postos >= 120) break;
      if (!visivelNo[n.i] || (comunidade !== null && n.c !== comunidade)) continue;
      const sx = n.px * zoom + tx, sy = n.py * zoom + ty, r = n.raio * fator * zoom;
      if (sx < -50 || sx > W + 50 || sy < -20 || sy > H + 20) continue;
      const caixa = [sx + r + 2, sy - 8, sx + r + 4 + n.t.length * 6.6, sy + 8];
      if (ocupado.some(o => caixa[0] < o[2] && caixa[2] > o[0] && caixa[1] < o[3] && caixa[3] > o[1])) continue;
      ocupado.push(caixa);
      const t = rotulos[n.i];
      t.setAttribute('x', n.px); t.setAttribute('y', n.py);
      t.setAttribute('font-size', tam.toFixed(3)); t.setAttribute('dx', ((r + 3) / zoom).toFixed(3));
      t.setAttribute('dy', (4 / zoom).toFixed(3)); t.style.strokeWidth = (3 / zoom) + 'px';
      t.style.display = '';
      postos++;
    }
  }
  const longe = !foco && zoom < PERTO && comunidade === null;
  nomesIlhas.forEach(([g, t]) => {
    const algum = g.nos.some(n => visivelNo[n.i]);
    t.style.display = longe && algum ? '' : 'none';
    t.setAttribute('font-size', (13 / zoom).toFixed(3)); t.style.strokeWidth = (4 / zoom) + 'px';
  });

  const ligacoes = D.links.filter(l => l.w >= minimo).length;
  $('minimo-valor').textContent = minimo;
  $('resumo').textContent = fmt(nos) + ' words · ' + fmt(ligacoes) + ' links · ' + fmt(D.meta.articles) +
    ' articles · words side by side at least ' + minimo + ' times';
}

function selecionar(i, mover) {
  selecionado = i; comunidade = null;
  document.querySelectorAll('#legenda button').forEach(b => b.classList.remove('ativo'));
  const n = D.nodes[i];
  const vizinhos = [...n.viz.entries()].filter(([, l]) => l.w >= minimo).sort((a, b) => b[1].w - a[1].w);
  const d = $('detalhe');
  d.innerHTML = '';
  const add = (tag, txt, cls) => { const e = document.createElement(tag); if (txt !== undefined) e.textContent = txt;
                                    if (cls) e.className = cls; d.appendChild(e); return e; };
  add('div', 'Selected word', 'rotulo');
  const h = add('h2', n.t);
  h.style.borderLeft = '6px solid ' + cor(n.c); h.style.paddingLeft = '8px';
  add('div', fmt(n.f) + ' times in ' + fmt(n.a) + ' articles · ' + vizinhos.length + ' words next to it', 'numeros');
  if (vizinhos.length) {
    add('div', 'Words next to it', 'rotulo').style.marginTop = '14px';
    const tab = add('table');
    vizinhos.forEach(([j, l]) => {
      const xy = l.s === i ? l.ab : l.ba, yx = l.s === i ? l.ba : l.ab;
      const tr = tab.insertRow();
      const a = document.createElement('a');
      a.textContent = D.nodes[j].t; a.onclick = () => selecionar(j, true);
      tr.insertCell().appendChild(a);
      const c = tr.insertCell(); c.className = 'n';
      // the usual order of the pair, as it is written in the articles
      c.textContent = (xy >= yx ? '"' + n.t + ' ' + D.nodes[j].t + '"' : '"' + D.nodes[j].t + ' ' + n.t + '"') +
                      '  ' + fmt(l.w) + '×';
      c.title = '"' + n.t + ' ' + D.nodes[j].t + '": ' + xy + ' times; "' + D.nodes[j].t + ' ' + n.t + '": ' + yx + ' times';
    });
  }
  if (n.r.length) {
    add('div', n.a > n.r.length ? 'Articles (' + n.r.length + ' most recent of ' + fmt(n.a) + ')' : 'Articles', 'rotulo')
      .style.marginTop = '14px';
    const ol = add('ol', undefined, 'artigos');
    n.r.forEach(k => {
      const art = D.articles[k], li = document.createElement('li');
      const id = document.createElement('div'); id.className = 'id';
      id.textContent = art.id + (art.y ? '  ·  ' + art.y : '');
      li.appendChild(id); li.appendChild(document.createTextNode(art.ti)); ol.appendChild(li);
    });
  }
  if (mover) irPara(Math.max(zoom, 2.2), n.px, n.py); else aplicar();
}

function limpar() {
  selecionado = null; comunidade = null;
  document.querySelectorAll('#legenda button').forEach(b => b.classList.remove('ativo'));
  $('detalhe').innerHTML = '<div class="dica">Point at a word to see its name; click it for the words next to it ' +
    'and its articles. Click a group below to zoom into it. Drag to move, scroll to zoom, Esc to start over.</div>';
  aplicar();
}

// Legend: each community with its three most frequent words; a click zooms into it
D.communities.forEach(c => {
  const b = document.createElement('button');
  const s = document.createElement('span'); s.className = 'amostra'; s.style.background = cor(c.c);
  b.appendChild(s);
  b.appendChild(document.createTextNode(c.top.join(', ') + (c.n > 3 ? ' (+' + (c.n - 3) + ')' : '')));
  b.onclick = () => {
    const ativo = comunidade === c.c;
    limpar();
    if (ativo) { ajustar(); return; }
    comunidade = c.c; b.classList.add('ativo');
    const g = ilhas.get(c.c);
    const z = Math.min(6, 0.8 * Math.min(W / Math.max(g.x1 - g.x0, 1), H / Math.max(g.y1 - g.y0, 1)));
    irPara(Math.max(1, z), (g.x0 + g.x1) / 2, (g.y0 + g.y1) / 2);
  };
  $('legenda').appendChild(b);
});

// Minimum co-occurrences. The page opens with a value that keeps the picture
// readable (about 600 links at most); the slider goes down to the value of the run.
const faixa = $('minimo');
const pesos = D.links.map(l => l.w).sort((a, b) => b - a);
const inicial = pesos.length > 600 ? Math.max(D.meta.min, pesos[599]) : D.meta.min;
minimo = inicial;
faixa.min = D.meta.min; faixa.max = Math.max(D.meta.min, wmax); faixa.value = inicial;
$('minimo-dica').textContent = (inicial > D.meta.min ? 'Opened at ' + inicial + ' so the picture stays readable; ' +
  'slide left to see every pair (down to ' + D.meta.min + ').' : 'From ' + D.meta.min + ' (the value of the run) to ' +
  wmax + ' (the strongest pair).');
faixa.addEventListener('input', () => { minimo = +faixa.value; aplicar(); });

// Search
D.nodes.forEach(n => { const o = document.createElement('option'); o.value = n.t; $('termos').appendChild(o); });
$('busca').addEventListener('change', ev => {
  const n = D.nodes.find(m => m.t === ev.target.value.trim().toLowerCase());
  if (!n) return;
  if (!visivelNo[n.i]) { minimo = D.meta.min; faixa.value = minimo; aplicar(); }
  selecionar(n.i, true);
});

// Pan, zoom and smooth moves
const svg = $('svg'), mundo = $('mundo');
svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H);
function transformar() { mundo.setAttribute('transform', 'translate(' + tx + ',' + ty + ') scale(' + zoom + ')'); aplicar(); }
function pontoSvg(ev) { const p = svg.createSVGPoint(); p.x = ev.clientX; p.y = ev.clientY;
                        return p.matrixTransform(svg.getScreenCTM().inverse()); }
function ampliar(f, cx, cy) { const z = Math.min(12, Math.max(0.5, zoom * f)); tx = cx - (cx - tx) * z / zoom;
                              ty = cy - (cy - ty) * z / zoom; zoom = z; transformar(); }
let animacao = null;
function irPara(z, px, py) {        // centre the point (px, py) at zoom z, in 400 ms
  const de = {zoom, tx, ty}, para = {zoom: z, tx: W / 2 - px * z, ty: H / 2 - py * z}, t0 = performance.now();
  cancelAnimationFrame(animacao);
  const passo = agora => {
    const k = Math.min(1, (agora - t0) / 400), e = k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2;
    zoom = de.zoom + (para.zoom - de.zoom) * e; tx = de.tx + (para.tx - de.tx) * e; ty = de.ty + (para.ty - de.ty) * e;
    transformar();
    if (k < 1) animacao = requestAnimationFrame(passo);
  };
  animacao = requestAnimationFrame(passo);
}
function ajustar() { irPara(1, W / 2, H / 2); }
svg.addEventListener('wheel', ev => { ev.preventDefault(); cancelAnimationFrame(animacao); const p = pontoSvg(ev);
                                      ampliar(ev.deltaY < 0 ? 1.15 : 1 / 1.15, p.x, p.y); }, {passive: false});
let arrasto = null;
svg.addEventListener('pointerdown', ev => { if (ev.target.tagName === 'circle') return;
                                            cancelAnimationFrame(animacao);
                                            arrasto = {p: pontoSvg(ev), tx, ty, moveu: false};
                                            svg.setPointerCapture(ev.pointerId); svg.classList.add('arrastando'); });
svg.addEventListener('pointermove', ev => { if (!arrasto) return; const p = pontoSvg(ev);
  tx = arrasto.tx + p.x - arrasto.p.x; ty = arrasto.ty + p.y - arrasto.p.y;
  arrasto.moveu = arrasto.moveu || Math.abs(p.x - arrasto.p.x) + Math.abs(p.y - arrasto.p.y) > 3; transformar(); });
svg.addEventListener('pointerup', () => { if (arrasto && !arrasto.moveu) limpar();
                                          arrasto = null; svg.classList.remove('arrastando'); });
$('mais').onclick = () => ampliar(1.4, W / 2, H / 2);
$('menos').onclick = () => ampliar(1 / 1.4, W / 2, H / 2);
$('ajustar').onclick = () => { limpar(); ajustar(); };
document.addEventListener('keydown', ev => { if (ev.key === 'Escape') { limpar(); ajustar(); } });

limpar();
transformar();
}
</script>
</body>
</html>
"""
