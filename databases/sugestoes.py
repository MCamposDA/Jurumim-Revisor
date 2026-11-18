"""
Screening suggestions written into the PRISMA table, never into screening_decision.

Rule-based (--suggest): default criteria valid for any topic, plus the
researcher's own (a criteria file and/or flags). Columns: rules_suggestion,
rules_reason, rules_score.

AI (--import-suggestions): a CSV written by a language model following the
jurumim-review skill. Columns: ai_suggestion, ai_reason, ai_evidence, ai_model.

The columns are added after the existing ones, so the screening formulas of
the summary sheet keep pointing at the same cells.
"""
import csv
import re
from pathlib import Path

from .medline import _campos

DECISOES = ('include', 'exclude', 'maybe')

# Default criteria, for any topic. Document types are matched as words inside the
# PubMed PT, WoS DT or Scopus Document Type values.
TIPOS_EXCLUIR = ['erratum', 'correction', 'retraction', 'retracted publication', 'editorial', 'comment',
                 'letter', 'news', 'biography', 'biographical-item', 'obituary', 'interview',
                 'meeting abstract', 'note', 'book review', 'conference review']
TIPOS_TALVEZ = ['review', 'meta-analysis']
INGLES = {'eng', 'english', 'en'}

MODELO_CRITERIOS = """# Screening criteria for Jurumim Revisor (--suggest MERGED.txt PRISMA.xlsx --criteria THIS_FILE)
# One criterion per line, "name: values". Lines starting with # are ignored.
# Terms are matched literally in title and abstract, as --ws does (case and hyphen
# variants ignored; whole words only).

# At least one of these terms must appear, otherwise "exclude":
include:

# Any of these terms gives "exclude":
exclude:

# Publication years kept (e.g. 2000-2026):
years:

# Document types to exclude, besides the default ones
# (erratum, correction, retraction, editorial, comment, letter, news, note, ...):
exclude types:

# Document types that should not get the default "exclude" (e.g. letter, note):
keep types:

# Languages kept without "maybe" (default: English):
languages:
"""


def ler_criterios(caminho=None, incluir=None, excluir=None, anos=None):
    """Criteria from a file and/or flags (flags are added to the file's values)."""
    c = {'include': [], 'exclude': [], 'years': None, 'exclude types': [], 'keep types': [], 'languages': []}
    if caminho:
        for n, linha in enumerate(Path(caminho).read_text(encoding='utf-8').splitlines(), 1):
            linha = linha.strip()
            if not linha or linha.startswith('#'):
                continue
            if ':' not in linha:
                raise ValueError(f"{caminho}, line {n}: expected 'name: values'")
            nome, valor = (p.strip() for p in linha.split(':', 1))
            nome = nome.lower()
            if nome not in c:
                raise ValueError(f"{caminho}, line {n}: unknown criterion '{nome}' "
                                 f"(use: {', '.join(c)})")
            if nome == 'years':
                c['years'] = valor or None
            else:
                c[nome] += [v.strip() for v in valor.split(',') if v.strip()]
    c['include'] += incluir or []
    c['exclude'] += excluir or []
    c['years'] = anos or c['years']
    if c['years']:
        m = re.fullmatch(r'\s*(\d{4})?\s*-\s*(\d{4})?\s*', c['years'])
        if not m or not (m.group(1) or m.group(2)):
            raise ValueError(f"years must look like 2000-2026, 2000- or -2026, not '{c['years']}'")
        c['years'] = (int(m.group(1)) if m.group(1) else None, int(m.group(2)) if m.group(2) else None)
    return c


def _tem_tipo(tipos, lista):
    texto = ' ; '.join(tipos).lower()
    return [t for t in lista if re.search(r'(?<![a-z])' + re.escape(t) + r'(?![a-z])', texto)]


def avaliar(campos, criterios, compilar_termo, normalizar):
    """(suggestion, reason, score) of one record."""
    texto = (normalizar(' '.join(campos.get('TI', []))) + ' ' + normalizar(' '.join(campos.get('AB', [])))).lower()
    tipos = campos.get('PT', [])
    motivos_excluir, motivos_talvez, achados = [], [], []

    if not ''.join(campos.get('AB', [])).strip():
        motivos_excluir.append('no abstract')
    manter = [t.lower() for t in criterios['keep types']]
    for t in _tem_tipo(tipos, [x for x in TIPOS_EXCLUIR if x not in manter] +
                       [x.lower() for x in criterios['exclude types']]):
        motivos_excluir.append(f"document type: {t}")
    for t in _tem_tipo(tipos, [x for x in TIPOS_TALVEZ if x not in manter]):
        motivos_talvez.append(f"document type: {t} (secondary study)")

    ano = re.match(r'\d{4}', (campos.get('DP') or [''])[0])
    if criterios['years'] and ano:
        inicio, fim = criterios['years']
        a = int(ano.group())
        if (inicio and a < inicio) or (fim and a > fim):
            motivos_excluir.append(f"year {a} outside {inicio or ''}-{fim or ''}")

    idiomas = [l.lower() for l in campos.get('LA', [])]
    aceitos = {l.lower() for l in criterios['languages']} or INGLES
    if criterios['languages'] and 'english' in aceitos:
        aceitos |= INGLES
    if idiomas and not any(l in aceitos for l in idiomas):
        motivos_talvez.append(f"language: {', '.join(campos.get('LA', []))}")

    for termo in criterios['exclude']:
        if compilar_termo(termo).search(texto):
            motivos_excluir.append(f"exclusion term: {termo}")
    for termo in criterios['include']:
        if compilar_termo(termo).search(texto):
            achados.append(termo)
    if criterios['include'] and not achados:
        motivos_excluir.append('no inclusion term')

    if motivos_excluir:
        return 'exclude', '; '.join(motivos_excluir + motivos_talvez), -len(motivos_excluir)
    if motivos_talvez:
        return 'maybe', '; '.join(motivos_talvez + ([f"inclusion terms: {', '.join(achados)}"] if achados else [])), \
            len(achados)
    if achados:
        return 'include', f"inclusion terms: {', '.join(achados)}", len(achados)
    return '', 'no rule applies', 0


