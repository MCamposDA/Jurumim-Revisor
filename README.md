# Jurumim Revisor

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.9%2B-3776AB.svg)
![PubMed](https://img.shields.io/badge/input-PubMed%20MEDLINE-326599.svg)
![Streamlit](https://img.shields.io/badge/viewer-Streamlit-FF4B4B.svg)

<p align="center"><img src="viewer/assets/jurumim_logo.jpg" width="160" alt="Jurumim Revisor logo"></p>

Auxiliary software for systematic reviews and literature analysis. It reads a PubMed export (MEDLINE format), counts terms in titles and abstracts, and writes Excel tables. A Streamlit viewer shows the results by word, author and article.

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

# 3. One table per article (used by the viewer)
python3 Jurumim_Revisor.py Pubmed_Nyssomyia.txt --articles

# 4. Open the viewer
python3 viewer/run_JR_Phleb.view.py --pubmed Pubmed_Nyssomyia.txt --general general.xlsx --pmid PMID
```

NLTK data (`punkt`, `punkt_tab`, `stopwords`, and `wordnet` for `--lemma`) is downloaded automatically on first use.

> **Python version:** use 3.9 or newer, except **3.9.7**, which Streamlit does not support. The core script (`Jurumim_Revisor.py`) runs on 3.9.7; only the viewer does not.

---

## Input data

The input is a plain-text file in **PubMed (MEDLINE) format**, where every record starts with a `PMID- ` line. You can get it in two ways:

- **From the website:** search on [PubMed](https://pubmed.ncbi.nlm.nih.gov/), then *Save* → *Selection: All results* → *Format: PubMed* → *Create file*. The website caps this export at 10,000 records.
- **From the script:** `-p` / `--pubmed` (see below), which has no 10,000 limit.

Other formats (CSV, XML, abstracts in plain text) are rejected with an error message.

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
| PubMed download | `-p -q "QUERY" --email you@example.org [--apikey KEY]` | `Pubmed_<query>.txt` |

### Options

| Flag | Meaning |
|---|---|
| `-sw`, `--stopword WORD_OR_FILE ...` | Extra stopwords. Each value is a word or a text file (words separated by spaces, commas or new lines). Works in every mode. |
| `-st TERM` | Starts a group; TERM names the merged row. |
| `-so SYNONYM` | Adds a synonym to the last `-st`. |
| `--ws`, `--wordsearch TERM ...` | Literal search (see *How counting works*). |
| `-art`, `--articles` | Writes one folder per PMID into `./PMID`. |
| `--lemma` | Counts noun lemmas (`viruses` → `virus`, `mice` → `mouse`). Off by default. Does not affect `--ws`. |
| `-p`, `--pubmed` | Downloads a query; requires `-q/--query` and `--email`. |
| `--apikey KEY` | NCBI API key. Optional; raises the request rate from 3 to 10 per second. |

### Output columns

| Column | Meaning |
|---|---|
| `palavra` / `termo` | Word, group name or searched term |
| `frequencia_tiab` | Occurrences in title + abstract |
| `frequencia_ti` | Occurrences in the title |
| `frequencia_ab` | Occurrences in the abstract |
| `art` / `artigos_com_termo` | Number of **distinct** articles containing the word (for a group: at least one of its terms) |

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
python3 viewer/run_JR_Phleb.view.py --pubmed FILE.txt --general TABLE.xlsx --pmid PMID/
```

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
| `Jurumim_Revisor.py` | Core: parsing, counting, PubMed download (CLI) |
| `viewer/run_JR_Phleb.view.py` | Viewer launcher |
| `viewer/JR_Phleb.view.py` | Streamlit app |
| `viewer/analysis/` | MEDLINE parser, author index, country inference, table loading |
| `viewer/assets/` | Logos |
| `requirements.txt` | Python dependencies |

---

## Author

ANDRADE, M. C. — Laboratory of Bioinformatics and Evolutionary Biology (LABBE), Brazil.

## License

[MIT](LICENSE)
