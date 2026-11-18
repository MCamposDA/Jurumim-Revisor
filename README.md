# Jurumim Revisor

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)
![PubMed](https://img.shields.io/badge/input-PubMed%20MEDLINE-326599.svg)
![Streamlit](https://img.shields.io/badge/viewer-Streamlit-FF4B4B.svg)

<p align="center"><img src="viewer/assets/jurumim_logo.jpg" width="160" alt="Jurumim Revisor logo"></p>

Auxiliary software for systematic reviews and literature analysis. It reads PubMed exports (MEDLINE format), as well as Web of Science and Scopus records converted to the same format, counts terms in titles and abstracts, and writes Excel tables. A Streamlit viewer shows the results by word, author and article.

With `--report` it also writes an interactive word co-occurrence network, trends per year, the PRISMA 2020 flow diagram and a methods text. Screening can be pre-sorted by default and custom criteria (`--suggest`) or by an AI assistant (Claude or Gemini, through the `jurumim-review` skill), whose suggestions go to their own columns; the decisions stay with the reviewers.

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
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt general.xlsx --report   # network, trends, PRISMA diagram, methods
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

1. Optionally, pre-sort the records with [screening suggestions](#screening-suggestions---suggest---import-suggestions): default criteria plus your own, or the CSV of an AI assistant. They fill their own columns.
2. Open `Nyssomyia_all_prisma.xlsx`, sheet `records`, and fill in `screening_decision` (include / exclude / maybe) and, if you want, `exclusion_reason`. The `summary` sheet follows your changes.
3. Keep only the records you chose:

```bash
python3 Jurumim_Revisor.py --suggest Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx --include-terms Nyssomyia Lutzomyia --years 2000-
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
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt general.xlsx --report --report-pt
python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt general.xlsx --context --net-min 5
```

`--report` and `--context` are described in [Report](#report---report) and [AI assistant](#ai-assistant---context-and-the-jurumim-review-skill).

#### Files written at each step

| Step | File | Content |
|---|---|---|
| `-p` (PubMed) | `Pubmed_<query>.txt` | PubMed records as downloaded |
| `-p --db wos` / `scopus` | `WOS_<query>.txt`, `Scopus_<query>.txt` | That database's records, in MEDLINE |
| `--merge`, or `-p --db` with anything other than PubMed alone | `<out>.txt` / `Merged_<query>.txt` | One MEDLINE file without duplicates, with `DB`, `UT`, `TC`, `EID`, `TCSC` lines |
| | `<out>_no_abstract.txt` | Records still without abstract: not analysed, marked excluded in the PRISMA table (not written with `--keep-no-abstract`) |
| | `<out>_prisma.xlsx` | Sheets `summary`, `records`, `duplicates_removed` |
| | `<out>_search_log.json` | Databases, queries, dates, kind of key and counts of the merge, read by the methods text of `--report` |
| `--suggest` / `--import-suggestions` | `<out>_prisma.xlsx` | Adds the `rules_*` / `ai_*` columns to the `records` sheet |
| `--fill-abstracts FILE` | `<FILE>_filled.txt` (+ `<FILE>_filled_no_abstract.txt`) | The same records with the missing abstracts filled in (`AB`, and `ABS` for the source); the input file is not changed |
| `--screen` | `<out>_screened.txt` | Only the records kept, unchanged |
| analysis | `general.xlsx`... | The usual tables, plus one `articles_<database>` column per database for a merged input |
| `--report` | `<input>_report/` | Network, trends, PRISMA 2020 diagram, methods text (see [Report](#report---report)) |
| `--context` | `<input>_report/context/` | Files for an AI assistant (see [AI assistant](#ai-assistant---context-and-the-jurumim-review-skill)) |

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
- `--set-keys` asks for the e-mail and keys and saves them, without running a search: `--set-keys` alone asks for all three databases, `--set-keys wos scopus` only for those. Enter keeps the value already saved. It is the way to give keys to the tool before an AI assistant runs the commands, so the keys never go through the chat:

```bash
python3 Jurumim_Revisor.py --set-keys wos scopus
```
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
| `--set-keys [DB...]` | Type and save the e-mail and keys of these databases (`pubmed`, `wos`, `scopus`, `all`; default all) without a search |
| `--suggest MERGED.txt PRISMA.xlsx` | Screening suggestions from criteria (see [Screening suggestions](#screening-suggestions---suggest---import-suggestions)) |
| `--criteria FILE` / `--criteria-template [FILE]` | Criteria file for `--suggest` / write an empty one (default `screening_criteria.txt`) |
| `--include-terms T...` / `--exclude-terms T...` / `--years FROM-TO` | Criteria for `--suggest` given as flags |
| `--import-suggestions CSV PRISMA.xlsx` / `--ai-model NAME` | Copy an AI assistant's suggestions to the `ai_*` columns |
| `--report` / `--report-pt` | Network, trends, PRISMA diagram and methods text in `<input>_report/` / also the methods text in Portuguese (see [Report](#report---report)) |
| `--context` | `--report` plus `<input>_report/context/` for an AI assistant |
| `--net-min N` / `--net-max-nodes N` / `--net-keep-generic` | Network: minimum times two words appear side by side (default 3), most frequent linked words kept (default 300), keep generic words |

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

`--suggest` and `--import-suggestions` add their columns after `notes`, so the formulas of `summary` keep pointing at the same cells.

The merge also writes `<output>_search_log.json`: for each source, the database, whether it came from an API (with the query, the date and the kind of key, never the key) or from a file, and its number of records; then the records identified, the duplicates removed by key, the unique records, and what happened to the abstracts (taken from duplicates, filled per source, not found). The methods text of `--report` is written from it.

### Screening (`--screen`)

Filling in `screening_decision` does not change the analysis by itself. After screening, `--screen` writes a new file with only the records you kept, and the analysis runs on that file:

```bash
# 1. merge, 2. fill in screening_decision in Nyssomyia_all_prisma.xlsx, then:
python3 Jurumim_Revisor.py --screen Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx
# -> Nyssomyia_all_screened.txt (records marked include)

python3 Jurumim_Revisor.py --screen Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx --keep include maybe --screen-out Nyssomyia_final.txt

# mark only what goes out; keep the included and the records left unmarked
python3 Jurumim_Revisor.py --screen Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx --keep include unmarked

python3 Jurumim_Revisor.py Nyssomyia_all_screened.txt general.xlsx --viewer
```

| Option | Meaning |
|---|---|
| `--screen MERGED.txt PRISMA.xlsx` | Merged file and its PRISMA table |
| `--keep include [maybe] [unmarked] [exclude]` | Decisions kept (default `include`); `unmarked` keeps the records with no decision |
| `--screen-out OUT.txt` | Output (default `<MERGED>_screened.txt`) |

- Records are matched by `record_id`, the `PMID-` line of the merged file, whatever their database. Kept records are copied unchanged. The merged file is never modified, so the counts before screening remain available.
- Records without a decision are left out and counted in a warning, unless `--keep` includes `unmarked`. With thousands of records it is often quicker to mark only the ones to exclude and keep the rest: `--keep include unmarked`. The PRISMA table still counts those records as not yet screened; to report them as included, fill `include` in the empty cells (in Excel: filter `screening_decision` on blanks, type `include` in the first cell and copy it down). Decisions are read without regard to case or surrounding spaces (` Include ` is `include`); any other value (`excl`) is reported and treated as not screened.
- A warning is also printed when the table has `record_id`s that are not in the merged file, which happens with the table of another merge.
- Records without abstract are read from `<MERGED>_no_abstract.txt`. They come marked `exclude`; a record you change to `include` is copied to the screened file too, counted by its title, and a note says so.

### Screening suggestions (`--suggest`, `--import-suggestions`)

Two ways to pre-sort the records before screening. Both write to their own columns of the `records` sheet and never to `screening_decision` or `exclusion_reason`. Running either one again replaces its columns. The PRISMA table must be closed in Excel while they run.

#### Criteria (`--suggest`)

Default criteria, valid for any topic:

| Record | Suggestion |
|---|---|
| no abstract | exclude |
| document type erratum, correction, retraction, retracted publication, editorial, comment, letter, news, note, biography, obituary, interview, meeting abstract, book review, conference review | exclude |
| document type review or meta-analysis | maybe |
| language other than English | maybe |

Document types are read from `PT` (PubMed), `DT` (Web of Science) and `Document Type` (Scopus). Your own criteria are added with flags or a criteria file:

```bash
python3 Jurumim_Revisor.py --suggest Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx
python3 Jurumim_Revisor.py --suggest Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx --include-terms Nyssomyia Lutzomyia --exclude-terms "in vitro" --years 2000-2026

python3 Jurumim_Revisor.py --criteria-template criteria.txt     # empty criteria file, to fill in
python3 Jurumim_Revisor.py --suggest Nyssomyia_all.txt Nyssomyia_all_prisma.xlsx --criteria criteria.txt
```

| Criteria file line | Meaning |
|---|---|
| `include: term, term` | At least one term must be in the title or abstract, otherwise exclude |
| `exclude: term, term` | Any of these terms gives exclude |
| `years: 2000-2026` | Publication years kept (`2000-` or `-2026` for one bound) |
| `exclude types: type, type` | Document types excluded besides the default ones |
| `keep types: letter, note` | Default excluded types that should not be excluded |
| `languages: English, Portuguese` | Languages kept without "maybe" |

Terms are matched as in `--ws`: whole words, case and hyphen variants ignored. Flags are added to the file's values. A record with an exclusion reason gets `exclude`; otherwise one with a "maybe" reason gets `maybe`; otherwise one with an inclusion term gets `include`; the rest get no suggestion. Columns: `rules_suggestion`, `rules_reason` (every reason found) and `rules_score` (inclusion terms found, or minus the number of exclusion reasons).

#### AI assistant (`--import-suggestions`)

A CSV written by Claude or Gemini with the [jurumim-review skill](#ai-assistant---context-and-the-jurumim-review-skill), with the columns `record_id`, `suggestion` (include / exclude / maybe), `reason`, `evidence` (a quote of the title or abstract) and `model`:

```bash
python3 Jurumim_Revisor.py --import-suggestions ai_suggestions.csv Nyssomyia_all_prisma.xlsx
python3 Jurumim_Revisor.py --import-suggestions ai_suggestions.csv Nyssomyia_all_prisma.xlsx --ai-model "model name"
```

They go to `ai_suggestion`, `ai_reason`, `ai_evidence` and `ai_model` (`--ai-model` when the CSV has no `model` column). The CSV may use `,` or `;` (as Excel saves it in Portuguese). Rows with another suggestion, without `record_id`, or with a `record_id` that is not in the table are reported and skipped.

The methods text of `--report` says how many records had suggestions from criteria and from a language model, and that every decision was made by the reviewers.

### WoS fields in MEDLINE

A WoS-only record gets its PMID when WoS has one, otherwise the UT without `WOS:` (`PMID- WOS000123456700001`), which is also its folder name in `PMID/`. A record with neither gets `WOSNOID` followed by a hash of its title, year, first author and journal, so its ID is the same on every run; two identical records without any ID get `_2`, `_3`. `AF` → `FAU`, `AU` → `AU`, and `C1` → `AD`, written after its own author, so the viewer still takes each author's country from that author's address only. Old WoS records whose `C1` names no authors keep their addresses, but without an owner. `SO` → `JT`, `J9` → `TA`, `DE` → `OT`, `DI` → `LID`/`AID`, `DT` → `PT`, `TC` → `TC`.

### Scopus fields in MEDLINE

A Scopus-only record gets its PMID when Scopus has one, otherwise `SCOPUS` followed by the EID without punctuation (`PMID- SCOPUS2s2085000000004`), or `SCOPUSNOID` and a hash when there is no EID either. `Author full names` → `FAU` (without the Scopus author ID in brackets), `Authors` → `AU`, and `Authors with affiliations` → `AD`, written after its own author. Each entry goes to the author whose name opens it, an entry without a name is another affiliation of the previous author, and when no entry opens with a name the affiliations stay without an owner. Two co-authors with the same short name (`Silva M.`) each get their own entries, in author order. `Source title` → `JT`, `Abbreviated Source Title` → `TA`, `Author Keywords` → `OT`, `DOI` → `LID`/`AID`, `Document Type` → `PT`, `Cited by` → `TCSC`, `ISSN` → `IS` (written `1756-3305`).

Scopus appends the publisher's copyright notice to the abstract (`© 2024 Elsevier B.V. All rights reserved.`). PubMed keeps it out of `AB`, so it is removed here; otherwise *elsevier*, *rights* and *reserved* would be counted as words of the Scopus-only abstracts. `[No abstract available]` is treated as no abstract.

---

## Report (`--report`)

Added to any analysis run, after the tables:

```bash
python3 Jurumim_Revisor.py Nyssomyia_all.txt general.xlsx --report
python3 Jurumim_Revisor.py Nyssomyia_all.txt general.xlsx --lemma --report --report-pt --net-min 5
```

It writes `<input>_report/` next to the output table:

| File | Content |
|---|---|
| `network.html` | Interactive word co-occurrence network, a single file that opens in any browser |
| `network.xlsx` | Its words (`nodes`: frequency, articles, degree, strength, community) and links (`links`: co-occurrences, times in each order, articles) |
| `network.graphml` | The same network for Cytoscape or Gephi |
| `trends.xlsx`, `trends.png` | Articles per year, and articles with each term per year: count, share of the year's articles, share over 3-year windows |
| `prisma_flow.png`, `prisma_flow.svg` | PRISMA 2020 flow diagram (when the input comes from a merge) |
| `methods_en.txt` (`methods_pt.txt` with `--report-pt`) | Methods text |

### Network

Titles and abstracts are split into words as in the frequency table (same stopwords, `-sw` and `--lemma`). For every word, the word right before it and the word right after it are counted. Stopwords, generic words of scientific writing (*study*, *results*, *using*, *however*, reporting verbs such as *suggest*, *performed*, *obtained*...), headings of structured abstracts and tokens that are not words leave a gap, so two words count as a pair only when they are written side by side. Pairs seen at least `--net-min` times (default 3) are kept, then the `--net-max-nodes` most frequent words (default 300). Communities are found with the Louvain method (fixed seed, so the same input gives the same groups).

The layout places each community on its own island; islands with more links between them are closer, and none overlaps. In the page, the size of a word is its frequency and the width of a link its number of co-occurrences; colours are communities (eight colours, the rest grey), and links inside a community take its colour. From afar, each island shows its two most frequent words; zooming in shows the words themselves, as many as fit without overlapping. Pointing at a word shows its name and its links; clicking it moves the view to it, shows only its name with its neighbours highlighted, and lists beside the drawing the words next to it (in the order they are usually written, with the count) and its most recent articles (record ID, year, title). Clicking a group in the legend zooms into it. The page opens with a minimum number of co-occurrences that keeps about 600 links at most; the slider goes down to the value of the run (`--net-min`). The mouse wheel zooms, dragging moves the view, and Esc goes back to the whole network. `--net-keep-generic` keeps the generic words.

### Trends

The terms followed are the `--ws` terms or the `-st` groups when the analysis uses them; otherwise the eight words found in most articles among those present in at most half of them (the words of the search itself are in nearly every article); without `--lemma`, a singular and its plural count as one choice. The chart shows articles per year, then one panel per term with its share of the articles of a 3-year window (the year, the one before and the one after), left out when the window has fewer than 5 articles. The panels start in the first year from which every window has at least 15 articles (fewer for small searches), so the sparse early years do not draw loose fragments; the footnote gives that year. The tables have the values per year.

### PRISMA 2020 flow diagram

Identification (records per database, duplicates removed) and title/abstract screening (screened, excluded without abstract and by the reviewers, included, maybe, not yet screened) come from `<merged>_prisma.xlsx` and `<merged>_search_log.json`, found next to the input (`<merged>.txt`, `<merged>_screened.txt` and `<merged>_filled.txt` all lead to them). Retrieval, full-text assessment and inclusion happen outside the tool: those boxes show `n = …`, to be completed in the SVG, whose text stays editable.

### Methods text

Paragraphs on the search (databases, queries, dates and kind of key for API searches; files for exports), duplicate removal with its counts by key, abstracts taken from duplicates and filled per source, records excluded without abstract, screening counts and suggestions, and the text analysis and network. What the tool cannot know, such as the query and date of an exported file, is left in `[brackets]`.

## AI assistant (`--context` and the jurumim-review skill)

`--context` writes the report plus `<input>_report/context/`, plain-text files for an AI assistant to read:

```bash
python3 Jurumim_Revisor.py Nyssomyia_all.txt general.xlsx --lemma --context
```

| File | Content |
|---|---|
| `README.md` | What the folder holds and the rules for the assistant |
| `overview.md` | Search, PRISMA counts, analysis options, most frequent words, network communities, strongest links, trends |
| `records.csv` | One row per record: IDs, year, first author, title, journal, document type, language, databases, screening and suggestion columns of the PRISMA table |
| `abstracts.md` | Title and abstract of every record, under `## [record_id]` |
| `network_terms.csv`, `network_links.csv` | Words and links of the network, with up to 25 record IDs each |
| `trends.csv` | Articles with each followed term per year |
| `methods_en.txt` | Methods text |
| `suggestions_template.csv` | Records without a screening decision, with the columns of `--import-suggestions` |

The folder has at most nine files, all plain text, so they can also be uploaded to a chat.

The `skills/jurumim-review/` folder is a skill, a set of instructions in the `SKILL.md` format read by Claude and Gemini. It works at two moments:

- Before a run, it asks for the topic, the databases, the queries (and can draft them for each database), the screening criteria and the report options, checks the Python packages and which keys are saved (`--show-keys`), and builds the commands. Where the assistant can run commands (Claude Code, Gemini CLI, Antigravity CLI), it runs them with `--no-prompt` and `--outdir results/<topic>`. Keys are never asked for in the chat: the researcher saves them with `--set-keys` in a terminal.
- After a run, it reads the context folder, answers questions citing record IDs as `[record_id]`, describes communities, frequent expressions and trends as patterns of words, and suggests screening decisions as a CSV for `--import-suggestions`, after confirming the criteria with the researcher.

The assistant suggests and the researcher decides: the skill never writes `screening_decision`.

The repository is also a Claude Code plugin, a Gemini CLI extension and an Antigravity plugin, which install the tool and the skill together:

| Assistant | Install |
|---|---|
| Claude Code | `claude plugin marketplace add MCamposDA/Jurumim-Revisor`, then `claude plugin install jurumim-revisor@jurumim` |
| Gemini CLI | `gemini extensions install https://github.com/MCamposDA/Jurumim-Revisor` |
| Antigravity CLI | `agy plugin install https://github.com/MCamposDA/Jurumim-Revisor` |
| claude.ai | Zip the `skills/jurumim-review` folder and upload it in the Skills settings; add the files of `context/` to a project |
| Gemini app (Gem) | Paste the Gem instructions of `skills/jurumim-review/references/web.md` in a new Gem and add the files of `context/` as its knowledge |

Each person runs these commands once on their own computer; they install the plugin for that person only. The GitHub repository is the marketplace: anyone can install from it with the same commands, without creating anything.

From a local copy: `claude plugin marketplace add /path/to/Jurumim-Revisor`, `gemini extensions link /path/to/Jurumim-Revisor` or `agy plugin install /path/to/Jurumim-Revisor`, where `/path/to/Jurumim-Revisor` is the folder of that copy (the desktop app shows it filled in). In claude.ai and the Gemini app the assistant cannot run commands: it gives them to be pasted in a terminal and works on the uploaded context files.

---

## Desktop app

```bash
python3 initialize.py              # open the window
python3 initialize.py --check      # only check what is installed
python3 initialize.py --shortcut   # add it to the applications menu (Linux; on WSL also the Windows Start menu)
```

The window runs `Jurumim_Revisor.py` for you. Each page is one step of the review, written in plain language; the button at the bottom says what it will do (Search, Merge, Keep chosen articles, Analyse…) and its progress appears below it. *Show terminal commands* (bottom right) shows the exact command of the page, with a Copy button, and the option name next to each field, so any step can be repeated in a terminal. `Jurumim_Revisor.py` does not need the window.

| Page | Runs | What is on it |
|---|---|---|
| 1 Search databases | `-p -q … --db …` | search words; PubMed (e-mail, NCBI key), Web of Science (key, institutional or free, other words), Scopus (key, institutional or personal, detail, token, other words); look for missing abstracts; keep articles without abstract; remember the keys |
| 2 Merge files | `--merge … --merge-out …` | exported files and the format each one was recognised as; *Add the downloads of step 1*; name of the result; abstract options |
| 3 Screen | `--screen …` or `--suggest …` | the PRISMA flow of the topic (identified per database, duplicates, screened, excluded without abstract or by you, included, not yet screened) and, below it, how many suggestions from rules and from an AI assistant the table holds; *Open the PRISMA table*; keep the articles chosen (include, maybe, not marked, exclude), or get suggestions first (words the article must mention, words that exclude it, years, rules file, *Create a rules file…*) |
| 4 Analyse | `input.txt output.xlsx …` | articles and table name; every word, groups of synonyms or only some terms; words to ignore; singular and plural together, one folder per article, viewer; report (methods also in Portuguese, network settings); *Open the network*, *Open the report folder* |
| AI assistant | `… --context` or `--import-suggestions …` | everything about AI in one place: 1, choose the assistant (Claude Code, Gemini CLI or Antigravity, or claude.ai and the Gemini app) and how to install it, with the commands to copy, *Create the skill file (zip)* and *Copy the Gem instructions*; 2, using the assistant before the search, with an example request; 3, *Prepare the files* for the assistant from the articles of step 4, with an example request; 4, *Load the suggestions* written by the assistant |
| Fill abstracts of a file | `--fill-abstracts FILE` | file, name of the result, e-mail |
| API keys | saves `~/.jurumim_keys.json` | saved keys (masked), Semantic Scholar and OpenAlex keys, Forget all saved keys |
| Help | nothing | how a review works in the window, keys, articles without abstract, suggestions, reading the report, words used, the terminal |

- The TOPIC box at the top names the review. Every run writes into `results/<topic>/`, or into the folder picked with *Choose folder…*. After a run, steps 3 and 4 point at the newest merged, PRISMA and screened files of that folder, and a *Next* button goes to the following step (after a report, *Open the network*). *Create a rules file…* writes `screening_criteria.txt` into the topic folder and opens it; an `ai_suggestions.csv` in the topic folder is picked up by the AI assistant page, and *Create the skill file (zip)* saves `jurumim-review.zip` there.
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

`databases/credenciais.py` fills each missing e-mail or key from the flag, the environment, the saved file or a hidden question (`completar`), writes `~/.jurumim_keys.json` readable by its owner only (`salvar`), shows keys as `abcd…wxyz` (`mascarar`), and asks for and saves keys without a search (`definir`, `--set-keys`).

`databases/registro.py` writes `<merged>_search_log.json`. `origem_api` and `origem_arquivo` describe each source (database, query, date and kind of key, or file name) before duplicates are removed; `escrever_log` adds the counts of the merge.

`databases/sugestoes.py` holds the screening suggestions. `ler_criterios` reads the criteria file and flags; `avaliar` gives one record its suggestion, reasons and score from its `TI`, `AB`, `PT`, `LA` and `DP` lines; `sugerir` runs it on the merged file and its `_no_abstract.txt`; `importar_ia` reads the AI CSV (`,` or `;`, detected) and checks each row; `gravar_colunas` writes either set of columns into the `records` sheet with openpyxl, adding them after the last column and keeping formulas, drop-down list and frozen header.

`reporting/` holds `--report` and `--context`. `artigos.py` reads the analysed file once (ID, year, title, abstract, journal, databases, DOI, type, language). `rede.py` turns each title and abstract into a sequence of words with gaps (`sequencia`), counts words and adjacent pairs with the records that contain them (`contar`), keeps the pairs above the minimum and finds the communities (`montar`), lays out each connected group with a force-directed layout and places the small groups beside the main one (`posicoes`), and writes the tables and GraphML (`tabelas`). `rede_html.py` writes the network page: the data as JSON inside one HTML file with its own drawing code (SVG), with no external library. `tendencias.py` chooses the terms and builds the tables and small-multiple chart. `prisma_figura.py` draws the diagram with matplotlib. `metodos.py` writes the methods text in English or Portuguese from the search log, the PRISMA counts and the analysis options. `contexto.py` writes the context folder. `relatorio.py` runs them in order and finds the PRISMA table and search log of the input.

`skills/jurumim-review/` is the skill (`SKILL.md`, with `references/running.md` for planning and running, `references/context.md` for reading a context folder and writing suggestions, and `references/web.md` for claude.ai and Gems). `.claude-plugin/` (plugin and marketplace), `gemini-extension.json` with `GEMINI.md`, and `.antigravity-plugin/` describe the repository to each assistant; all three point at the same `skills/` folder.

`gui/comandos.py` has one function per page of the desktop app (`comando_busca`, `comando_merge`, `comando_triagem`, `comando_sugerir`, `comando_importar_ia`, `comando_analise`, `comando_preencher`; `comando_tela_triagem` picks the screening action). Each turns the form into the command line, the API keys as environment variables, and the problems that block the run; `texto_comando` writes the command as it would be typed. `arquivos_do_topico` finds the newest files of a topic folder and `resumo_prisma` reads the PRISMA counts. `gui/app.py` is the Tkinter window: it rebuilds the command on every change, runs `Jurumim_Revisor.py` with the same Python in its own process group, shows its output through a thread and a queue, and ends the whole group on Stop. `initialize.py` checks Python, Tkinter, the display and the fonts before opening the window.

In `Jurumim_Revisor.py`, these features are in `carregar_arquivo` (recognises PubMed, WoS and Scopus files), `combinar` (duplicates, abstracts taken from duplicates, `--fill-abstracts`, the `_no_abstract.txt` file, MEDLINE and PRISMA outputs), `baixar_varias` (`-p --db`), `preencher_resumos` and `modo_preencher` (`--fill-abstracts`), `modo_merge` (fixed priority, then file name), `modo_screen` (`--screen`), `modo_sugerir` and `modo_importar_ia` (`--suggest`, `--import-suggestions`), `gerar_relatorio` (`--report`, `--context`), `preparar_outdir` (`--outdir`), and `colunas_por_base` / `rodar_modo`, which run the same counting mode on each database's records to add the `articles_<database>` columns.

---

## Limitations

- Records from before ~2014 usually list an affiliation only for the first author, so the last author's country is often *Unknown*.
- Affiliations without any country name ("Calcutta", "Basel") give *Unknown*. The country is never guessed from city names.
- The same person can appear under two spellings in PubMed ("Galati, Eunice A Bianchi" and "Galati, Eunice Aparecida Bianchi"). They are counted as different authors.
- Without `--lemma`, singular and plural are separate words.
- Counts can change slightly between NLTK versions for unusual punctuation. For a review, write down the versions you used (`pip freeze`).
- The network and the trends count words in titles and abstracts. A link between two words says they are written side by side, not what the studies found.
- Suggestions from criteria only see words, document types, languages and years; suggestions of an AI assistant can be wrong. Both are there to be checked.

---

## Files in this repo

| Path | Purpose |
|---|---|
| `Jurumim_Revisor.py` | Everything you run: parsing, counting, PubMed download, `--viewer`, `--db`, `--merge`, `--screen`, `--suggest`, `--report` |
| `databases/medline.py` | Record shared by all databases, MEDLINE reader and writer |
| `databases/wos.py` | Web of Science files and APIs → MEDLINE |
| `databases/scopus.py` | Scopus files and API → MEDLINE |
| `databases/dedup.py` | Duplicate removal across databases |
| `databases/prisma.py` | PRISMA table (`_prisma.xlsx`) |
| `databases/resumos.py` | `--fill-abstracts`: missing abstracts from PubMed, Crossref, Semantic Scholar, OpenAlex |
| `databases/credenciais.py` | E-mail and API keys: flags, environment, saved file, terminal questions, `--set-keys` |
| `databases/registro.py` | Search log of a merge (`_search_log.json`) |
| `databases/sugestoes.py` | `--suggest` and `--import-suggestions` |
| `reporting/` | `--report` and `--context`: network, network page, trends, PRISMA diagram, methods text, context folder |
| `skills/jurumim-review/` | Skill for Claude and Gemini |
| `.claude-plugin/`, `gemini-extension.json`, `GEMINI.md`, `.antigravity-plugin/` | Plugin and extension manifests for Claude Code, Gemini CLI and Antigravity CLI |
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
