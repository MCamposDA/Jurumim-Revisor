"""
E-mail and API keys for the downloads (-p / --db).

Each value is taken from, in this order:
  1. its flag (--email, --wos-apikey, --scopus-apikey)
  2. its environment variable (WOS_API_KEY, SCOPUS_API_KEY)
  3. the keys file saved on a previous run (~/.jurumim_keys.json)
  4. a question in the terminal, one value at a time

Keys are typed hidden (like a password) and saved only when the user says so.
The file is readable by its owner only, and keys are always shown masked.
--no-prompt turns the questions off; --show-keys and --forget-keys inspect
and delete the file.
"""
import getpass
import json
import os
import sys
from pathlib import Path

ARQUIVO = Path.home() / '.jurumim_keys.json'

# What each database needs: (args attribute, file key, label, where to get it, secret)
NECESSARIOS = {
    'pubmed': [('email', 'email', 'E-mail for NCBI (PubMed)',
                'any e-mail of yours; NCBI asks for one to contact heavy users', False)],
    'wos': [('wos_apikey', 'wos_apikey', 'Web of Science API key',
             'developer.clarivate.com (Expanded: institutional subscription; Starter: free)', True)],
    'scopus': [('scopus_apikey', 'scopus_apikey', 'Scopus (Elsevier) API key',
                'dev.elsevier.com > I want an API key; anyone can get one, an institution '
                'is only needed for abstracts', True)],
}
NOMES = {'pubmed': 'PubMed', 'wos': 'Web of Science', 'scopus': 'Scopus'}

# Kind of key, asked right after a typed key and saved with it:
# (args attribute = saved name, question, answer prefix of the second kind, second kind, default kind)
TIPOS = {
    'wos': ('wos_api', "Is it an Expanded (abstracts) or a Starter (titles only) key? [E/s]: ",
            's', 'starter', 'expanded'),
    'scopus': ('scopus_key', "Is it an institutional key (abstracts; institution network or token) "
                             "or a personal key (no institution; titles only)? [I/p]: ",
               'p', 'personal', 'institutional'),
}


def mascarar(valor, secreto=True):
    if not valor:
        return ''
    if not secreto:
        return valor
    return '*' * len(valor) if len(valor) <= 8 else f"{valor[:4]}…{valor[-4:]}"


def carregar():
    try:
        return json.loads(ARQUIVO.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return {}


def salvar(chave, valor):
    dados = carregar()
    dados[chave] = valor
    # Created with owner-only permissions (like ~/.netrc); on Windows the user folder protects it
    fd = os.open(ARQUIVO, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w', encoding='utf-8') as f:
        json.dump(dados, f, indent=2)
    try:
        os.chmod(ARQUIVO, 0o600)
    except OSError:
        pass


def esquecer():
    if ARQUIVO.exists():
        ARQUIVO.unlink()
        print(f"Deleted {ARQUIVO}")
    else:
        print(f"No saved keys ({ARQUIVO} does not exist).")


def mostrar():
    dados = carregar()
    if not dados:
        print(f"No saved keys ({ARQUIVO} does not exist or is empty).")
        return
    print(f"Saved in {ARQUIVO}:")
    secretos = {k: s for itens in NECESSARIOS.values() for _, k, _, _, s in itens}
    for k, v in dados.items():
        if k in {t[0] for t in TIPOS.values()}:
            print(f"  {k}: {v}")
        else:
            print(f"  {k}: {mascarar(v, secretos.get(k, True))}")


def _ler(funcao, pergunta):
    """One answer; Ctrl+D counts as an empty answer, Ctrl+C cancels the run."""
    try:
        return funcao(pergunta).strip()
    except EOFError:
        print()
        return ''
    except KeyboardInterrupt:
        print("\nCancelled.")
        raise SystemExit(1)


def completar(args, dbs, interativo=None, perguntar=input, perguntar_segredo=getpass.getpass):
    """
    Fill the missing e-mail / keys of the chosen databases in `args`.
    Returns the databases left: one the user skipped (Enter) is dropped.
    Without questions, missing values stay empty and main() reports them.
    """
    if interativo is None:
        interativo = (not getattr(args, 'no_prompt', False)) and sys.stdin.isatty()
    salvos = carregar()
    restantes = []
    for db in dbs:
        ok = True
        for attr, chave, rotulo, onde, secreto in NECESSARIOS.get(db, []):
            if getattr(args, attr, None):
                continue
            tipo_attr = TIPOS[db][0] if db in TIPOS else None
            if salvos.get(chave):
                setattr(args, attr, salvos[chave])
                if tipo_attr and getattr(args, tipo_attr, None) is None:
                    setattr(args, tipo_attr, salvos.get(tipo_attr))
                tipo = f" ({getattr(args, tipo_attr, None)} key)" if tipo_attr and getattr(args, tipo_attr, None) else ''
                print(f"Using saved {rotulo}{tipo}: {mascarar(salvos[chave], secreto)}")
                continue
            if not interativo:
                continue  # left empty: main() stops with the usual "needs ..." error
            print(f"\n{rotulo} is needed for {NOMES[db]} ({onde}).")
            pergunta = f"{rotulo} (typed hidden; Enter to skip {NOMES[db]}): " if secreto \
                else f"{rotulo} (Enter to skip {NOMES[db]}): "
            valor = _ler(perguntar_segredo if secreto else perguntar, pergunta)
            if not valor:
                print(f"{NOMES[db]} skipped.")
                ok = False
                break
            setattr(args, attr, valor)
            if tipo_attr and getattr(args, tipo_attr, None) is None:
                _, pergunta_tipo, prefixo, outro, padrao = TIPOS[db]
                resposta = _ler(perguntar, pergunta_tipo).lower()
                setattr(args, tipo_attr, outro if resposta.startswith(prefixo) else padrao)
            if _ler(perguntar, f"Save it in {ARQUIVO} for next time? [y/N]: ").lower().startswith('y'):
                salvar(chave, valor)
                if tipo_attr:
                    salvar(tipo_attr, getattr(args, tipo_attr, None) or TIPOS[db][4])
                print(f"Saved ({mascarar(valor, secreto)}).")
        if ok:
            restantes.append(db)
    return restantes
