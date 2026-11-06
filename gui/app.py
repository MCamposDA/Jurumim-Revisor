"""
Jurumim Revisor desktop window (Tkinter, standard library).

Each page is a form; gui/comandos.py turns it into the command line you would
type, and "Run" executes it as a subprocess and shows its output. The window
does not import Jurumim_Revisor.py.
"""
import json
import os
import platform
import queue
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import filedialog, ttk
from tkinter import font as tkfont

from . import comandos as C

# Layout: a left rail with the four review steps (a real sequence: search, merge,
# screen, analyse) and two utilities; the form of the chosen step on the right;
# docked below, the exact terminal command and its live log.
COR = {
    'fundo': '#EEF2EE',       # window ground, a paper grey biased to the logo's green
    'superficie': '#FFFFFF',  # forms and log
    'trilho': '#E1E9E2',      # left rail
    'tinta': '#17251C',       # text
    'suave': '#5A6A60',       # hints, secondary text
    'linha': '#CBD6CE',       # borders and rules
    'folha': '#2B7A4B',       # Jurumim green: primary action, selection
    'folha_clara': '#DCEDE2',
    'ouro': '#D9A92B',        # the logo's yellow: only while a command runs
    'rio': '#1D6694',         # the logo's blue: links and info
    'alerta': '#9A5F0B',
    'erro': '#A8342A',
}
PASTA_CONFIG = Path.home() / '.jurumim_gui.json'
ASSETS = C.RAIZ / 'viewer' / 'assets'


def _fonte(familias, padrao):
    disponiveis = {f.lower(): f for f in tkfont.families()}
    return next((disponiveis[f.lower()] for f in familias if f.lower() in disponiveis), padrao)


def tk_sem_fontes():
    """
    True for a Tk built without Xft (the default conda 'tk' on Linux): it only
    knows the bitmap font 'fixed', with no sizes and no glyphs such as '…'.
    Fix: conda install -c conda-forge "tk=*=xft_*"
    """
    return {f.lower() for f in tkfont.families()} <= {'fixed'}


SUBSTITUTOS = {'…': '...', '·': '|', '→': '->', '•': '*', '–': '-', '—': '-', '>': '>'}


def ascii_se_preciso(texto, basico):
    if not basico or not isinstance(texto, str):
        return texto
    for de, para in SUBSTITUTOS.items():
        texto = texto.replace(de, para)
    return texto


def abrir_no_sistema(caminho):
    """Open a file or folder with the system's own program (also from WSL)."""
    caminho = str(caminho)
    try:
        if sys.platform.startswith('win'):
            os.startfile(caminho)  # noqa: S606
        elif sys.platform == 'darwin':
            subprocess.Popen(['open', caminho])
        elif 'microsoft' in platform.release().lower() and shutil.which('wslpath'):
            win = subprocess.run(['wslpath', '-w', caminho], capture_output=True, text=True).stdout.strip()
            subprocess.Popen(['explorer.exe', win])
        else:
            subprocess.Popen(['xdg-open', caminho])
        return True
    except Exception:
        return False


def abrir_url(url):
    """Open a web address in the user's browser (on WSL, the Windows one)."""
    try:
        if 'microsoft' in platform.release().lower() and shutil.which('explorer.exe'):
            subprocess.Popen(['explorer.exe', url])
        else:
            webbrowser.open(url)
    except Exception:
        pass


