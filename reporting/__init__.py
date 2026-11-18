"""
Report of an analysed file (--report): word co-occurrence network, trends per
year, PRISMA 2020 flow diagram and methods text, written into <input>_report/.

  artigos.py        records of the analysed file (ID, year, title, abstract)
  rede.py           co-occurrence network of adjacent words; tables and GraphML
  rede_html.py      the interactive network page
  tendencias.py     articles and terms per year; table and chart
  prisma_figura.py  PRISMA 2020 flow diagram (PNG and SVG)
  metodos.py        methods text in English (and Portuguese with --report-pt)
"""
