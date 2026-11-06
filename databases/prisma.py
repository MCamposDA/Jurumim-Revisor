"""
PRISMA workbook written by --merge and --db.

Sheets:
  summary              PRISMA 2020 identification and screening counts
  records              one row per unique article, with its IDs in each database
                       and empty screening columns to fill in
  duplicates_removed   every record removed as a duplicate and the key that matched

The screening counts in 'summary' are Excel formulas over the 'records' sheet,
so they update while the screening_decision column is filled in.

Records without abstract (not analysed, written to <merged>_no_abstract.txt)
come pre-marked: screening_decision = exclude, exclusion_reason = SEM_RESUMO.
Changing a decision to include brings the record back with --screen.
"""
from collections import Counter

import pandas as pd
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation

from .medline import _campos

COLUNAS_REGISTROS = ['record_id', 'pmid', 'wos_ut', 'scopus_eid', 'doi',
                     'in_pubmed', 'in_wos', 'in_scopus', 'databases',
                     'title', 'first_author', 'year', 'journal', 'document_type', 'has_abstract',
                     'abstract_source', 'times_cited_wos', 'times_cited_scopus',
                     'screening_decision', 'exclusion_reason', 'notes']
COLUNAS_DUPLICATAS = ['removed_source', 'removed_id', 'kept_source', 'kept_id',
                      'matched_on', 'title', 'removed_doi', 'kept_doi']
DECISOES = ['include', 'exclude', 'maybe']
SEM_RESUMO = 'No abstract available'


def _inteiro(valor):
    return int(valor) if valor and str(valor).isdigit() else ''


def linha_registro(r, sem_resumo=False):
    campos = _campos(r.to_medline())
    autores = campos.get('FAU') or campos.get('AU') or ['']
    return {
        'record_id': r.id,
        'pmid': r.pmid or '',
        'wos_ut': r.ut or '',
        'scopus_eid': r.eid or '',
        'doi': r.doi or '',
        'in_pubmed': 'yes' if 'PubMed' in r.fontes else 'no',
        'in_wos': 'yes' if 'WOS' in r.fontes else 'no',
        'in_scopus': 'yes' if 'Scopus' in r.fontes else 'no',
        'databases': '; '.join(r.fontes),
        'title': r.titulo,
        'first_author': autores[0],
        'year': r.ano or '',
        'journal': (campos.get('JT') or campos.get('TA') or [''])[0],
        'document_type': '; '.join(campos.get('PT', [])),
        'has_abstract': 'yes' if campos.get('AB') else 'no',
        # blank = the abstract came with the record; otherwise the source used by --fill-abstracts
        'abstract_source': (campos.get('ABS') or [''])[0],
        'times_cited_wos': _inteiro(r.tc),
        'times_cited_scopus': _inteiro(r.tc_scopus),
        'screening_decision': 'exclude' if sem_resumo else '',
        'exclusion_reason': SEM_RESUMO if sem_resumo else '',
        'notes': '',
    }


def escrever_prisma(grupos, mantidos, relatorio, destino, resumos=None, sem_resumo=()):
    """sem_resumo: the records (objects) without abstract, pre-marked as excluded."""
    fora = {id(r) for r in sem_resumo}
    registros = pd.DataFrame([linha_registro(r, id(r) in fora) for r in mantidos],
                             columns=COLUNAS_REGISTROS)
    duplicatas = pd.DataFrame(relatorio, columns=COLUNAS_DUPLICATAS)

    n = len(mantidos)
    col = get_column_letter(COLUNAS_REGISTROS.index('screening_decision') + 1)
    faixa = f"records!${col}$2:${col}${n + 1}"
    col_motivo = get_column_letter(COLUNAS_REGISTROS.index('exclusion_reason') + 1)
    faixa_motivo = f"records!${col_motivo}$2:${col_motivo}${n + 1}"
    fontes = Counter('; '.join(r.fontes) for r in mantidos)
    motivos = Counter(d['matched_on'] for d in relatorio)

    resumo = [('Identification', f"Records identified from {rotulo}", len(regs)) for rotulo, regs in grupos]
    resumo += [('Identification', 'Records identified (total)', sum(len(r) for _, r in grupos)),
               ('Identification', 'Duplicate records removed', len(relatorio))]
    resumo += [('Identification', f"  matched on {m}", c) for m, c in motivos.most_common()]
    resumo += [('Overlap', f"Unique records in {f}", c) for f, c in fontes.most_common()]
    herdados = int(registros['abstract_source'].str.endswith('(duplicate record)').sum())
    if herdados:
        resumo += [('Abstracts', 'Abstracts taken from a duplicate record', herdados)]
    if resumos is not None:
        resumo += [('Abstracts', 'Records without abstract before filling', resumos['without'])]
        resumo += [('Abstracts', f"  filled from {f}", c) for f, c in resumos['filled'].items()]
        resumo += [('Abstracts', '  still without abstract: not found', resumos['not_found']),
                   ('Abstracts', '  still without abstract: only in another language',
                    resumos['only_other_language']),
                   ('Abstracts', '  still without abstract: no DOI or PMID', resumos['no_id'])]
    resumo += [('Screening', 'Records screened', n),
               ('Screening', 'Records excluded', f'=COUNTIF({faixa},"exclude")'),
               ('Screening', f'  of which: {SEM_RESUMO.lower()} (marked automatically; not analysed)',
                f'=COUNTIFS({faixa},"exclude",{faixa_motivo},"{SEM_RESUMO}")'),
               ('Screening', 'Records included', f'=COUNTIF({faixa},"include")'),
               ('Screening', 'Records marked maybe', f'=COUNTIF({faixa},"maybe")'),
               ('Screening', 'Records not yet screened', f'=COUNTBLANK({faixa})')]
    resumo = pd.DataFrame(resumo, columns=['stage', 'item', 'n'])

    with pd.ExcelWriter(destino, engine='openpyxl') as writer:
        resumo.to_excel(writer, sheet_name='summary', index=False)
        registros.to_excel(writer, sheet_name='records', index=False)
        duplicatas.to_excel(writer, sheet_name='duplicates_removed', index=False)

        ws = writer.sheets['records']
        ws.freeze_panes = 'B2'
        if n:
            dv = DataValidation(type='list', formula1='"' + ','.join(DECISOES) + '"', allow_blank=True)
            ws.add_data_validation(dv)
            dv.add(f"{col}2:{col}{n + 1}")
        larguras = {'title': 60, 'journal': 30, 'first_author': 25, 'doi': 28, 'exclusion_reason': 30,
                    'notes': 30, 'databases': 20, 'wos_ut': 22, 'scopus_eid': 22, 'record_id': 22}
        for i, nome in enumerate(COLUNAS_REGISTROS, 1):
            ws.column_dimensions[get_column_letter(i)].width = larguras.get(nome, 12)
        writer.sheets['summary'].column_dimensions['B'].width = 45
    return destino
