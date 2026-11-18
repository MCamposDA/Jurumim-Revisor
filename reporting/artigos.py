"""Records of the analysed MEDLINE file, read the same way as the frequency tables."""
import re
from pathlib import Path

from databases.medline import _campos, normalizar_doi


def ler_artigos(caminho, normalizar):
    """
    One dict per record: id, ano (int or None), titulo and resumo (as written),
    ti and ab (normalised like the frequency tables), revista, bases (set of
    databases), doi, tipos (document types), linguas, autor (first author).
    Records are split on PMID- lines, as extrair_artigos does, so their order is
    the same as in the tables.
    """
    texto = Path(caminho).read_text(encoding='utf-8')
    artigos = []
    for bloco in re.split(r'\n(?=PMID-)', texto):
        if not bloco.strip():
            continue
        c = _campos(bloco.strip('\n'))
        ano = re.match(r'\d{4}', (c.get('DP') or [''])[0])
        titulo = ' '.join(c.get('TI', [])).strip()
        bases = {b.strip() for linha in c.get('DB', []) for b in linha.split(';') if b.strip()}
        artigos.append({
            'id': (c.get('PMID') or [''])[0],
            'ano': int(ano.group()) if ano else None,
            'titulo': titulo,
            'ti': normalizar(titulo),
            'ab': normalizar(' '.join(c.get('AB', [])).strip()),
            'revista': (c.get('JT') or c.get('TA') or [''])[0],
            'bases': bases or {'PubMed'},
            'resumo': ' '.join(c.get('AB', [])).strip(),
            'doi': next((normalizar_doi(v[:-5]) for v in c.get('LID', []) + c.get('AID', [])
                         if v.endswith('[doi]')), None),
            'tipos': c.get('PT', []),
            'linguas': c.get('LA', []),
            'autor': (c.get('FAU') or c.get('AU') or [''])[0],
        })
    return artigos
