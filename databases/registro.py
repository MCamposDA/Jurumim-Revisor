"""
Search log of a merge (<merged>_search_log.json), read by the methods text.

It records, for each source, the database, whether it came from an API or an
exported file, the query sent (APIs only; an exported file does not carry it),
the kind of key and the number of records; then the duplicates removed by key,
the abstracts taken from duplicates or filled from each source, and the
records left without abstract.
"""
import json
from datetime import date
from pathlib import Path

NOMES = {'PubMed': 'PubMed', 'WOS': 'Web of Science', 'Scopus': 'Scopus'}


def origem_arquivo(nome, registros):
    """Source entry of an exported file: its database comes from its records."""
    bases = sorted({f for r in registros for f in r.fontes})
    return {'label': nome, 'database': ' + '.join(NOMES.get(b, b) for b in bases) or 'unknown',
            'origin': 'merged file' if len(bases) > 1 else 'file', 'file': nome, 'query': None,
            'key': None, 'date': None, 'records': len(registros)}


def origem_api(rotulo, query, chave, registros, arquivo=None):
    return {'label': rotulo, 'database': rotulo, 'origin': 'api', 'file': arquivo, 'query': query,
            'key': chave, 'date': date.today().isoformat(), 'records': len(registros)}


def escrever_log(destino, origens, relatorio, mantidos, sem_ab, resumos, herdados, manter_todos):
    from collections import Counter
    dados = {
        'tool': 'Jurumim Revisor',
        'merged_on': date.today().isoformat(),
        'merged_file': Path(destino).name,
        'sources': origens,
        'identified': sum(o['records'] for o in origens),
        'duplicates': {'total': len(relatorio),
                       'by_key': dict(Counter(d['matched_on'] for d in relatorio))},
        'unique': len(mantidos),
        'abstracts': {
            'taken_from_duplicates': herdados,
            'fill_requested': resumos is not None,
            'filled': dict(resumos['filled']) if resumos else {},
            'only_other_language': resumos['only_other_language'] if resumos else None,
            'not_found': resumos['not_found'] if resumos else None,
            'no_id': resumos['no_id'] if resumos else None,
        },
        'without_abstract': len(sem_ab),
        'kept_without_abstract': manter_todos,
    }
    caminho = Path(destino).with_name(Path(destino).stem + '_search_log.json')
    caminho.write_text(json.dumps(dados, indent=1, ensure_ascii=False), encoding='utf-8')
    return caminho


def ler_log(caminho):
    try:
        return json.loads(Path(caminho).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None
