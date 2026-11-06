import hashlib
import re
import unicodedata
from pathlib import Path


# =====================================================
# Record shared by all sources
# =====================================================
class Registro:
    """
    One article from any source.

    PubMed records keep their original text untouched (`bloco`); records from
    other sources are a list of (tag, value) pairs in MEDLINE order (`linhas`).
    `extras` are tags added later (DB, UT, TC, EID, TCSC of a duplicate that was merged in).
    ut / tc are the WoS ID and times cited; eid / tc_scopus the Scopus ones.
    """

    def __init__(self, fonte, id, bloco=None, linhas=None,
                 pmid=None, doi=None, titulo='', ano=None, ut=None, tc=None,
                 eid=None, tc_scopus=None):
        self.fonte = fonte
        self.id = id
        self.bloco = bloco
        self.linhas = linhas or []
        self.pmid = pmid
        self.doi = normalizar_doi(doi)
        self.titulo = titulo
        self.ano = ano
        self.ut = ut
        self.tc = tc
        self.eid = eid
        self.tc_scopus = tc_scopus
        self.fontes = [fonte]
        self.extras = []

    def to_medline(self):
        extras = [('DB', '; '.join(self.fontes))] + self.extras
        if self.bloco is not None:
            linhas = [self.bloco.rstrip('\n')]
        else:
            linhas = [formatar_tag('PMID', self.id)] + [formatar_tag(t, v) for t, v in self.linhas]
        return '\n'.join(linhas + [formatar_tag(t, v) for t, v in extras])


def id_sem_identificador(prefixo, *partes):
    """
    ID for a record with no PMID, WoS UT or Scopus EID: prefix + a hash of its
    title, year, first author and journal. The same record always gets the same
    ID, so re-running a merge keeps the PRISMA record_id of every article.
    """
    chave = '|'.join(chave_titulo(str(p)) for p in partes)
    return f"{prefixo}NOID{hashlib.sha1(chave.encode('utf-8')).hexdigest()[:12]}"


def garantir_ids_unicos(registros):
    """
    Records left with the same ID (e.g. two "Editorial" items without any ID,
    whose titles are too short to be compared) get _2, _3... The ID is the key
    of the PRISMA table, --screen, the ./PMID folders and the viewer.
    """
    vistos = {}
    for r in registros:
        n = vistos.get(r.id, 0) + 1
        vistos[r.id] = n
        if n > 1:
            novo = f"{r.id}_{n}"
            if r.bloco is not None:
                r.bloco = re.sub(r'^PMID- *\S+', f'PMID- {novo}', r.bloco, count=1)
            r.id = novo
    return registros


def formatar_tag(tag, valor):
    """'FAU', 'Silva, Maria' -> 'FAU - Silva, Maria' (one line; MEDLINE readers accept long lines)."""
    valor = re.sub(r'\s+', ' ', str(valor)).strip()
    return f"{tag:<4}- {valor}"


def escrever_medline(registros, destino):
    texto = '\n\n'.join(r.to_medline() for r in registros) + '\n'
    Path(destino).write_text(texto, encoding='utf-8')


# =====================================================
# Keys used for duplicate detection
# =====================================================
def normalizar_doi(doi):
    if not doi:
        return None
    doi = doi.strip().lower()
    doi = re.sub(r'^(https?://)?(dx\.)?doi\.org/', '', doi)
    doi = re.sub(r'^doi:\s*', '', doi)
    return doi.rstrip('.') or None


def chave_titulo(titulo):
    """
    Title reduced to lowercase letters and digits, accents removed.
    PubMed brackets translated titles ("[Title].") and WoS sometimes writes them
    in upper case; both differences disappear here.
    """
    t = unicodedata.normalize('NFKD', titulo or '')
    t = ''.join(c for c in t if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]', '', t.lower())


# =====================================================
# PubMed (MEDLINE) files
# =====================================================
def ler_medline(texto):
    """Split a MEDLINE file into Registro objects, keeping each block's text as is."""
    registros = []
    for bloco in re.split(r'\n(?=PMID-)', texto.replace('\r\n', '\n')):
        bloco = bloco.strip('\n')
        if not bloco.strip() or not bloco.startswith('PMID-'):
            continue
        campos = _campos(bloco)
        pmid = campos.get('PMID', [''])[0]
        doi = None
        for v in campos.get('LID', []) + campos.get('AID', []):
            if v.endswith('[doi]'):
                doi = v[:-5].strip()
                break
        ano = re.match(r'\d{4}', campos.get('DP', [''])[0])
        r = Registro('PubMed', pmid, bloco=bloco, pmid=pmid if pmid.isdigit() else None,
                     doi=doi, titulo=' '.join(campos.get('TI', [])),
                     ano=int(ano.group()) if ano else None)
        # A MEDLINE file written by a previous merge already has DB/UT/TC lines
        if 'DB' in campos:
            r.bloco = '\n'.join(l for l in bloco.split('\n') if not l.startswith('DB  -'))
            r.fontes = [f.strip() for f in campos['DB'][0].split(';') if f.strip()]
            r.fonte = r.fontes[0]
        r.ut = (campos.get('UT') or [None])[0]
        r.tc = (campos.get('TC') or [None])[0]
        r.eid = (campos.get('EID') or [None])[0]
        r.tc_scopus = (campos.get('TCSC') or [None])[0]
        registros.append(r)
    return registros


def _campos(bloco):
    campos = {}
    chave = None
    for linha in bloco.split('\n'):
        if len(linha) >= 6 and linha[4:6] == '- ':
            chave = linha[:4].strip()
            campos.setdefault(chave, []).append(linha[6:].strip())
        elif linha.startswith('      ') and chave:
            campos[chave][-1] += ' ' + linha.strip()
    return campos
