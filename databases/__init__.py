"""
Extra bibliographic databases for Jurumim Revisor.

Every source is turned into MEDLINE records, so the rest of the tool
(frequency tables, --articles, --viewer) reads them exactly like a PubMed file.

  medline.py   record type shared by all sources, MEDLINE reader and writer
  wos.py       Web of Science: export files (plain text / tab-delimited) and APIs
  dedup.py     duplicate removal across sources (PMID, DOI, title + year)
"""