def blocos_do_mesclado(mesclado):
    """{record_id: MEDLINE fields} of the merged file and its _no_abstract.txt."""
    blocos = {}
    caminhos = [Path(mesclado), Path(mesclado).with_name(Path(mesclado).stem + '_no_abstract.txt')]
    for caminho in caminhos:
        if not caminho.is_file():
            continue
        for bloco in re.split(r'\n(?=PMID-)', caminho.read_text(encoding='utf-8')):
            if bloco.strip():
                c = _campos(bloco.strip('\n'))
                blocos[(c.get('PMID') or [''])[0]] = c
    return blocos


def gravar_colunas(prisma, valores, colunas):
    """
    Write {record_id: [value, ...]} into `colunas` of the records sheet (created at
    the end when missing). Rows not in `valores` are emptied. Returns (written, ids not found).
    """
    from openpyxl import load_workbook
    wb = load_workbook(prisma)
    ws = wb['records']
    cab = [c.value for c in ws[1]]
    if 'record_id' not in cab:
        raise ValueError(f"{prisma} has no record_id column; use the _prisma.xlsx written by --merge")
    indices = []
    for nome in colunas:
        if nome not in cab:
            cab.append(nome)
            ws.cell(1, len(cab), nome)
            ws.column_dimensions[ws.cell(1, len(cab)).column_letter].width = 16 if 'reason' not in nome \
                and 'evidence' not in nome else 48
        indices.append(cab.index(nome) + 1)
    i_id = cab.index('record_id') + 1
    vistos = set()
    for linha in range(2, ws.max_row + 1):
        rid = str(ws.cell(linha, i_id).value or '').strip()
        rid = re.sub(r'\.0$', '', rid)
        dados = valores.get(rid)
        if dados is not None:
            vistos.add(rid)
        for col, v in zip(indices, dados or [None] * len(indices)):
            ws.cell(linha, col, v)
    wb.save(prisma)
    return len(vistos), sorted(set(valores) - vistos)


def sugerir(mesclado, prisma, criterios, compilar_termo, normalizar):
    blocos = blocos_do_mesclado(mesclado)
    valores, contagem = {}, {'include': 0, 'exclude': 0, 'maybe': 0, '': 0}
    for rid, campos in blocos.items():
        sugestao, motivo, pontos = avaliar(campos, criterios, compilar_termo, normalizar)
        valores[rid] = [sugestao or None, motivo, pontos]
        contagem[sugestao] += 1
    gravados, fora = gravar_colunas(prisma, valores, ['rules_suggestion', 'rules_reason', 'rules_score'])
    return contagem, gravados, fora


COLUNAS_IA = ['record_id', 'suggestion', 'reason', 'evidence']


def importar_ia(csv_caminho, prisma, modelo=None):
    """AI suggestions CSV -> ai_* columns. Returns (counts, written, ids not found, problems)."""
    with open(csv_caminho, newline='', encoding='utf-8-sig') as f:
        amostra = f.read(4096)
        f.seek(0)
        try:    # Excel in some languages (Portuguese included) saves CSV with ';'
            dialeto = csv.Sniffer().sniff(amostra, delimiters=',;\t')
        except csv.Error:
            dialeto = csv.excel
        leitor = csv.DictReader(f, dialect=dialeto)
        cab = [c.strip().lower() for c in (leitor.fieldnames or [])]
        faltam = [c for c in COLUNAS_IA[:2] if c not in cab]
        if faltam:
            raise ValueError(f"{csv_caminho} lacks the column(s) {', '.join(faltam)} "
                             f"(expected: {', '.join(COLUNAS_IA)}, model)")
        linhas = [{k.strip().lower(): (v or '').strip() for k, v in l.items() if k} for l in leitor]
    valores, problemas, contagem = {}, [], {'include': 0, 'exclude': 0, 'maybe': 0}
    for n, l in enumerate(linhas, 2):
        rid, s = re.sub(r'\.0$', '', l.get('record_id', '')), l.get('suggestion', '').lower()
        if not rid:
            problemas.append(f"line {n}: no record_id")
            continue
        if s not in DECISOES:
            problemas.append(f"line {n} ({rid}): suggestion '{s}' is not include/exclude/maybe")
            continue
        valores[rid] = [s, l.get('reason') or None, l.get('evidence') or None, l.get('model') or modelo or None]
    gravados, fora = gravar_colunas(prisma, valores, ['ai_suggestion', 'ai_reason', 'ai_evidence', 'ai_model'])
    ausentes = set(fora)
    for rid, v in valores.items():
        if rid not in ausentes:
            contagem[v[0]] += 1
    return contagem, gravados, fora, problemas
