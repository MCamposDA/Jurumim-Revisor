# Jurumim Revisor

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)
![PubMed](https://img.shields.io/badge/input-PubMed%20MEDLINE-326599.svg)
![Streamlit](https://img.shields.io/badge/viewer-Streamlit-FF4B4B.svg)

<p align="center"><img src="viewer/assets/jurumim_logo.jpg" width="160" alt="Jurumim Revisor logo"></p>

Auxiliary software for systematic reviews and literature analysis. It reads PubMed exports (MEDLINE format), as well as Web of Science and Scopus records converted to the same format, counts terms in titles and abstracts, and writes Excel tables. A Streamlit viewer shows the results by word, author and article.

It was built for the sand fly literature (*Lutzomyia* / *Nyssomyia*), but works with any PubMed query.

---

## Quick start

```bash
git clone https://github.com/MCamposDA/Jurumim-Revisor.git
cd Jurumim-Revisor
pip install -r requirements.txt

# 1. Get the records (or export them from pubmed.ncbi.nlm.nih.gov, see below)
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --email you@example.org

# 2. Word frequency table
python3 Jurumim_Revisor.py Pubmed_Nyssomyia.txt general.xlsx

# 3. Or do everything at once: table + per-article tables + viewer in the browser
python3 Jurumim_Revisor.py Pubmed_Nyssomyia.txt general.xlsx --viewer
```

For a systematic review over PubMed, Web of Science and Scopus (merge without duplicates, PRISMA table, screening), see [the step-by-step pipeline](#systematic-review-pipeline-step-by-step):

```bash
python3 Jurumim_Revisor.py --merge Pubmed_Nyssomyia.txt savedrecs.txt scopus.csv --merge-out Nyssomyia_all.txt
# fill in screening_decision in Nyssomyia_all_prisma.xlsx, then:
python3 Jurumim_Revisor.py --screen Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt general.xlsx --viewer
```

`python3 initialize.py` opens the [desktop app](#desktop-app), which runs the same commands from a window.

NLTK data (`punkt`, `punkt_tab`, `stopwords`, and `wordnet` for `--lemma`) is downloaded automatically on first use.

> **Python version:** use 3.9 or newer, except **3.9.7**, which Streamlit does not support. The core script (`Jurumim_Revisor.py`) runs on 3.9.7; only the viewer does not.

---

## Input data

The input is a plain-text file in **PubMed (MEDLINE) format**, where every record starts with a `PMID- ` line. You can get it in two ways:

- **From the website:** search on [PubMed](https://pubmed.ncbi.nlm.nih.gov/), then *Save* → *Selection: All results* → *Format: PubMed* → *Create file*. The website caps this export at 10,000 records.
- **From the script:** `-p` / `--pubmed` (see below), which has no 10,000 limit.

Other formats (CSV, XML, abstracts in plain text) are rejected with an error message. Web of Science and Scopus exports are first converted with `--merge` (see [Web of Science, Scopus and multiple databases](#web-of-science-scopus-and-multiple-databases)).

---

## Usage

```
python3 Jurumim_Revisor.py INPUT.txt [OUTPUT.xlsx] [options]
```

Put the input and output files **first**. `--ws` and `-sw` take several values and consume every word after them until the next flag.

### Modes

| Mode | Command | Output |
|---|---|---|
| Word frequency | `input.txt out.xlsx` | every word, sorted by frequency |
| Synonym groups | `input.txt out.xlsx -st virus -so viral -so virome` | same table, with each group merged into one row |
| Word search | `input.txt out.xlsx --ws "science park" covid-19 t-cell` | one row per searched term |
| Word search, grouped | `input.txt out.xlsx --ws -st sandfly -so phlebotomine` | one row per group (loose terms and groups can be mixed) |
| Per article | `input.txt --articles` | `PMID/<pmid>/<pmid>.xlsx` and `<pmid>_info.txt` |
| Viewer | `input.txt out.xlsx --viewer` (combines with any table mode) | writes `out.xlsx`, builds `PMID/` if needed, opens the viewer |
| PubMed download | `-p -q "QUERY" --email you@example.org [--apikey KEY]` | `Pubmed_<query>.txt` |
| Several databases | `-p -q "QUERY" --db pubmed wos scopus` (or `--db all`) | one file per database, `Merged_<query>.txt`, `Merged_<query>_prisma.xlsx` |
| Merge files | `--merge FILE... --merge-out OUT.txt` | `OUT.txt` (no duplicates), `OUT_prisma.xlsx` |
| Screening | `--screen MERGED.txt PRISMA.xlsx [--keep include maybe]` | `MERGED_screened.txt` |
| Fill abstracts | `--fill-abstracts FILE.txt`, or `--fill-abstracts` with `--merge` / `-p --db` | `FILE_filled.txt`, or the merged file with the missing abstracts filled |
| Saved keys | `--show-keys` / `--forget-keys` | shows (masked) / deletes the saved e-mail and API keys |

### Options

| Flag | Meaning |
|---|---|
| `-sw`, `--stopword WORD_OR_FILE ...` | Extra stopwords. Each value is a word or a text file (words separated by spaces, commas or new lines). Works in every mode. |
| `-st TERM` | Starts a group; TERM names the merged row. |
| `-so SYNONYM` | Adds a synonym to the last `-st`. |
| `--ws`, `--wordsearch TERM ...` | Literal search (see *How counting works*). |
| `-art`, `--articles` | Writes one folder per PMID into `./PMID`. |
| `-v`, `--viewer` | After writing the output table, opens the Streamlit viewer (see *Viewer*). |
| `--lemma` | Counts noun lemmas (`viruses` → `virus`, `mice` → `mouse`). Off by default. Does not affect `--ws`. |
| `-p`, `--pubmed` | Downloads a query; requires `-q/--query` and `--email`. |
| `--apikey KEY` | NCBI API key. Optional; raises the request rate from 3 to 10 per second. |

### Output columns

| Column | Meaning |
|---|---|
| `word` / `term` | Word or group name (`term` for `--ws` tables: searched term or group name) |
| `tiab_frequency` | Occurrences in title + abstract |
| `ti_frequency` | Occurrences in the title |
| `ab_frequency` | Occurrences in the abstract |
| `articles` | Number of **distinct** articles containing the word (for a group: at least one of its terms) |
| `articles_pubmed` / `articles_wos` / `articles_scopus` | Merged input only (see [Web of Science, Scopus](#web-of-science-scopus-and-multiple-databases)): the same count over the records found in PubMed / Web of Science / Scopus, for the databases present in the file. An article found in several databases counts in each of their columns, so the columns can add up to more than `articles` |

The per-article tables in `PMID/` have the same columns except `articles`.

---

## How counting works

**Text preparation (all modes)**
1. Only the `TI` (title) and `AB` (abstract) fields are read.
2. Unicode hyphens (`‐ ‑ ‒ −`) become `-`; en and em dashes (`– —`) become spaces.
3. *Sand fly* variants (`sand fly`, `sand flies`, `sand-fly`, `sand-flies`, `sandflies`) are merged into **`sandfly`**. This is intentional for the sand fly literature; edit `normalizar_sandfly()` to change or remove it.

**Word frequency, groups and `--articles`**
- Text is lowercased; slashes and single quotes are split before tokenizing (NLTK `word_tokenize`).
- Only purely alphabetic tokens are kept. Tokens with digits or hyphens (`covid-19`, `t-cell`) are dropped here; use `--ws` for them.
- English stopwords (NLTK) and your `-sw` words are removed.
- With `--lemma`, WordNet noun lemmas are counted. Words of up to three letters (mostly acronyms: `lps`, `ros`) and a list of known bad cases (`chagas`, `aids`, `doses`, `data`, `species`, genus names…) are left unchanged; see `LEMMA_EXCEPTIONS`.
- In a group, frequencies are **summed**. The article count is the **union** of articles, so an article that contains both `virus` and `viral` is counted once.

**Word search (`--ws`)**
- Matches the literal term in the lowercased text. It is not tokenized, and stopwords are not removed.
- Spaces in a phrase match any whitespace. `-` and `/` are matched literally (`t-cell`, `balb/c`).
- The term must not touch letters, digits or hyphens on either side, so `virus` does not match `viruses` or `virus-like`. Search the variants you need, or group them with `-st/-so`.
- Every occurrence is counted.

**PubMed download (`-p`)**
- NCBI returns at most 9,999 IDs per search. Larger queries are split automatically by publication date until each slice fits, and the parts are joined.
- Records are fetched in batches of 500, with retries.
- At the end, the number of downloaded records is compared with the count PubMed reports, and a warning is printed if they differ.
- Any characters that are not valid in a filename are replaced by `_` in the output name.

---

## Viewer

```bash
python3 Jurumim_Revisor.py input.txt output.xlsx --viewer
```

What `--viewer` does:
1. It runs the requested analysis and writes `output.xlsx`. Any table mode works: plain, `-st/-so`, `--ws`, `-sw`, `--lemma`.
2. It builds `PMID/` (the same output as `--articles`) unless that folder already has a table for every PMID of the input file.
   - Add `--articles` to force a rebuild, for example after changing `-sw` or `--lemma`.
   - Or delete the folder.
3. It opens the app in the browser. Stop it with Ctrl+C.

Tables written by older versions, with Portuguese column names, are still read.

| Tab | Content |
|---|---|
| General Frequency | totals, full table and top-N words from the general table |
| Authors (General) | every author (full name, `FAU` field), number of articles, times as first/middle/last author, minimum-articles filter |
| Articles | searchable by title: authors, first/last author country, identifiers, and the word table from `--articles` |

**Author country.** In MEDLINE, each `AD` (affiliation) line belongs to the author (`FAU`) right above it.
- The viewer takes the country of the first and last authors from **their own** affiliations only.
- An author without an affiliation is shown as *Unknown*. Affiliations are never borrowed from co-authors.
- Countries are recognized by whole-word matching against a list of countries and common variants (`USA`, `Brasil`, `P.R. China`, US state names…).
- E-mail addresses are ignored.
- When an affiliation names several countries, the last one wins.

---

## Web of Science, Scopus and multiple databases

Web of Science and Scopus records are converted to MEDLINE, so every mode (`--ws`, `-st`, `--articles`, `--viewer`) works on them as it does on a PubMed file. The converters are in `databases/wos.py` and `databases/scopus.py`.

### Systematic review pipeline, step by step

```
 1. GET                         2. CONVERT AND MERGE                 3. SCREEN                  4. ANALYSE
 PubMed (.txt MEDLINE) ──┐
 WoS (.txt / tab)  ──────┼──► --merge   (or -p --db ...)            fill in                    the usual modes:
 Scopus (.csv / .ris) ───┘     ├─ wos.py / scopus.py convert         screening_decision          frequency table, --ws,
                               ├─ dedup.py removes duplicates        in _prisma.xlsx             -st, --lemma, --articles,
                               ├─ medline.py writes MEDLINE               │                      --viewer
                               └─ prisma.py writes the table              ▼                          ▲
                               ▼                                     --screen ──► _screened.txt ─────┘
                       Merged.txt + Merged_prisma.xlsx               (records marked include)
```

Run the commands from the folder that holds the files, or give the full path of the script (`python3 /path/to/Jurumim-Revisor/Jurumim_Revisor.py ...`).

To keep each review in its own folder, add `--outdir results/<topic>` to every step. All files of the run go into that folder (created if needed). Input files are looked up first where you run the command and then inside the folder, so the steps of one topic can refer to each other by file name:

```bash
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db all --fill-abstracts --outdir results/Nyssomyia
python3 Jurumim_Revisor.py --screen Merged_Nyssomyia.txt Merged_Nyssomyia_prisma.xlsx --outdir results/Nyssomyia
python3 Jurumim_Revisor.py Merged_Nyssomyia_screened.txt general.xlsx --outdir results/Nyssomyia
```

Without `--outdir`, files are written where you run the command. The desktop app always works in a topic folder.

#### Step 0: install (once)

```bash
cd Jurumim-Revisor
pip install -r requirements.txt
```

The database modules only need the standard library and the packages in `requirements.txt`. The desktop app also needs Tkinter (see [Desktop app](#desktop-app)).

#### Step 1: get the records

Use the same search in every database, each in its own syntax, and report it in the PRISMA flow. The records can come from export files, from the APIs, or from both.

Export files from the websites (no API key needed):

| Database | How to export | File |
|---|---|---|
| PubMed | Search → *Save* → *Selection: All results* → *Format: PubMed* → *Create file* (website limit: 10,000), or `python3 Jurumim_Revisor.py -p -q "Nyssomyia"` (no limit) | `pubmed-....txt` / `Pubmed_<query>.txt` |
| Web of Science | Search → *Export* → *Plain text file* (or *Tab delimited file*) → *Records 1 to 1000* → *Record Content: Full Record*. Above 1,000 results, export in batches (1-1000, 1001-2000...) | `savedrecs.txt`, one per batch |
| Scopus | Select all → *Export* → *CSV*, with citation information, bibliographical information (it includes the affiliations) and *Abstract & keywords*. *RIS* also works, but its affiliations are not linked to authors | `scopus.csv` |

Download through the APIs:

```bash
# all three databases (each one is also saved on its own)
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db all

# any combination
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db pubmed wos
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db pubmed scopus

# each database with its own query syntax
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db all --wos-query 'TS=(Nyssomyia) AND PY=(2015-2025)' --scopus-query 'TITLE-ABS-KEY(Nyssomyia) AND PUBYEAR > 2014'

# one database
python3 Jurumim_Revisor.py -p --db wos --wos-query 'TS=(Nyssomyia)'
python3 Jurumim_Revisor.py -p --db scopus --scopus-query 'TITLE-ABS-KEY(Nyssomyia)'

# free keys, no institution needed: titles only, and a warning says so
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db wos --wos-api starter
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db scopus --scopus-key personal
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db pubmed wos scopus --wos-api starter --scopus-key personal

# institutional Scopus key, titles only (STANDARD view)
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db scopus --scopus-view standard
```

If the e-mail or a key is missing, it is asked for in the terminal (see [API keys and e-mail](#api-keys-and-e-mail)). They can also be given as flags or environment variables.

Both, for example PubMed through the API and WoS and Scopus as files:

```bash
python3 Jurumim_Revisor.py -p -q "Nyssomyia"
python3 Jurumim_Revisor.py --merge Pubmed_Nyssomyia.txt savedrecs.txt scopus.csv --merge-out Nyssomyia_all.txt
```

#### Step 2: merge without duplicates

```bash
python3 Jurumim_Revisor.py --merge Pubmed_Nyssomyia.txt savedrecs.txt scopus.csv --merge-out Nyssomyia_all.txt
# -> Nyssomyia_all.txt (MEDLINE, no duplicates) + Nyssomyia_all_prisma.xlsx

# several WoS batches: records present in more than one batch are kept once (WoS UT)
python3 Jurumim_Revisor.py --merge Pubmed_Nyssomyia.txt savedrecs1.txt savedrecs2.txt savedrecs3.txt scopus.csv --merge-out Nyssomyia_all.txt

# two databases only
python3 Jurumim_Revisor.py --merge Pubmed_Nyssomyia.txt savedrecs.txt --merge-out Nyssomyia_pw.txt
```

The order of the files does not change the result (see [Duplicates](#duplicates)), and a merged file can be merged again with new files. `-p --db` does this step by itself and writes `Merged_<query>.txt` and `Merged_<query>_prisma.xlsx`.

Records without an abstract are left out of the analysis. Once duplicates are removed (and the missing abstracts looked up, with `--fill-abstracts`), the records that still have no abstract, such as letters, editorials or records from title-only APIs, go to `<out>_no_abstract.txt` instead of `<out>.txt`. The frequency tables, `--articles` and the viewer only see articles with an abstract. The PRISMA table still lists them, marked `exclude` with the reason `No abstract available`. With `--keep-no-abstract` they stay in `<out>.txt`, are counted by their title and are not marked. A PubMed file given directly to the analysis is analysed with all its records, with or without abstract.

To fill in missing abstracts in the same step (see [Filling missing abstracts](#filling-missing-abstracts---fill-abstracts)):

```bash
python3 Jurumim_Revisor.py --merge Pubmed_Nyssomyia.txt savedrecs.txt scopus.csv --merge-out Nyssomyia_all.txt --fill-abstracts
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db all --wos-api starter --scopus-key personal --fill-abstracts
```

#### Step 3: screen

1. Open `Nyssomyia_all_prisma.xlsx`, sheet `records`, and fill in `screening_decision` (include / exclude / maybe) and, if you want, `exclusion_reason`. The `summary` sheet follows your changes.
2. Keep only the records you chose:

```bash
python3 Jurumim_Revisor.py --screen Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx
# -> Nyssomyia_all_screened.txt (include only)

python3 Jurumim_Revisor.py --screen Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx --keep include maybe --screen-out Nyssomyia_final.txt
```

#### Step 4: analyse

The usual modes, run on the screened file:

```bash
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt general.xlsx                  # + articles_pubmed / _wos / _scopus
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt general_lemma.xlsx --lemma
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt groups.xlsx -st sandfly -so phlebotomine -so phlebotomines
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt search.xlsx --ws "sand flies" leishmaniasis covid-19
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt general.xlsx -sw study results
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt --articles
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt general.xlsx --viewer
```

#### Files written at each step

| Step | File | Content |
|---|---|---|
| `-p` (PubMed) | `Pubmed_<query>.txt` | PubMed records as downloaded |
| `-p --db wos` / `scopus` | `WOS_<query>.txt`, `Scopus_<query>.txt` | That database's records, in MEDLINE |
| `--merge`, or `-p --db` with anything other than PubMed alone | `<out>.txt` / `Merged_<query>.txt` | One MEDLINE file without duplicates, with `DB`, `UT`, `TC`, `EID`, `TCSC` lines |
| | `<out>_no_abstract.txt` | Records still without abstract: not analysed, marked excluded in the PRISMA table (not written with `--keep-no-abstract`) |
| | `<out>_prisma.xlsx` | Sheets `summary`, `records`, `duplicates_removed` |
| `--fill-abstracts FILE` | `<FILE>_filled.txt` (+ `<FILE>_filled_no_abstract.txt`) | The same records with the missing abstracts filled in (`AB`, and `ABS` for the source); the input file is not changed |
| `--screen` | `<out>_screened.txt` | Only the records kept, unchanged |
| analysis | `general.xlsx`... | The usual tables, plus one `articles_<database>` column per database for a merged input |

#### What each database needs

| Database | As files | Through the API |
|---|---|---|
| PubMed | nothing | an e-mail (`--apikey` optional) |
| Web of Science | access to the website | a Clarivate key: Expanded (abstracts, institutional subscription) or Starter (free, titles only, `--wos-api starter`) |
| Scopus | access to the website | an Elsevier key from [dev.elsevier.com](https://dev.elsevier.com), free for anyone. Institutional (`--scopus-key institutional`, the default): abstracts and all authors, from the institution's network or with `--scopus-insttoken`. Personal (`--scopus-key personal`): titles and first author only, at most 5,000 records per search (larger searches are split by year) |

| Database | Source | Abstracts |
|---|---|---|
| WoS | Export file (plain text / tab-delimited, *Full Record*) | yes |
| WoS | `--wos-api expanded` (default) | yes |
| WoS | `--wos-api starter` | no, titles only |
| Scopus | CSV export (with *Abstract & keywords*) | yes |
| Scopus | RIS export | yes, but no author gets a country |
| Scopus | institutional key, `--scopus-view complete` (default) | yes |
| Scopus | institutional key, `--scopus-view standard` | no, titles and first author only |
| Scopus | `--scopus-key personal` | no, titles and first author only |

Records that only the WoS Starter API, a personal Scopus key or the Scopus STANDARD view returned are counted by their title, and their authors have no country. For frequency analysis, export files or institutional keys are better. The free keys still bring the records, their IDs and citation counts, which matter for duplicates and for the PRISMA counts, and `--fill-abstracts` recovers most of the missing abstracts (see [Filling missing abstracts](#filling-missing-abstracts---fill-abstracts)).

#### When a download stops or a database fails

- A quota or network error in the middle of a download (the free WoS Starter plan allows 50 requests a day; Scopus keys have a weekly quota) keeps the records already fetched. A warning says the search is incomplete and how many records are missing. A refused key or a rejected query stops the download straight away.
- If one database fails (wrong key, no access), the others still run and are merged without it. The run ends with a warning naming that database and exit code 1. Fix the problem and run again, or add the database later with `--merge`.

#### Keys without an institution

WoS and Scopus both give free API keys to anyone:

| | WoS Starter (`--wos-api starter`) | Scopus personal (`--scopus-key personal`) |
|---|---|---|
| Where | [developer.clarivate.com](https://developer.clarivate.com/apis/wos-starter), *Free Trial* plan | [dev.elsevier.com](https://dev.elsevier.com) → *I want an API key* |
| Records | title, journal, year, DOI, PMID, authors, keywords | title, journal, year, DOI, PMID, first author only, citations |
| Abstracts / affiliations | no / no | no / no |
| Limits | free plan: 1 request per second, 50 per day (50 records per request) | 5,000 records per search, about 20,000 requests per week (25 records per request) |

With a personal Scopus key, a search with more than 5,000 records is split by publication year, as PubMed searches above 9,999 are, so all its records are retrieved. A single year with more than 5,000 records gives only its first 5,000; the warning says how many were left out and suggests narrowing the query (`DOCTYPE(ar)`, `SUBJAREA(...)`). Records without a year are reported too.

### Filling missing abstracts (`--fill-abstracts`)

Records without an abstract are counted by their title only. `--fill-abstracts` looks for each missing abstract in open sources, none of which needs an institution, and uses the first English one it finds:

| Order | Source | Looked up by | Key |
|---|---|---|---|
| 1 | PubMed | PMID | the e-mail already used for PubMed |
| 2 | Crossref | DOI | none (abstract deposited by the publisher) |
| 3 | Semantic Scholar | DOI | optional: `--s2-apikey` or `S2_API_KEY` (without it, busy responses are retried) |
| 4 | OpenAlex | DOI | optional: `--openalex-apikey` or `OPENALEX_API_KEY` (without it, a small daily budget shared per network) |

```bash
# a file on disk -> <FILE>_filled.txt (the input is not changed)
python3 Jurumim_Revisor.py --fill-abstracts WOS_Nyssomyia.txt
python3 Jurumim_Revisor.py --fill-abstracts Nyssomyia_all.txt --fill-out Nyssomyia_all_full.txt

# while merging or downloading: the merged file is filled
python3 Jurumim_Revisor.py --merge Pubmed_Nyssomyia.txt savedrecs.txt scopus.csv --merge-out Nyssomyia_all.txt --fill-abstracts
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db all --fill-abstracts
```

On a merge (`--merge` or `-p --db`), the steps are:

1. duplicates are removed, with the priority PubMed > WoS > Scopus;
2. a kept record without abstract takes the abstract of its removed copy, if that copy has one;
3. the records that still have no abstract are looked up in the sources above;
4. those still without abstract go to `<out>_no_abstract.txt` and are marked excluded.

An article found in several databases is therefore looked up once, and only when none of your own downloads had its abstract.

Records that already have an abstract are never changed. A filled record gains `AB` and `ABS` (the source). The PRISMA table has an `abstract_source` column, empty when the abstract came with the record, and an *Abstracts* block in `summary` with the number filled from each source and the reasons for the rest. These numbers belong in the methods section.

Latin American journals often give the abstract in Portuguese or Spanish, or in two languages in the same text, and the sources do not always return the same version. Sentences in Portuguese, Spanish or French are dropped, using stopwords that only exist in each of those languages, and an abstract is accepted only if at least 100 characters of English remain; otherwise the next source is tried. Records whose abstract exists only in another language are counted separately. Crossref's JATS markup, headings such as `Abstract` or `Resumo`, and copyright notices are removed.

Publisher-deposited text is tried first. OpenAlex comes last because some of its abstracts were extracted from PDFs (`Lutzornyia` for *Lutzomyia*) and a few are not abstracts at all (the title in three languages, which the English check rejects). Europe PMC is not queried: it indexes PubMed and PubMed Central articles, which the PubMed lookup already covers.

Abstracts belong to their publishers. Use them for the analysis, but do not publish the filled files.

### API keys and e-mail

Each value needed by `-p` is taken from, in this order:

1. its flag: `--email`, `--wos-apikey`, `--scopus-apikey`
2. its environment variable: `WOS_API_KEY`, `SCOPUS_API_KEY` (and `SCOPUS_INSTTOKEN` for the token)
3. the keys saved on a previous run, in `~/.jurumim_keys.json`
4. a question in the terminal

Missing values are asked for one at a time. Keys are typed hidden, like a password. Enter (or Ctrl+D) skips that database and the search goes on with the others; Ctrl+C cancels. For a WoS key you are also asked whether it is an Expanded or a Starter key, and for a Scopus key whether it is institutional or personal; the answer is saved with the key. After each value you are asked whether to save it, and nothing is saved unless you answer `y`.

```
$ python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db pubmed wos

E-mail for NCBI (PubMed) is needed for PubMed (any e-mail of yours; NCBI asks for one to contact heavy users).
E-mail for NCBI (PubMed) (Enter to skip PubMed): you@example.org
Save it in /home/you/.jurumim_keys.json for next time? [y/N]: y
Saved (you@example.org).

Web of Science API key is needed for Web of Science (developer.clarivate.com (Expanded: institutional subscription; Starter: free)).
Web of Science API key (typed hidden; Enter to skip Web of Science):
Is it an Expanded (abstracts) or a Starter (titles only) key? [E/s]: e
Save it in /home/you/.jurumim_keys.json for next time? [y/N]: n
```

On the next run the saved values are used without asking (`Using saved Web of Science API key: abcd…wxyz`).

- The keys file can only be read by its owner (permissions `600`, like `~/.netrc`), and keys are always shown masked.
- `--show-keys` shows what is saved, masked; `--forget-keys` deletes the file.
- With `--no-prompt` nothing is asked, and a missing value stops the run with an error that names it. Nothing is asked either when there is no terminal (scripts, servers, piped input). In those cases, pass the values as flags or environment variables:

```bash
export WOS_API_KEY=your-clarivate-key
export SCOPUS_API_KEY=your-elsevier-key
export SCOPUS_INSTTOKEN=your-token        # optional
python3 Jurumim_Revisor.py -p -q "Nyssomyia" --db all --email you@example.org --no-prompt
```

A variable set with `export` lasts until the terminal is closed and does not go into the shell history, which a key typed as a flag does.

### All options

| Option | Meaning |
|---|---|
| `--db pubmed wos scopus` / `--db all` | Databases searched by `-p`, in any combination (default `pubmed`). `all` means the three |
| `--wos-apikey KEY` | Clarivate key (default: `WOS_API_KEY`, then the saved key) |
| `--wos-api expanded\|starter` | Which WoS API the key belongs to (default: `expanded`, or the type saved with the key) |
| `--wos-query Q` | WoS query. Without it, `-q` is sent as `TS=(...)` |
| `--scopus-apikey KEY` | Elsevier key (default: `SCOPUS_API_KEY`, then the saved key) |
| `--scopus-insttoken TOKEN` | Elsevier institutional token, for the COMPLETE view outside the institution's network (default: `SCOPUS_INSTTOKEN`) |
| `--scopus-key institutional\|personal` | Kind of Elsevier key: `institutional` (abstracts; institution network or token) or `personal` (no institution; titles only, searches above 5,000 split by year). Default: `institutional`, or the kind saved with the key |
| `--scopus-view complete\|standard` | Institutional key only. `complete`: abstracts and all authors; `standard`: titles and first author only |
| `--scopus-query Q` | Scopus query. Without it, `-q` is sent as `TITLE-ABS-KEY(...)` |
| `--merge FILE...` / `--merge-out OUT.txt` | Merge files on disk (default output `Merged_records.txt`) |
| `--screen MERGED.txt PRISMA.xlsx` / `--keep` / `--screen-out` | Screening (see [Screening](#screening---screen)) |
| `--keep-no-abstract` | With `--merge` / `-p --db`: keep the records without abstract in the merged file (counted by title) and do not mark them as excluded |
| `--fill-abstracts [FILE]` / `--fill-out OUT.txt` | Fill in missing abstracts (see [Filling missing abstracts](#filling-missing-abstracts---fill-abstracts)) |
| `--s2-apikey KEY` / `--openalex-apikey KEY` | Optional keys for `--fill-abstracts` (default: `S2_API_KEY`, `OPENALEX_API_KEY`) |
| `--outdir DIR` | Write all files of the run into `DIR`, for example one folder per topic. Inputs are looked up where you run the command, then in `DIR` |
| `--no-prompt` | Never ask for a missing e-mail or key |
| `--show-keys` / `--forget-keys` | Show (masked) or delete the saved e-mail and keys |

WoS and Scopus do not understand PubMed field tags such as `[tiab]`. A warning is printed when `-q` contains them; use `--wos-query` and `--scopus-query` to give each database its own query.

### Duplicates

An article found in more than one database is kept once. Databases are merged in a fixed order, PubMed > WoS > Scopus, then by file name, whatever the order in which the files are given, so the same files always give the same result. PubMed comes first because its records have MeSH terms and affiliations for every author. A later record is a duplicate of an earlier one when it has:

1. the same PMID (WoS and Scopus records carry it when the article is in MEDLINE), or the same WoS UT or Scopus EID (overlapping exports of one database);
2. the same DOI (case and `https://doi.org/` ignored);
3. the same title, reduced to letters and digits (case and accents ignored), and publication years at most 1 apart. Titles shorter than 30 characters ("Editorial", "Erratum") are never compared this way.

Records with different PMIDs are never merged, since a PMID identifies one article. A title match is also refused when both records have a DOI and the DOIs differ, so two articles that share a generic title in the same year stay separate.

The kept record is written as it was (a PubMed record exactly as downloaded). It only gains `DB` (the databases where it was found) and, from its copies, `UT` and `TC` (WoS ID and times cited) and `EID` and `TCSC` (Scopus ID and cited by). Every removed record is listed in the `duplicates_removed` sheet of `<output>_prisma.xlsx` with the key that matched, and the counts per database are printed at the end.

When the kept record has no abstract and its removed copy has one in English, the kept record takes it (`ABS - Scopus (duplicate record)`, for example). This happens on every merge. Otherwise the abstract of a Scopus CSV record would be lost behind a WoS Starter record of the same article, and `--fill-abstracts` would look for it elsewhere. A kept record that already has an abstract is never changed.

### PRISMA table (`<output>_prisma.xlsx`)

Written next to the merged file by `--merge` and by `-p --db`:

| Sheet | Content |
|---|---|
| `summary` | PRISMA 2020 counts: records identified per file or database and in total, duplicates removed (and by which key), unique records per combination of databases (PubMed only, WoS and Scopus...), records screened. *Excluded* (and, within it, *no abstract available*), *included*, *maybe* and *not yet screened* are Excel formulas over the `records` sheet, so they change as you screen |
| `records` | One row per unique article: `record_id` (the `PMID-` line of the merged file), `pmid` (empty when the article is not in PubMed/MEDLINE), `wos_ut` (empty when not in WoS), `scopus_eid` (empty when not in Scopus), `doi`, `in_pubmed`, `in_wos`, `in_scopus`, `databases`, `title`, `first_author`, `year`, `journal`, `document_type`, `has_abstract`, `abstract_source` (empty when the abstract came with the record, `<database> (duplicate record)` when it came from a removed copy, otherwise the source used by `--fill-abstracts`), `times_cited_wos`, `times_cited_scopus`, and the columns you fill in: `screening_decision` (list: include / exclude / maybe), `exclusion_reason`, `notes`. Records without abstract already have `exclude` / `No abstract available`; the others are empty |
| `duplicates_removed` | Every record removed as a duplicate: its source and ID, the record kept, the key that matched, the title and both DOIs |

### Screening (`--screen`)

Filling in `screening_decision` does not change the analysis by itself. After screening, `--screen` writes a new file with only the records you kept, and the analysis runs on that file:

```bash
# 1. merge, 2. fill in screening_decision in Nyssomyia_all_prisma.xlsx, then:
python3 Jurumim_Revisor.py --screen Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx
# -> Nyssomyia_all_screened.txt (records marked include)

python3 Jurumim_Revisor.py --screen Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx --keep include maybe --screen-out Nyssomyia_final.txt

python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt general.xlsx --viewer
```

| Option | Meaning |
|---|---|
| `--screen MERGED.txt PRISMA.xlsx` | Merged file and its PRISMA table |
| `--keep include [maybe] [exclude]` | Decisions kept (default `include`) |
| `--screen-out OUT.txt` | Output (default `<MERGED>_screened.txt`) |

- Records are matched by `record_id`, the `PMID-` line of the merged file, whatever their database. Kept records are copied unchanged. The merged file is never modified, so the counts before screening remain available.
- Records without a decision are left out and counted in a warning. Decisions are read without regard to case or surrounding spaces (` Include ` is `include`); any other value (`excl`) is reported and treated as not screened.
- A warning is also printed when the table has `record_id`s that are not in the merged file, which happens with the table of another merge.
- Records without abstract are read from `<MERGED>_no_abstract.txt`. They come marked `exclude`; a record you change to `include` is copied to the screened file too, counted by its title, and a note says so.

### WoS fields in MEDLINE

A WoS-only record gets its PMID when WoS has one, otherwise the UT without `WOS:` (`PMID- WOS000123456700001`), which is also its folder name in `PMID/`. A record with neither gets `WOSNOID` followed by a hash of its title, year, first author and journal, so its ID is the same on every run; two identical records without any ID get `_2`, `_3`. `AF` → `FAU`, `AU` → `AU`, and `C1` → `AD`, written after its own author, so the viewer still takes each author's country from that author's address only. Old WoS records whose `C1` names no authors keep their addresses, but without an owner. `SO` → `JT`, `J9` → `TA`, `DE` → `OT`, `DI` → `LID`/`AID`, `DT` → `PT`, `TC` → `TC`.

### Scopus fields in MEDLINE

A Scopus-only record gets its PMID when Scopus has one, otherwise `SCOPUS` followed by the EID without punctuation (`PMID- SCOPUS2s2085000000004`), or `SCOPUSNOID` and a hash when there is no EID either. `Author full names` → `FAU` (without the Scopus author ID in brackets), `Authors` → `AU`, and `Authors with affiliations` → `AD`, written after its own author. Each entry goes to the author whose name opens it, an entry without a name is another affiliation of the previous author, and when no entry opens with a name the affiliations stay without an owner. Two co-authors with the same short name (`Silva M.`) each get their own entries, in author order. `Source title` → `JT`, `Abbreviated Source Title` → `TA`, `Author Keywords` → `OT`, `DOI` → `LID`/`AID`, `Document Type` → `PT`, `Cited by` → `TCSC`, `ISSN` → `IS` (written `1756-3305`).

Scopus appends the publisher's copyright notice to the abstract (`© 2024 Elsevier B.V. All rights reserved.`). PubMed keeps it out of `AB`, so it is removed here; otherwise *elsevier*, *rights* and *reserved* would be counted as words of the Scopus-only abstracts. `[No abstract available]` is treated as no abstract.

---

## Desktop app

```bash
python3 initialize.py              # open the window
python3 initialize.py --check      # only check what is installed
python3 initialize.py --shortcut   # add it to the applications menu (Linux; on WSL also the Windows Start menu)
```

The window builds and runs `Jurumim_Revisor.py` commands. Each page is a form; below it is the terminal command it will run, with a Copy button, and Run executes that command and shows its output in the log. Anything done in the window can be repeated in a terminal, and `Jurumim_Revisor.py` does not need the window.

| Page | Runs | Controls |
|---|---|---|
| 1 Search databases | `-p -q … --db …` | query; PubMed (e-mail, NCBI key), Web of Science (key, Expanded/Starter, own query), Scopus (key, institutional/personal, view, token, own query); fill abstracts; keep records without abstract; save keys |
| 2 Merge files | `--merge … --merge-out …` | exported files and their detected format (PubMed, WoS plain text / tab-delimited, Scopus CSV / RIS, merged); "Add this topic's downloads"; output name; abstract options |
| 3 Screen | `--screen MERGED PRISMA --keep …` | the topic's PRISMA flow read from its `_prisma.xlsx` (identified per database, duplicates, screened, excluded without abstract or by you, included, not yet screened); Open PRISMA table; decisions to keep |
| 4 Analyse | `input.txt output.xlsx …` | every word, synonym groups (`term: synonym, synonym`, one per line) or search terms (one per line); stopwords and stopword file; `--lemma`, `--articles`, `--viewer` |
| Fill abstracts of a file | `--fill-abstracts FILE` | file, output name, e-mail |
| API keys | saves `~/.jurumim_keys.json` | saved keys (masked), Semantic Scholar and OpenAlex keys, Forget all saved keys |

- The TOPIC box at the top names the review. Every run writes into `results/<topic>/`, or into the folder picked with *Choose folder…*. After a run, steps 3 and 4 point at the newest merged, PRISMA and screened files of that folder, and a *Next* button goes to the following step.
- Keys typed in the window are passed to the tool as environment variables (`WOS_API_KEY`, `SCOPUS_API_KEY`, ...), so they never appear in the command box or in the process list. Keys saved by the terminal tool are used as well. The window keeps its own settings (topic, query, options, but no keys) in `~/.jurumim_gui.json`.
- Stop ends the running command and anything it started, such as the viewer.
- The viewer opens in the browser by itself. Streamlit asks for an e-mail the first time it runs; the window has no terminal to answer, so it starts Streamlit in headless mode, which skips the question.
- Tkinter comes with Python on Windows and macOS; on Ubuntu, `sudo apt install python3-tk`. Pillow (in `requirements.txt`) draws the logo; without it the window opens without the logo.
- On Linux, the `tk` package installed by default with conda has no font support, and the window opens in a single bitmap font. `python3 initialize.py --check` reports it, and `conda install -c conda-forge "tk=*=xft_*"` fixes it.

## How the database modules work

Every source goes through the same path: its own format, then a dict of fields, then one MEDLINE record (`Registro`). Duplicate removal, the PRISMA table, `--screen` and the analysis only handle MEDLINE records, whatever database they came from.

`databases/medline.py` holds `Registro`, one article with its comparison keys (`pmid`, `doi`, `titulo`, `ano`, the WoS `ut`/`tc`, the Scopus `eid`/`tc_scopus`) and the databases where it was found (`fontes`). A PubMed record keeps its original text (`bloco`); the others are `(tag, value)` pairs. `to_medline()` writes the record with `DB` and the IDs taken from its duplicates. `normalizar_doi` and `chave_titulo` (letters and digits only, no accents) build the keys. `ler_medline` splits a file on its `PMID-` lines, as the original reader does, and reads back the `DB`/`UT`/`TC`/`EID`/`TCSC` lines of a merged file, so a second merge adds nothing twice.

`databases/wos.py` converts Web of Science records. WoS tags differ from MEDLINE, and some have a PubMed name with another meaning (`IS` is the issue, not the ISSN; `SO` the journal, not the citation; `PT` the letter "J"). `detectar_formato` tells plain text (`FN `) from tab-delimited (`PT\tAU`) and the encoding; `ler_wos_txt` reads two-letter tags, 3-space continuation lines and `ER`; `ler_wos_tab` reads one record per row. `_autores_e_enderecos` gives each `C1` address to the authors named in its brackets, and `wos_para_registro` translates tag by tag, writing each `AD` after its author. The Expanded and Starter API responses are turned into the same tags, so they go through the same translation.

`databases/scopus.py` reads the CSV and RIS exports and the Search API into one intermediate dict (`_vazio`), which `scopus_para_registro` writes as MEDLINE. `limpar_resumo` removes the copyright notice and the `[No abstract available]` placeholder. `ler_scopus_csv` finds the columns whatever the case of their header and accepts the `;` and the older `,` separators. `_enderecos_csv` splits `Authors with affiliations` as described above, trying every form of each name and starting from the author after the current one, which keeps two `Silva M.` apart. `ler_scopus_ris` takes the EID from the link and the citations and PMID from the notes. `baixar_scopus` pages the Search API with a cursor. A personal key cannot use the cursor and cannot go past the 5,000th record of a search, so `baixar_scopus_pessoal` pages by position (`start`) and, above 5,000, `_por_ano` halves the year range (`PUBYEAR > a AND PUBYEAR < b`) until each part fits.

`databases/dedup.py` reads the records in priority order and keeps an index of the keys already seen (PMID, UT, EID, DOI, title + year), so duplicates are found in one pass. Each duplicate is reported with the key that matched; the kept record gains the databases, IDs and citation counts of its copies, and the abstract of a copy when it has none.

`databases/prisma.py` writes one row per article (`linha_registro`) with each database's ID in its own column. The screening counts are `COUNTIF` formulas over `screening_decision`, which has a drop-down list; records without abstract get `exclude` / `No abstract available`, and a `COUNTIFS` row counts them within *Records excluded*.

`databases/resumos.py` fills in missing abstracts. `preencher` takes the records without `AB` and asks each source only for those still missing: `_pubmed` by PMID in batches of 200, `_crossref` by DOI in batches of 50, `_semantic_scholar` in batches of 500 and `_openalex` in batches of 50, rebuilding OpenAlex's word-position index into text. A batch refused because of one malformed DOI is split until that DOI is isolated. Every text goes through `limpar` (JATS, headings, HTML entities, copyright) and `so_ingles` (the language check described above). A source that fails, from the network or a quota, is reported and the next one runs with what was found so far.

`databases/credenciais.py` fills each missing e-mail or key from the flag, the environment, the saved file or a hidden question (`completar`), writes `~/.jurumim_keys.json` readable by its owner only (`salvar`) and shows keys as `abcd…wxyz` (`mascarar`).

`gui/comandos.py` has one function per page of the desktop app (`comando_busca`, `comando_merge`, `comando_triagem`, `comando_analise`, `comando_preencher`). Each turns the form into the command line, the API keys as environment variables, and the problems that block the run; `texto_comando` writes the command as it would be typed. `arquivos_do_topico` finds the newest files of a topic folder and `resumo_prisma` reads the PRISMA counts. `gui/app.py` is the Tkinter window: it rebuilds the command on every change, runs `Jurumim_Revisor.py` with the same Python in its own process group, shows its output through a thread and a queue, and ends the whole group on Stop. `initialize.py` checks Python, Tkinter, the display and the fonts before opening the window.

In `Jurumim_Revisor.py`, these features are in `carregar_arquivo` (recognises PubMed, WoS and Scopus files), `combinar` (duplicates, abstracts taken from duplicates, `--fill-abstracts`, the `_no_abstract.txt` file, MEDLINE and PRISMA outputs), `baixar_varias` (`-p --db`), `preencher_resumos` and `modo_preencher` (`--fill-abstracts`), `modo_merge` (fixed priority, then file name), `modo_screen` (`--screen`), `preparar_outdir` (`--outdir`), and `colunas_por_base` / `rodar_modo`, which run the same counting mode on each database's records to add the `articles_<database>` columns.

---

## Limitations

- Records from before ~2014 usually list an affiliation only for the first author, so the last author's country is often *Unknown*.
- Affiliations without any country name ("Calcutta", "Basel") give *Unknown*. The country is never guessed from city names.
- The same person can appear under two spellings in PubMed ("Galati, Eunice A Bianchi" and "Galati, Eunice Aparecida Bianchi"). They are counted as different authors.
- Without `--lemma`, singular and plural are separate words.
- Counts can change slightly between NLTK versions for unusual punctuation. For a review, write down the versions you used (`pip freeze`).

---

## Files in this repo

| Path | Purpose |
|---|---|
| `Jurumim_Revisor.py` | Everything you run: parsing, counting, PubMed download, `--viewer`, `--db`, `--merge`, `--screen` |
| `databases/medline.py` | Record shared by all databases, MEDLINE reader and writer |
| `databases/wos.py` | Web of Science files and APIs → MEDLINE |
| `databases/scopus.py` | Scopus files and API → MEDLINE |
| `databases/dedup.py` | Duplicate removal across databases |
| `databases/prisma.py` | PRISMA table (`_prisma.xlsx`) |
| `databases/resumos.py` | `--fill-abstracts`: missing abstracts from PubMed, Crossref, Semantic Scholar, OpenAlex |
| `databases/credenciais.py` | E-mail and API keys: flags, environment, saved file, terminal questions |
| `initialize.py` | Opens the desktop app (`--check`, `--shortcut`) |
| `gui/comandos.py` | Desktop app: form state → `Jurumim_Revisor.py` command line |
| `gui/app.py` | Desktop app window (Tkinter) |
| `viewer/JR_Phleb.view.py` | Streamlit app (started by `--viewer`) |
| `viewer/analysis/` | MEDLINE parser, author index, country inference, table loading |
| `viewer/assets/` | Logos |
| `requirements.txt` | Python dependencies |

---

## Author

ANDRADE, M. C. — Laboratory of Bioinformatics and Evolutionary Biology (LABBE), Brazil.

## License

[MIT](LICENSE)