class Rolavel(tk.Frame):
    """A vertically scrollable frame (forms longer than the window)."""

    def __init__(self, pai, **kw):
        super().__init__(pai, bg=COR['superficie'], **kw)
        self.canvas = tk.Canvas(self, bg=COR['superficie'], highlightthickness=0, bd=0)
        barra = ttk.Scrollbar(self, orient='vertical', command=self.canvas.yview)
        self.corpo = tk.Frame(self.canvas, bg=COR['superficie'])
        self.corpo.bind('<Configure>', lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')))
        self._janela = self.canvas.create_window((0, 0), window=self.corpo, anchor='nw')
        self.canvas.bind('<Configure>', lambda e: self.canvas.itemconfigure(self._janela, width=e.width))
        self.canvas.configure(yscrollcommand=barra.set)
        self.canvas.pack(side='left', fill='both', expand=True)
        barra.pack(side='right', fill='y')
        for seq in ('<MouseWheel>', '<Button-4>', '<Button-5>'):
            self.corpo.bind_all(seq, self._roda, add='+')

    def _roda(self, e):
        w = e.widget
        while w is not None and w is not self:
            w = getattr(w, 'master', None)
        if w is None or not self.winfo_ismapped():
            return
        passo = -1 if getattr(e, 'num', 0) == 4 or getattr(e, 'delta', 0) > 0 else 1
        self.canvas.yview_scroll(passo * 2, 'units')


class App:
    PAGINAS = [('search', '1', 'Search databases'), ('merge', '2', 'Merge files'),
               ('screen', '3', 'Screen'), ('analyse', '4', 'Analyse')]
    UTILIDADES = [('fill', 'Fill abstracts of a file'), ('keys', 'API keys')]

    def __init__(self, root):
        self.root = root
        self.proc = None
        self.fila = queue.Queue()
        self.inicio = None
        self.pagina = 'search'
        self.cfg = self._ler_config()
        self.salvas = C.chaves_salvas()

        root.title('Jurumim Revisor')
        root.configure(bg=COR['fundo'])
        root.minsize(1080, 740)
        root.geometry(self.cfg.get('geometria', '1220x820'))
        self._fontes()
        self._estilos()
        self._icone()

        self.v = {}
        self._variaveis()
        self._cabecalho()
        corpo = tk.Frame(root, bg=COR['fundo'])
        corpo.pack(fill='both', expand=True, padx=16, pady=(0, 8))
        self._trilho(corpo)
        self.area = tk.Frame(corpo, bg=COR['superficie'], highlightbackground=COR['linha'],
                             highlightthickness=1)
        self.area.pack(side='left', fill='both', expand=True)
        self.paginas = {}
        for nome, construir in (('search', self._pagina_busca), ('merge', self._pagina_merge),
                                ('screen', self._pagina_triagem), ('analyse', self._pagina_analise),
                                ('fill', self._pagina_preencher), ('keys', self._pagina_chaves)):
            quadro = Rolavel(self.area)
            construir(quadro.corpo)
            self.paginas[nome] = quadro
        self._doca()
        if self.basico:
            self._limpar_textos(root)
            self._escrever('This Tk has no font support (only the bitmap font "fixed"), so the window looks '
                           'plain. To fix it: conda install -c conda-forge "tk=*=xft_*"\n', 'aviso')
        self.mostrar(self.cfg.get('pagina', 'search'))
        self._sugerir_arquivos()
        root.protocol('WM_DELETE_WINDOW', self._fechar)
        root.after(100, self._ler_fila)

    # ------------------------------------------------------------------ look
    def t(self, texto):
        return ascii_se_preciso(texto, self.basico)

    def _limpar_textos(self, w):
        """Replace the glyphs a bitmap-only Tk cannot draw, in every widget built so far."""
        try:
            if 'text' in w.keys():
                w.configure(text=self.t(w.cget('text')))
        except tk.TclError:
            pass
        for filho in w.winfo_children():
            self._limpar_textos(filho)

    def _fontes(self):
        self.basico = tk_sem_fontes()
        ui = _fonte(['Segoe UI', 'SF Pro Text', 'Helvetica Neue', 'Noto Sans', 'Ubuntu', 'Cantarell',
                     'DejaVu Sans'], 'TkDefaultFont')
        mono = _fonte(['Cascadia Mono', 'Consolas', 'SF Mono', 'Menlo', 'JetBrains Mono',
                       'Ubuntu Mono', 'DejaVu Sans Mono'], 'TkFixedFont')
        self.f = {
            'marca': (ui, 17, 'bold'), 'titulo': (ui, 14, 'bold'), 'secao': (ui, 9, 'bold'),
            'corpo': (ui, 10), 'forte': (ui, 10, 'bold'), 'dica': (ui, 9), 'mono': (mono, 9),
            'mono_peq': (mono, 8), 'num': (ui, 10, 'bold'), 'botao': (ui, 10, 'bold'),
        }
        self.root.option_add('*Font', self.f['corpo'])

    def _estilos(self):
        s = ttk.Style(self.root)
        s.theme_use('clam')
        s.configure('.', background=COR['superficie'], foreground=COR['tinta'], font=self.f['corpo'],
                    bordercolor=COR['linha'], lightcolor=COR['linha'], darkcolor=COR['linha'],
                    focuscolor=COR['folha'])
        s.configure('TEntry', fieldbackground=COR['superficie'], padding=(6, 4), insertcolor=COR['tinta'])
        s.map('TEntry', bordercolor=[('focus', COR['folha'])], lightcolor=[('focus', COR['folha'])])
        s.configure('TCheckbutton', background=COR['superficie'], indicatorbackground=COR['superficie'],
                    indicatorforeground=COR['folha'], padding=(0, 2))
        s.map('TCheckbutton', indicatorbackground=[('selected', COR['folha_clara'])],
              background=[('active', COR['superficie'])])
        s.configure('TRadiobutton', background=COR['superficie'], indicatorbackground=COR['superficie'],
                    indicatorforeground=COR['folha'], padding=(0, 2))
        s.map('TRadiobutton', indicatorbackground=[('selected', COR['folha_clara'])],
              background=[('active', COR['superficie'])], foreground=[('disabled', COR['linha'])])
        s.configure('Primario.TButton', background=COR['folha'], foreground='#FFFFFF', font=self.f['botao'],
                    padding=(22, 7), borderwidth=0)
        s.map('Primario.TButton', background=[('disabled', COR['linha']), ('active', '#24683F')],
              foreground=[('disabled', COR['suave'])])
        s.configure('TButton', background=COR['superficie'], foreground=COR['tinta'], padding=(12, 5),
                    borderwidth=1)
        s.map('TButton', background=[('active', COR['folha_clara']), ('disabled', COR['superficie'])],
              foreground=[('disabled', COR['linha'])])
        s.configure('Parar.TButton', foreground=COR['erro'])
        s.configure('Treeview', background=COR['superficie'], fieldbackground=COR['superficie'],
                    rowheight=24, borderwidth=0)
        s.configure('Treeview.Heading', background=COR['fundo'], font=self.f['secao'], relief='flat')
        s.map('Treeview', background=[('selected', COR['folha_clara'])], foreground=[('selected', COR['tinta'])])
        s.configure('Vertical.TScrollbar', background=COR['fundo'], troughcolor=COR['superficie'],
                    borderwidth=0, arrowsize=12)

    def _icone(self):
        self.logo = self.logo_peq = None
        try:
            from PIL import Image, ImageTk
            img = Image.open(ASSETS / 'jurumim_logo.jpg').convert('RGBA')
            # the JPEG has a white square around the round logo: make it transparent, then crop
            img.putalpha(img.convert('L').point(lambda v: 0 if v > 242 else 255))
            img = img.crop(img.getbbox() or (0, 0) + img.size)
            self.logo = ImageTk.PhotoImage(img.resize((46, 46), Image.LANCZOS))
            self.logo_peq = ImageTk.PhotoImage(img.resize((64, 64), Image.LANCZOS))
            self.root.iconphoto(True, self.logo_peq)
        except Exception:
            pass   # Pillow missing: the window works without the logo

    # ------------------------------------------------------------------ state
    def _variaveis(self):
        padrao = {
            'topico': 'my_review', 'query': '', 'db_pubmed': True, 'db_wos': False, 'db_scopus': True,
            'email': self.salvas.get('email', ''), 'ncbi_apikey': '',
            'wos_apikey': '', 'wos_api': self.salvas.get('wos_api', 'expanded'), 'wos_query': '',
            'scopus_apikey': '', 'scopus_key': self.salvas.get('scopus_key', 'institutional'),
            'scopus_view': 'complete', 'scopus_insttoken': '', 'scopus_query': '',
            'preencher': True, 'manter_sem_resumo': False, 'salvar_chaves': False,
            'merge_out': '', 'mesclado': '', 'prisma': '', 'screen_out': '',
            'keep_include': True, 'keep_maybe': False, 'keep_exclude': False,
            'entrada': '', 'saida': 'general.xlsx', 'modo': 'frequency', 'stopwords': '',
            'stopword_file': '', 'lemma': False, 'articles': False, 'viewer': False,
            'arquivo_preencher': '', 'fill_out': '', 's2_apikey': '', 'openalex_apikey': '',
        }
        secretos = {'ncbi_apikey', 'wos_apikey', 'scopus_apikey', 'scopus_insttoken', 's2_apikey',
                    'openalex_apikey'}
        for k, valor in padrao.items():
            if k not in secretos and k in self.cfg.get('estado', {}):
                valor = self.cfg['estado'][k]
            var = tk.BooleanVar(value=valor) if isinstance(valor, bool) else tk.StringVar(value=valor)
            var.trace_add('write', lambda *a: self.atualizar())
            self.v[k] = var
        self._adiado = None
        self.v['topico'].trace_add('write', lambda *a: self._topico_mudou())
        self.secretos = secretos
        self.arquivos = list(self.cfg.get('arquivos', []))
        self.textos = {}

    def estado(self):
        e = {k: v.get() for k, v in self.v.items()}
        e['pasta'] = str(self.pasta())
        e['arquivos'] = list(self.arquivos)
        for k, w in self.textos.items():
            e[k] = w.get('1.0', 'end').strip()
        return e

    def pasta(self):
        nome = (self.v['topico'].get() or 'my_review').strip()
        p = Path(nome).expanduser()
        return p if p.is_absolute() else C.RAIZ / 'results' / nome

    # ------------------------------------------------------------------ frame
    def _cabecalho(self):
        topo = tk.Frame(self.root, bg=COR['fundo'])
        topo.pack(fill='x', padx=16, pady=(12, 10))
        marca = tk.Frame(topo, bg=COR['fundo'])
        marca.pack(side='left')
        if self.logo:
            tk.Label(marca, image=self.logo, bg=COR['fundo']).pack(side='left', padx=(0, 10))
        textos = tk.Frame(marca, bg=COR['fundo'])
        textos.pack(side='left')
        tk.Label(textos, text='Jurumim Revisor', font=self.f['marca'], bg=COR['fundo'],
                 fg=COR['tinta']).pack(anchor='w')
        tk.Label(textos, text='Systematic review over PubMed, Web of Science and Scopus',
                 font=self.f['dica'], bg=COR['fundo'], fg=COR['suave']).pack(anchor='w')

        topico = tk.Frame(topo, bg=COR['fundo'])
        topico.pack(side='right', anchor='e')
        tk.Label(topico, text='TOPIC', font=self.f['secao'], bg=COR['fundo'], fg=COR['suave']).pack(anchor='w')
        linha = tk.Frame(topico, bg=COR['fundo'])
        linha.pack(anchor='w')
        ttk.Entry(linha, textvariable=self.v['topico'], width=26).pack(side='left', padx=(0, 6))
        ttk.Button(linha, text='Choose folder…', command=self._escolher_pasta).pack(side='left', padx=(0, 6))
        ttk.Button(linha, text='Open folder', command=lambda: self._abrir(self.pasta())).pack(side='left')
        # the full folder, shortened from the left so the row keeps its width
        self.rotulo_pasta = tk.Label(topico, text='', font=self.f['mono_peq'], bg=COR['fundo'], fg=COR['suave'],
                                     anchor='w', width=64)
        self.rotulo_pasta.pack(anchor='w', pady=(3, 0))

    def _trilho(self, pai):
        trilho = tk.Frame(pai, bg=COR['trilho'], width=228)
        trilho.pack(side='left', fill='y', padx=(0, 12))
        trilho.pack_propagate(False)
        tk.Label(trilho, text='REVIEW STEPS', font=self.f['secao'], bg=COR['trilho'], fg=COR['suave']).pack(
            anchor='w', padx=14, pady=(14, 6))
        self.botoes = {}
        for nome, num, texto in self.PAGINAS:
            self.botoes[nome] = self._item_trilho(trilho, nome, texto, num)
        tk.Frame(trilho, bg=COR['linha'], height=1).pack(fill='x', padx=14, pady=12)
        tk.Label(trilho, text='TOOLS', font=self.f['secao'], bg=COR['trilho'], fg=COR['suave']).pack(
            anchor='w', padx=14, pady=(0, 6))
        for nome, texto in self.UTILIDADES:
            self.botoes[nome] = self._item_trilho(trilho, nome, texto, None)
        rodape = tk.Label(trilho, text='Runs Jurumim_Revisor.py.\nEvery command is shown below\n'
                                       'and can be copied to a terminal.',
                          font=self.f['dica'], justify='left', bg=COR['trilho'], fg=COR['suave'])
        rodape.pack(side='bottom', anchor='w', padx=14, pady=14)

    def _item_trilho(self, pai, nome, texto, num):
        linha = tk.Frame(pai, bg=COR['trilho'], cursor='hand2')
        linha.pack(fill='x', padx=8, pady=1)
        disco = tk.Label(linha, text=num or '·', width=2, font=self.f['num'], bg=COR['trilho'], fg=COR['suave'])
        disco.pack(side='left', padx=(6, 6), pady=7)
        rot = tk.Label(linha, text=texto, font=self.f['corpo'], bg=COR['trilho'], fg=COR['tinta'], anchor='w')
        rot.pack(side='left', fill='x', expand=True)
        for w in (linha, disco, rot):
            w.bind('<Button-1>', lambda e, n=nome: self.mostrar(n))
        return linha, disco, rot

    def mostrar(self, nome):
        if nome not in self.paginas:
            nome = 'search'
        self.pagina = nome
        for n, q in self.paginas.items():
            q.pack_forget()
        self.paginas[nome].pack(fill='both', expand=True)
        for n, (linha, disco, rot) in self.botoes.items():
            ativo = n == nome
            fundo = COR['superficie'] if ativo else COR['trilho']
            for w in (linha, disco, rot):
                w.configure(bg=fundo)
            disco.configure(fg=COR['folha'] if ativo else COR['suave'])
            rot.configure(font=self.f['forte'] if ativo else self.f['corpo'])
        if nome == 'screen':
            self._desenhar_prisma()
        self.atualizar()

    # ------------------------------------------------------------------ form helpers
    def _titulo(self, pai, titulo, texto):
        tk.Label(pai, text=titulo, font=self.f['titulo'], bg=COR['superficie'], fg=COR['tinta']).pack(
            anchor='w', padx=24, pady=(20, 2))
        tk.Label(pai, text=texto, font=self.f['corpo'], bg=COR['superficie'], fg=COR['suave'],
                 wraplength=720, justify='left').pack(anchor='w', padx=24, pady=(0, 6))

    def _secao(self, pai, texto):
        tk.Frame(pai, bg=COR['linha'], height=1).pack(fill='x', padx=24, pady=(14, 8))
        tk.Label(pai, text=texto.upper(), font=self.f['secao'], bg=COR['superficie'], fg=COR['suave']).pack(
            anchor='w', padx=24, pady=(0, 6))
        bloco = tk.Frame(pai, bg=COR['superficie'])
        bloco.pack(fill='x', padx=24)
        bloco.columnconfigure(1, weight=1)
        return bloco

    def _dica(self, pai, texto, flag=None, linha=None, coluna=1, onde='grid'):
        quadro = tk.Frame(pai, bg=COR['superficie'])
        if flag:
            tk.Label(quadro, text=flag, font=self.f['mono_peq'], bg=COR['superficie'], fg=COR['rio']).pack(
                side='left', padx=(0, 6))
        if texto:
            tk.Label(quadro, text=texto, font=self.f['dica'], bg=COR['superficie'], fg=COR['suave'],
                     wraplength=560, justify='left').pack(side='left')
        if onde == 'grid':
            quadro.grid(row=linha, column=coluna, sticky='w', pady=(0, 8))
        else:
            quadro.pack(anchor='w', pady=(0, 8))
        return quadro

    def _campo(self, pai, linha, rotulo, chave, dica='', flag=None, secreto=False, largura=48, arquivo=None):
        tk.Label(pai, text=rotulo, font=self.f['corpo'], bg=COR['superficie'], fg=COR['tinta']).grid(
            row=linha, column=0, sticky='nw', padx=(0, 14), pady=(5, 0))
        quadro = tk.Frame(pai, bg=COR['superficie'])
        quadro.grid(row=linha, column=1, sticky='w')
        ent = ttk.Entry(quadro, textvariable=self.v[chave], width=largura,
                        show=self.t('•') if secreto else '')
        ent.pack(side='left')
        if arquivo:
            ttk.Button(quadro, text='Browse…', command=lambda: self._procurar(chave, arquivo)).pack(
                side='left', padx=(6, 0))
        if dica or flag:
            self._dica(pai, dica, flag, linha + 1)
        return ent

    def _opcao(self, pai, linha, texto, chave, dica='', flag=None):
        ttk.Checkbutton(pai, text=texto, variable=self.v[chave]).grid(row=linha, column=0, columnspan=2,
                                                                       sticky='w')
        if dica or flag:
            q = self._dica(pai, dica, flag, linha + 1, coluna=0)
            q.grid(columnspan=2, padx=(26, 0))

    def _radios(self, pai, linha, rotulo, chave, opcoes, flag=None, dica=''):
        tk.Label(pai, text=rotulo, font=self.f['corpo'], bg=COR['superficie'], fg=COR['tinta']).grid(
            row=linha, column=0, sticky='nw', padx=(0, 14), pady=(3, 0))
        quadro = tk.Frame(pai, bg=COR['superficie'])
        quadro.grid(row=linha, column=1, sticky='w')
        botoes = []
        for valor, texto in opcoes:
            b = ttk.Radiobutton(quadro, text=texto, value=valor, variable=self.v[chave])
            b.pack(side='left', padx=(0, 16))
            botoes.append(b)
        if dica or flag:
            self._dica(pai, dica, flag, linha + 1)
        return botoes

    def _texto(self, pai, linha, rotulo, chave, altura, dica='', flag=None):
        tk.Label(pai, text=rotulo, font=self.f['corpo'], bg=COR['superficie'], fg=COR['tinta']).grid(
            row=linha, column=0, sticky='nw', padx=(0, 14), pady=(5, 0))
        caixa = tk.Text(pai, height=altura, width=56, font=self.f['mono'], relief='flat', wrap='word',
                        highlightthickness=1, highlightbackground=COR['linha'], highlightcolor=COR['folha'],
                        bg=COR['superficie'], fg=COR['tinta'], insertbackground=COR['tinta'], padx=6, pady=4)
        caixa.grid(row=linha, column=1, sticky='w', pady=(2, 0))
        caixa.insert('1.0', self.cfg.get('textos', {}).get(chave, ''))
        caixa.bind('<KeyRelease>', lambda e: self.atualizar())
        self.textos[chave] = caixa
        if dica or flag:
            self._dica(pai, dica, flag, linha + 1)
        return caixa

    def _nota_chave(self, chave):
        valor = self.salvas.get(chave)
        if not valor:
            return 'Not saved yet.'
        try:
            from databases.credenciais import mascarar
            return f'Saved key in use when the field is empty: {mascarar(valor)}'
        except Exception:
            return 'A saved key is in use when the field is empty.'

    # ------------------------------------------------------------------ pages
    def _pagina_busca(self, p):
        self._titulo(p, '1  Search databases',
                     'Downloads the query from each database you tick, keeps each raw file, removes the '
                     'duplicates (PubMed > Web of Science > Scopus) and writes the merged file with its '
                     'PRISMA table into the topic folder.')
        b = self._secao(p, 'Query')
        self._campo(b, 0, 'Search', 'query', 'Free text is sent to each database in its own syntax '
                    '(TS=(…) for Web of Science, TITLE-ABS-KEY(…) for Scopus).', '-q', largura=60)

        b = self._secao(p, 'PubMed')
        self._opcao(b, 0, 'Search PubMed', 'db_pubmed', 'No key needed: NCBI asks for an e-mail.', '--db pubmed')
        self._campo(b, 2, 'E-mail', 'email', flag='--email')
        self._campo(b, 4, 'NCBI key', 'ncbi_apikey', 'Optional: raises the request rate from 3 to 10 per second.',
                    '--apikey', secreto=True, largura=32)

        b = self._secao(p, 'Web of Science')
        self._opcao(b, 0, 'Search Web of Science', 'db_wos', '', '--db wos')
        self._campo(b, 2, 'API key', 'wos_apikey', self._nota_chave('wos_apikey'), 'WOS_API_KEY', secreto=True,
                    largura=40)
        self._radios(b, 4, 'Key', 'wos_api', [('expanded', 'Expanded (institutional, abstracts)'),
                                              ('starter', 'Starter (free, titles only)')], '--wos-api')
        self._campo(b, 6, 'Own query', 'wos_query', 'Optional, in WoS syntax, e.g. TS=(Nyssomyia) AND PY=(2015-2025)',
                    '--wos-query', largura=60)

        b = self._secao(p, 'Scopus')
        self._opcao(b, 0, 'Search Scopus', 'db_scopus', '', '--db scopus')
        self._campo(b, 2, 'API key', 'scopus_apikey', self._nota_chave('scopus_apikey'), 'SCOPUS_API_KEY',
                    secreto=True, largura=40)
        self._radios(b, 4, 'Key', 'scopus_key', [('institutional', 'Institutional (abstracts)'),
                                                 ('personal', 'Personal (no institution, titles only)')],
                     '--scopus-key')
        self.radios_view = self._radios(b, 6, 'View', 'scopus_view', [('complete', 'Complete'),
                                                                      ('standard', 'Standard (titles only)')],
                                        '--scopus-view', 'Institutional keys only.')
        self._campo(b, 8, 'Inst. token', 'scopus_insttoken', 'Only to use an institutional key outside the '
                    'institution network.', 'SCOPUS_INSTTOKEN', secreto=True, largura=32)
        self._campo(b, 10, 'Own query', 'scopus_query', 'Optional, in Scopus syntax, e.g. '
                    'TITLE-ABS-KEY(Nyssomyia) AND PUBYEAR > 2014', '--scopus-query', largura=60)

        b = self._secao(p, 'Abstracts and keys')
        self._opcao_resumos(b, 0)
        self._opcao(b, 4, 'Save the keys typed above for the next runs', 'salvar_chaves',
                    'Stored in ~/.jurumim_keys.json, readable by you only (the terminal tool uses the same file).')

    def _opcao_resumos(self, b, linha):
        self._opcao(b, linha, 'Fill missing abstracts from open sources', 'preencher',
                    'PubMed by PMID, then Crossref, Semantic Scholar and OpenAlex by DOI; English only. '
                    'Looked up after duplicates are removed.', '--fill-abstracts')
        self._opcao(b, linha + 2, 'Keep records without abstract in the analysis', 'manter_sem_resumo',
                    'Off: they go to *_no_abstract.txt and are pre-marked "exclude" in the PRISMA table.',
                    '--keep-no-abstract')

    def _pagina_merge(self, p):
        self._titulo(p, '2  Merge files',
                     'Merges files you exported from the websites (PubMed .txt, Web of Science plain text or '
                     'tab-delimited, Scopus CSV or RIS) or downloaded in step 1. The order of the files does '
                     'not matter: PubMed > Web of Science > Scopus always.')
        b = self._secao(p, 'Files')
        quadro = tk.Frame(b, bg=COR['superficie'])
        quadro.grid(row=0, column=0, columnspan=2, sticky='we')
        self.lista = ttk.Treeview(quadro, columns=('formato', 'pasta'), height=7, selectmode='extended')
        self.lista.heading('#0', text='FILE', anchor='w')
        self.lista.heading('formato', text='FORMAT', anchor='w')
        self.lista.heading('pasta', text='FOLDER', anchor='w')
        self.lista.column('#0', width=260)
        self.lista.column('formato', width=190)
        self.lista.column('pasta', width=300)
        self.lista.pack(side='left', fill='x', expand=True)
        botoes = tk.Frame(b, bg=COR['superficie'])
        botoes.grid(row=1, column=0, columnspan=2, sticky='w', pady=(8, 0))
        ttk.Button(botoes, text='Add files…', command=self._adicionar_arquivos).pack(side='left', padx=(0, 6))
        ttk.Button(botoes, text="Add this topic's downloads", command=self._adicionar_do_topico).pack(
            side='left', padx=(0, 6))
        ttk.Button(botoes, text='Remove selected', command=self._remover_arquivos).pack(side='left')
        self._dica(b, '', '--merge FILE …', 2, coluna=0).grid(columnspan=2, pady=(6, 8))
        self._preencher_lista()

        b = self._secao(p, 'Output')
        self._campo(b, 0, 'Merged file', 'merge_out', 'Written into the topic folder with *_prisma.xlsx and, '
                    'if any, *_no_abstract.txt.', '--merge-out', largura=40)
        b = self._secao(p, 'Abstracts')
        self._opcao_resumos(b, 0)

    def _pagina_triagem(self, p):
        self._titulo(p, '3  Screen',
                     'Open the PRISMA table, fill in screening_decision in the records sheet (include, exclude '
                     'or maybe), save it, then keep only the records you chose. The merged file is not changed.')
        b = self._secao(p, 'PRISMA flow of this topic')
        self.prisma_canvas = tk.Canvas(b, width=700, height=236, bg=COR['superficie'], highlightthickness=0)
        self.prisma_canvas.grid(row=0, column=0, columnspan=2, sticky='w')
        botoes = tk.Frame(b, bg=COR['superficie'])
        botoes.grid(row=1, column=0, columnspan=2, sticky='w', pady=(6, 0))
        ttk.Button(botoes, text='Open PRISMA table', command=lambda: self._abrir(self.v['prisma'].get())).pack(
            side='left', padx=(0, 6))
        ttk.Button(botoes, text='Refresh counts', command=self._desenhar_prisma).pack(side='left')

        b = self._secao(p, 'Files')
        self._campo(b, 0, 'Merged file', 'mesclado', flag='--screen MERGED.txt', largura=56,
                    arquivo=[('MEDLINE', '*.txt')])
        self._campo(b, 2, 'PRISMA table', 'prisma', flag='PRISMA.xlsx', largura=56, arquivo=[('Excel', '*.xlsx')])
        b = self._secao(p, 'Keep')
        tk.Label(b, text='Decisions', font=self.f['corpo'], bg=COR['superficie']).grid(row=0, column=0, sticky='w',
                                                                                         padx=(0, 14))
        q = tk.Frame(b, bg=COR['superficie'])
        q.grid(row=0, column=1, sticky='w')
        for chave, texto in (('keep_include', 'include'), ('keep_maybe', 'maybe'), ('keep_exclude', 'exclude')):
            ttk.Checkbutton(q, text=texto, variable=self.v[chave]).pack(side='left', padx=(0, 16))
        self._dica(b, 'Records without a decision are left out.', '--keep', 1)
        self._campo(b, 2, 'Output', 'screen_out', 'Optional; default <merged>_screened.txt', '--screen-out',
                    largura=40)

    def _pagina_analise(self, p):
        self._titulo(p, '4  Analyse',
                     'Counts words in titles and abstracts. For a merged file, each table also gets one '
                     'articles_<database> column per database.')
        b = self._secao(p, 'Files')
        self._campo(b, 0, 'Input', 'entrada', 'The screened file (or the merged one).', 'input.txt', largura=56,
                    arquivo=[('MEDLINE', '*.txt')])
        self._campo(b, 2, 'Table', 'saida', 'Written into the topic folder.', 'output.xlsx', largura=30)

        b = self._secao(p, 'Count')
        self._radios(b, 0, 'Mode', 'modo', [('frequency', 'Every word'), ('groups', 'Synonym groups'),
                                            ('search', 'Search terms')])
        self.caixa_grupos = self._texto(b, 2, 'Groups', 'grupos', 3,
                                        'One group per line: sandfly: phlebotomine, phlebotomines', '-st / -so')
        self.caixa_termos = self._texto(b, 4, 'Terms', 'termos', 3,
                                        'One per line; phrases and hyphenated terms allowed (sand flies, covid-19).',
                                        '--ws')
        self._campo(b, 6, 'Stopwords', 'stopwords', 'Extra words to ignore, separated by spaces or commas.', '-sw',
                    largura=44)
        self._campo(b, 8, 'Stopword file', 'stopword_file', '', '-sw FILE', largura=44,
                    arquivo=[('Text', '*.txt *.csv')])

        b = self._secao(p, 'Options')
        self._opcao(b, 0, 'Merge singular and plural (noun lemmas)', 'lemma', 'viruses → virus; does not change '
                    'search terms.', '--lemma')
        self._opcao(b, 2, 'Write one folder per article', 'articles', 'Word table and all fields of each article '
                    'in PMID/.', '--articles')
        self._opcao(b, 4, 'Open the viewer when done', 'viewer', 'Streamlit, in the browser; Stop closes it.',
                    '--viewer')

    def _pagina_preencher(self, p):
        self._titulo(p, 'Fill abstracts of a file',
                     'For a single file outside a merge. Inside the pipeline, use the option in steps 1 and 2: '
                     'it also gives the PRISMA table.')
        b = self._secao(p, 'File')
        self._campo(b, 0, 'File', 'arquivo_preencher', 'PubMed, Web of Science or Scopus export, or a merged file.',
                    '--fill-abstracts FILE', largura=56, arquivo=[('Exports', '*.txt *.csv *.ris')])
        self._campo(b, 2, 'Output', 'fill_out', 'Optional; default <file>_filled.txt', '--fill-out', largura=40)
        self._campo(b, 4, 'E-mail', 'email', 'For the PubMed step.', '--email', largura=40)
        self._opcao(b, 6, 'Keep records without abstract in the output', 'manter_sem_resumo', '',
                    '--keep-no-abstract')

    def _pagina_chaves(self, p):
        self._titulo(p, 'API keys',
                     'Keys typed here are saved in ~/.jurumim_keys.json (readable by you only) and used by the '
                     'interface and by the terminal tool. They are passed to the tool as environment variables, '
                     'never in the command line.')
        b = self._secao(p, 'Saved now')
        self.rotulo_salvas = tk.Label(b, text='', font=self.f['mono'], bg=COR['superficie'], fg=COR['tinta'],
                                      justify='left')
        self.rotulo_salvas.grid(row=0, column=0, columnspan=2, sticky='w')
        b = self._secao(p, 'Optional keys for filling abstracts')
        self._campo(b, 0, 'Semantic Scholar', 's2_apikey', 'Free; only speeds up large reviews.', 'S2_API_KEY',
                    secreto=True, largura=40)
        self._campo(b, 2, 'OpenAlex', 'openalex_apikey', 'Free; only for large reviews.', 'OPENALEX_API_KEY',
                    secreto=True, largura=40)
        botoes = tk.Frame(p, bg=COR['superficie'])
        botoes.pack(anchor='w', padx=24, pady=(12, 0))
        ttk.Button(botoes, text='Save typed keys', command=self._salvar_chaves).pack(side='left', padx=(0, 6))
        ttk.Button(botoes, text='Forget all saved keys', command=self._esquecer_chaves).pack(side='left')
        self._atualizar_salvas()

    # ------------------------------------------------------------------ dock: command + log
    def _doca(self):
        doca = tk.Frame(self.root, bg=COR['fundo'])
        doca.pack(fill='x', padx=16, pady=(0, 12))
        linha = tk.Frame(doca, bg=COR['fundo'])
        linha.pack(fill='x')
        tk.Label(linha, text='TERMINAL COMMAND', font=self.f['secao'], bg=COR['fundo'], fg=COR['suave']).pack(
            side='left')
        ttk.Button(linha, text='Copy', command=self._copiar).pack(side='right')
        self.comando = tk.Text(doca, height=2, font=self.f['mono'], relief='flat', wrap='char', bg=COR['superficie'],
                               fg=COR['tinta'], highlightthickness=1, highlightbackground=COR['linha'], padx=8, pady=6)
        self.comando.pack(fill='x', pady=(4, 8))
        self.comando.configure(state='disabled')

        acoes = tk.Frame(doca, bg=COR['fundo'])
        acoes.pack(fill='x')
        self.estado_rot = tk.Label(acoes, text='', font=self.f['corpo'], bg=COR['fundo'], fg=COR['suave'],
                                   anchor='w', justify='left', wraplength=700)
        self.estado_rot.pack(side='left', fill='x', expand=True)
        self.botao_rodar = ttk.Button(acoes, text='Run', style='Primario.TButton', command=self.rodar)
        self.botao_rodar.pack(side='right')
        self.botao_parar = ttk.Button(acoes, text='Stop', style='Parar.TButton', command=self.parar, state='disabled')
        self.botao_parar.pack(side='right', padx=(0, 8))
        self.botao_proximo = ttk.Button(acoes, text='', command=lambda: None)

        quadro_log = tk.Frame(doca, bg=COR['superficie'], highlightthickness=1, highlightbackground=COR['linha'])
        quadro_log.pack(fill='x', pady=(8, 0))
        self.log = tk.Text(quadro_log, height=7, font=self.f['mono'], relief='flat', wrap='word',
                           bg=COR['superficie'], fg=COR['tinta'], padx=8, pady=6)
        barra = ttk.Scrollbar(quadro_log, orient='vertical', command=self.log.yview)
        self.log.configure(yscrollcommand=barra.set, state='disabled')
        barra.pack(side='right', fill='y')
        self.log.pack(side='left', fill='both', expand=True)
        for tag, cor in (('aviso', COR['alerta']), ('erro', COR['erro']), ('ok', COR['folha']),
                         ('cmd', COR['rio']), ('suave', COR['suave'])):
            self.log.tag_configure(tag, foreground=cor)
        self.log.tag_configure('forte', font=self.f['mono'] + ('bold',))
        self._escrever('Output of each run appears here.\n', 'suave')

    # ------------------------------------------------------------------ command building
    def _comando_atual(self):
        e = self.estado()
        if self.pagina == 'search':
            return C.comando_busca(e, self.salvas)
        if self.pagina == 'merge':
            return C.comando_merge(e)
        if self.pagina == 'screen':
            return C.comando_triagem(e)
        if self.pagina == 'analyse':
            return C.comando_analise(e)
        if self.pagina == 'fill':
            return C.comando_preencher(e)
        return None

    def atualizar(self):
        if not hasattr(self, 'comando'):
            return
        caminho = str(self.pasta())
        self.rotulo_pasta.configure(text=caminho if len(caminho) <= 64 else self.t('…') + caminho[-63:])
        inst = self.v['scopus_key'].get() == 'institutional'
        for b in getattr(self, 'radios_view', []):
            b.state(['!disabled'] if inst else ['disabled'])
        modo = self.v['modo'].get()
        if hasattr(self, 'caixa_grupos'):
            self.caixa_grupos.configure(state='normal' if modo in ('groups', 'search') else 'disabled',
                                        bg=COR['superficie'] if modo in ('groups', 'search') else COR['fundo'])
            self.caixa_termos.configure(state='normal' if modo == 'search' else 'disabled',
                                        bg=COR['superficie'] if modo == 'search' else COR['fundo'])
        r = self._comando_atual()
        texto = 'Keys are saved on this page; nothing to run.' if r is None else C.texto_comando(r[0])
        self.comando.configure(state='normal')
        self.comando.delete('1.0', 'end')
        self.comando.insert('1.0', texto)
        self.comando.configure(state='disabled')
        if self.proc:
            return
        if r is None:
            self.botao_rodar.state(['disabled'])
            self.estado_rot.configure(text='', fg=COR['suave'])
        elif r[2]:
            self.botao_rodar.state(['disabled'])
            self.estado_rot.configure(text=self.t('  ·  ').join(r[2]), fg=COR['erro'])
        else:
            self.botao_rodar.state(['!disabled'])
            self.estado_rot.configure(text=f'Ready. Output goes to the topic folder "{self.pasta().name}".',
                                      fg=COR['suave'])

    # ------------------------------------------------------------------ running
    def rodar(self):
        r = self._comando_atual()
        if not r or r[2] or self.proc:
            return
        argv, env_extra, _ = r
        if self.pagina == 'search' and self.v['salvar_chaves'].get():
            self._salvar_chaves(silencioso=True)
        self.pasta().mkdir(parents=True, exist_ok=True)
        env = dict(os.environ, PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8', **env_extra)
        # The viewer (Streamlit) asks for an e-mail on its first run and waits for an answer;
        # with no terminal it would just exit. Headless mode skips that question, and the
        # window opens the browser itself when the address shows in the log.
        env.update(STREAMLIT_SERVER_HEADLESS='true', STREAMLIT_BROWSER_GATHER_USAGE_STATS='false')
        self.url_aberta = False
        cmd = [sys.executable, '-u', str(C.SCRIPT)] + argv
        kw = {}
        if sys.platform.startswith('win'):
            kw['creationflags'] = subprocess.CREATE_NEW_PROCESS_GROUP
        else:
            kw['start_new_session'] = True
        self._escrever(f"\n$ {C.texto_comando(argv)}\n", 'cmd')
        try:
            self.proc = subprocess.Popen(cmd, cwd=str(C.RAIZ), env=env, stdout=subprocess.PIPE,
                                         stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                                         text=True, encoding='utf-8', errors='replace', bufsize=1, **kw)
        except OSError as e:
            self._escrever(f"Could not start: {e}\n", 'erro')
            return
        self.inicio = time.time()
        self.parado = False
        self.pagina_rodando = self.pagina
        threading.Thread(target=self._bombear, args=(self.proc,), daemon=True).start()
        self.botao_rodar.state(['disabled'])
        self.botao_parar.state(['!disabled'])
        self.botao_proximo.pack_forget()
        self.estado_rot.configure(text=self.t('Running…'), fg=COR['ouro'])
        self._salvar_config()

    def _bombear(self, proc):
        for linha in proc.stdout:
            self.fila.put(('linha', linha))
        proc.wait()
        self.fila.put(('fim', proc.returncode))

    def _ler_fila(self):
        try:
            while True:
                tipo, dado = self.fila.get_nowait()
                if tipo == 'linha':
                    self._escrever(dado, self._tag(dado))
                    url = re.search(r'Local URL:\s*(http://\S+)', dado)
                    if url and not self.url_aberta:
                        self.url_aberta = True
                        abrir_url(url.group(1))
                        self._escrever(f"Viewer opened in the browser: {url.group(1)} (Stop closes it).\n", 'ok')
                else:
                    self._terminou(dado)
        except queue.Empty:
            pass
        if self.proc and self.inicio:
            self.estado_rot.configure(text=self.t(f'Running…  {int(time.time() - self.inicio)} s'))
        self.root.after(80, self._ler_fila)

    @staticmethod
    def _tag(linha):
        baixo = linha.lower()
        if 'error' in baixo or 'failed' in baixo or 'traceback' in baixo:
            return 'erro'
        if baixo.startswith('warning') or 'incomplete' in baixo or baixo.startswith('note:'):
            return 'aviso'
        if baixo.startswith(('saved:', 'prisma table:', 'frequency table', 'word search written',
                             'grouped frequency', 'kept (')):
            return 'ok'
        return None

    def _terminou(self, codigo):
        dur = int(time.time() - (self.inicio or time.time()))
        self.proc = None
        self.botao_parar.state(['disabled'])
        self.salvas = C.chaves_salvas()
        self._atualizar_salvas()
        self._sugerir_arquivos()
        self.atualizar()      # refresh the command first, then the final message on top of it
        if codigo == 0:
            self._escrever(f"Finished in {dur} s.\n", 'ok')
            self.estado_rot.configure(text=f'Finished in {dur} s. Files are in the topic folder.', fg=COR['folha'])
        elif codigo in (-signal.SIGTERM, -signal.SIGKILL, 143, 137) or (sys.platform.startswith('win') and codigo == 1
                                                                       and getattr(self, 'parado', False)):
            self._escrever(f"Stopped after {dur} s.\n", 'aviso')
            self.estado_rot.configure(text=f'Stopped after {dur} s.', fg=COR['alerta'])
        else:
            self._escrever(f"Ended with code {codigo} after {dur} s.\n", 'erro')
            self.estado_rot.configure(text=f'Ended with code {codigo}: see the log above.', fg=COR['erro'])
        proximo = {'search': ('screen', 'Next: 3 Screen'), 'merge': ('screen', 'Next: 3 Screen'),
                   'screen': ('analyse', 'Next: 4 Analyse')}.get(getattr(self, 'pagina_rodando', ''))
        if codigo in (0, 1) and proximo:
            self.botao_proximo.configure(text=proximo[1], command=lambda n=proximo[0]: self.mostrar(n))
            self.botao_proximo.pack(side='right', padx=(0, 8))

    def parar(self):
        if not self.proc:
            return
        self.parado = True
        self._escrever(self.t('Stopping…\n'), 'aviso')
        try:
            if sys.platform.startswith('win'):
                subprocess.run(['taskkill', '/PID', str(self.proc.pid), '/T', '/F'], capture_output=True)
            else:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGTERM)
                self.root.after(3000, self._matar)
        except (ProcessLookupError, OSError):
            pass

    def _matar(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
            except (ProcessLookupError, OSError):
                pass

    def _escrever(self, texto, tag=None):
        self.log.configure(state='normal')
        self.log.insert('end', texto.replace('\r', ''), tag or ())
        self.log.see('end')
        self.log.configure(state='disabled')

    def _copiar(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.comando.get('1.0', 'end').strip())
        self.estado_rot.configure(text='Command copied.', fg=COR['suave'])

    # ------------------------------------------------------------------ files
    def _escolher_pasta(self):
        d = filedialog.askdirectory(initialdir=str(self.pasta().parent if self.pasta().parent.exists() else C.RAIZ))
        if d:
            self.v['topico'].set(d)
            self._sugerir_arquivos()

    def _procurar(self, chave, tipos):
        inicial = self.pasta() if self.pasta().is_dir() else C.RAIZ
        f = filedialog.askopenfilename(initialdir=str(inicial), filetypes=tipos + [('All files', '*')])
        if f:
            self.v[chave].set(f)

    def _abrir(self, caminho):
        caminho = Path(caminho) if caminho else None
        if not caminho or not caminho.exists():
            self.estado_rot.configure(text=f'Not found yet: {caminho}', fg=COR['erro'])
            return
        if not abrir_no_sistema(caminho):
            self.estado_rot.configure(text=f'Could not open {caminho}', fg=COR['erro'])

    def _adicionar_arquivos(self):
        inicial = self.pasta() if self.pasta().is_dir() else C.RAIZ
        fs = filedialog.askopenfilenames(initialdir=str(inicial), filetypes=[
            ('Database exports', '*.txt *.csv *.ris'), ('All files', '*')])
        for f in fs:
            if f not in self.arquivos:
                self.arquivos.append(f)
        self._preencher_lista()

    def _adicionar_do_topico(self):
        for f in C.arquivos_do_topico(self.pasta()).get('brutos', []):
            if f not in self.arquivos:
                self.arquivos.append(f)
        self._preencher_lista()

    def _remover_arquivos(self):
        fora = {self.lista.item(i, 'text') + '|' + self.lista.set(i, 'pasta') for i in self.lista.selection()}
        self.arquivos = [a for a in self.arquivos if Path(a).name + '|' + str(Path(a).parent) not in fora]
        self._preencher_lista()

    def _preencher_lista(self):
        self.lista.delete(*self.lista.get_children())
        for a in self.arquivos:
            self.lista.insert('', 'end', text=Path(a).name, values=(C.formato_arquivo(a) if Path(a).is_file()
                                                                    else 'not found', str(Path(a).parent)))
        self.atualizar()

    def _topico_mudou(self):
        """Typing a topic name: point the steps at that folder's files once the typing stops."""
        if self._adiado:
            self.root.after_cancel(self._adiado)
        self._adiado = self.root.after(500, self._sugerir_arquivos)

    def _sugerir_arquivos(self):
        """Point steps 3 and 4 at the newest files of the topic folder."""
        achado = C.arquivos_do_topico(self.pasta())
        if achado.get('mesclado'):
            self.v['mesclado'].set(achado['mesclado'])
            self.v['prisma'].set(achado['prisma'])
            self.v['entrada'].set(achado.get('triado') or achado['mesclado'])
        if not self.v['merge_out'].get():
            nome = Path(self.v['topico'].get() or 'records').name
            self.v['merge_out'].set(f"Merged_{nome}.txt")
        if self.pagina == 'screen':
            self._desenhar_prisma()

    # ------------------------------------------------------------------ PRISMA drawing
    def _desenhar_prisma(self):
        c = self.prisma_canvas
        c.delete('all')
        caminho = self.v['prisma'].get()
        if not caminho or not Path(caminho).is_file():
            c.create_text(4, 20, anchor='w', font=self.f['corpo'], fill=COR['suave'],
                          text='No PRISMA table in this topic yet: run step 1 or step 2 first.')
            return
        try:
            r = C.resumo_prisma(caminho)
        except Exception as e:
            c.create_text(4, 20, anchor='w', font=self.f['corpo'], fill=COR['erro'], text=f'Could not read it: {e}')
            return

        def caixa(x, y, w, h, titulo, numero, detalhe='', cor=COR['tinta'], fundo=COR['superficie']):
            c.create_rectangle(x, y, x + w, y + h, outline=COR['linha'], fill=fundo)
            c.create_text(x + 10, y + 14, anchor='w', text=titulo.upper(), font=self.f['secao'], fill=COR['suave'])
            c.create_text(x + 10, y + 36, anchor='w', text=str(numero), font=self.f['titulo'], fill=cor)
            if detalhe:
                c.create_text(x + 10, y + h - 12, anchor='w', text=detalhe, font=self.f['dica'], fill=COR['suave'])

        def seta(x1, y1, x2, y2):
            c.create_line(x1, y1, x2, y2, fill=COR['suave'], arrow='last', arrowshape=(7, 8, 3))

        bases = self.t('  ·  ').join(f"{n.replace('.txt', '').replace('.csv', '')} {v}" for n, v in r['por_base'])
        caixa(0, 4, 330, 66, 'Records identified', r['identificados'], bases[:58])
        caixa(380, 4, 300, 66, 'Duplicates removed', r['duplicatas'])
        seta(330, 37, 380, 37)
        seta(165, 70, 165, 86)
        caixa(0, 86, 330, 66, 'Records screened', r['triados'])
        caixa(380, 86, 300, 66, 'Excluded', r['sem_resumo'] + r['excluidos'],
              self.t(f"{r['sem_resumo']} without abstract  ·  {r['excluidos']} by you"))
        seta(330, 119, 380, 119)
        seta(165, 152, 165, 168)
        caixa(0, 168, 330, 66, 'Included', r['incluidos'], f"maybe {r['talvez']}", cor=COR['folha'],
              fundo=COR['folha_clara'])
        if r['pendentes']:
            caixa(380, 168, 300, 66, 'Not yet screened', r['pendentes'], 'fill in screening_decision',
                  cor=COR['alerta'])

    # ------------------------------------------------------------------ keys
    def _atualizar_salvas(self):
        if not hasattr(self, 'rotulo_salvas'):
            return
        try:
            from databases.credenciais import mascarar
        except Exception:
            mascarar = lambda v, s=True: '****'  # noqa: E731
        linhas = []
        for k in ('email', 'wos_apikey', 'wos_api', 'scopus_apikey', 'scopus_key'):
            if self.salvas.get(k):
                valor = self.salvas[k] if k in ('email', 'wos_api', 'scopus_key') else mascarar(self.salvas[k])
                linhas.append(f"{k:15s} {valor}")
        self.rotulo_salvas.configure(text='\n'.join(linhas) or 'Nothing saved.')

    def _salvar_chaves(self, silencioso=False):
        try:
            from databases import credenciais
        except Exception as e:
            self._escrever(f"Could not save keys: {e}\n", 'erro')
            return
        salvos = []
        for chave in ('wos_apikey', 'scopus_apikey', 's2_apikey', 'openalex_apikey', 'email'):
            valor = self.v[chave].get().strip()
            if valor:
                credenciais.salvar(chave, valor)
                salvos.append(chave)
        if self.v['wos_apikey'].get().strip():
            credenciais.salvar('wos_api', self.v['wos_api'].get())
        if self.v['scopus_apikey'].get().strip():
            credenciais.salvar('scopus_key', self.v['scopus_key'].get())
        self.salvas = C.chaves_salvas()
        self._atualizar_salvas()
        if not silencioso:
            self.estado_rot.configure(text=f"Saved: {', '.join(salvos) or 'nothing typed'}", fg=COR['suave'])

    def _esquecer_chaves(self):
        argv, env, _ = C.comando_esquecer()
        self._escrever(f"\n$ {C.texto_comando(argv)}\n", 'cmd')
        r = subprocess.run([sys.executable, str(C.SCRIPT)] + argv, cwd=str(C.RAIZ), capture_output=True, text=True)
        self._escrever(r.stdout + r.stderr)
        self.salvas = C.chaves_salvas()
        self._atualizar_salvas()

    # ------------------------------------------------------------------ settings
    def _ler_config(self):
        try:
            return json.loads(PASTA_CONFIG.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            return {}

    def _salvar_config(self):
        estado = {k: v.get() for k, v in self.v.items() if k not in self.secretos}
        dados = {'estado': estado, 'arquivos': self.arquivos, 'pagina': self.pagina,
                 'textos': {k: w.get('1.0', 'end').strip() for k, w in self.textos.items()},
                 'geometria': self.root.geometry()}
        try:
            PASTA_CONFIG.write_text(json.dumps(dados, indent=1), encoding='utf-8')
        except OSError:
            pass

    def _fechar(self):
        if self.proc:
            self.parar()
        self._salvar_config()
        self.root.destroy()


def main():
    root = tk.Tk()
    App(root)
    root.mainloop()
