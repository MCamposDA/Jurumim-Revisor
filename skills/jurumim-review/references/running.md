# Before the run: planning and running Jurumim Revisor

`JR` below stands for `python3 <tool folder>/Jurumim_Revisor.py`. Add `--no-prompt` to
every command you run yourself; drop it from commands the researcher runs in a terminal.

## 1. Ask, one topic at a time

Ask only what is missing; propose a default the researcher can accept.

1. **Topic and question.** What is the review about, and what should the included
   studies have (population, exposure/intervention, outcome, study design)? The answer
   feeds the queries and the screening criteria.
2. **Databases.** PubMed (free, needs only an e-mail), Web of Science (API key: Expanded
   gives abstracts and needs an institutional subscription; Starter is free, titles
   only), Scopus (API key: institutional gives abstracts, from the institution's network
   or with an institutional token; personal gives titles only). `--db all` = the three.
3. **Query.** One free-text query works for all three: Jurumim turns it into
   `TS=(...)` for Web of Science and `TITLE-ABS-KEY(...)` for Scopus. A query with PubMed
   field tags (`[tiab]`, `[mh]`) needs its own versions: `--wos-query 'TS=(...)'` and
   `--scopus-query 'TITLE-ABS-KEY(...)'`. Offer to draft the three from the topic; the
   researcher approves them.
4. **Exported files instead of APIs?** Records exported from the websites (PubMed
   "PubMed format" .txt, Web of Science "Plain text" or "Tab-delimited", Scopus CSV or
   RIS) are merged with `--merge`; no key needed.
5. **Missing abstracts.** `--fill-abstracts` looks for them after duplicates are removed
   (PubMed by PMID, then Crossref, Semantic Scholar and OpenAlex by DOI; English only).
   Records still without abstract are set apart and pre-marked as excluded in the
   PRISMA table (`--keep-no-abstract` keeps them in the analysis instead).
6. **Folder.** `--outdir results/<Topic>`: one folder per topic; later steps of the same
   topic use the same `--outdir` and find their inputs there.
7. **Screening criteria** (section 4) and **report options** (section 5).

## 2. Keys and e-mail

Check what is saved (prints masked values; reading this output is fine):

    JR --show-keys

If a key is missing, ask the researcher to run, in their own terminal window (not
through you, since keys are typed hidden and saved in their home folder):

    python3 <tool folder>/Jurumim_Revisor.py --set-keys wos scopus

The e-mail for NCBI is not secret; the researcher may give it to you for `--email`, or
save it the same way (`--set-keys pubmed`). Environment variables also work:
`WOS_API_KEY`, `SCOPUS_API_KEY`, `SCOPUS_INSTTOKEN`, `S2_API_KEY`, `OPENALEX_API_KEY`.
Saved keys are used by later runs, also with `--no-prompt`.

## 3. Commands of each step

Show the command and what it will do before running it: downloads take minutes and use
API quotas. Outputs are named after the query (non-word characters become `_`):
`Pubmed_<q>.txt`, `WOS_<q>.txt`, `Scopus_<q>.txt` and the merge `Merged_<q>.txt`.

**Search the APIs and merge** (one or more databases):

    JR -p -q "QUERY" --db all --fill-abstracts --no-prompt --outdir results/TOPIC

Options: `--db pubmed wos` (any subset), `--wos-api starter`, `--scopus-key personal`,
`--scopus-insttoken`, `--wos-query`, `--scopus-query`, `--keep-no-abstract`.
`-p -q "QUERY"` alone (PubMed only, no `--db`, no `--fill-abstracts`) keeps the original
single download without PRISMA table.

**Merge exported files** (any mix; PubMed > Web of Science > Scopus when duplicated):

    JR --merge Pubmed_X.txt savedrecs.txt scopus.csv --merge-out Merged_X.txt --fill-abstracts --outdir results/TOPIC

**Fill abstracts of a file already merged:** `JR --fill-abstracts Merged_X.txt` (writes
`Merged_X_filled.txt`).

Every merge writes, next to `Merged_X.txt`:

| File | Content |
|---|---|
| `Merged_X_prisma.xlsx` | sheets `summary` (PRISMA counts, as formulas), `records` (one row per record, screening columns to fill), `duplicates_removed` |
| `Merged_X_search_log.json` | databases, queries, dates, keys used (kind only), counts; read by the methods text |
| `Merged_X_no_abstract.txt` | records still without abstract (pre-marked exclude) |

## 4. Screening suggestions from criteria (`--suggest`)

Default criteria, valid for any topic: no abstract, erratum, correction, retraction,
editorial, comment, letter, news, note, book/conference review, biography, obituary,
interview, meeting abstract → `exclude`; review, meta-analysis, or a language other than
English → `maybe`. The researcher adds their own:

    JR --criteria-template results/TOPIC/criteria.txt     # empty file to fill in
    JR --suggest Merged_X.txt Merged_X_prisma.xlsx --criteria criteria.txt --outdir results/TOPIC

Criteria file lines (`name: values`, comma-separated): `include:` (at least one term
must appear in title/abstract), `exclude:` (any term gives exclude), `years: 2000-2026`,
`exclude types:`, `keep types:` (types not to exclude by default, e.g. `letter`),
`languages:` (kept without `maybe`). The same as flags: `--include-terms`,
`--exclude-terms`, `--years`. Terms match whole words, ignoring case and hyphen variants.

Help the researcher turn their question into criteria, but keep them general: rules
only see words. Writes `rules_suggestion`, `rules_reason`, `rules_score` in the
`records` sheet; `screening_decision` is untouched. Run it again after changing the
criteria: the columns are rewritten. The PRISMA table must be closed in Excel.

## 5. Analysis, report and context

    JR results/TOPIC/Merged_X.txt results/TOPIC/general.xlsx --lemma --context

- `--report`: `<input>_report/` with `network.html` (interactive co-occurrence network),
  `network.xlsx`, `network.graphml`, `trends.xlsx`, `trends.png`, `prisma_flow.png/.svg`,
  `methods_en.txt`. `--report-pt` adds `methods_pt.txt`.
- `--context` (implies `--report`): `<input>_report/context/`, the files you read after
  the run (references/context.md).
- Network options: `--net-min N` (minimum times two words appear side by side; default
  3; raise it for large sets), `--net-max-nodes N` (default 300), `--net-keep-generic`.
- Analysis options: `--lemma` (singular/plural together), `-sw word file.txt` (extra
  stopwords), `--ws term "two words"` (count only these terms), `-st term -so synonym`
  (groups). With `--ws` or `-st`, the trends follow those terms.

**After screening**, keep only the records marked include (or include and maybe) and
analyse them:

    JR --screen Merged_X.txt Merged_X_prisma.xlsx --keep include maybe --outdir results/TOPIC
    JR results/TOPIC/Merged_X_screened.txt results/TOPIC/included.xlsx --lemma --context

## 6. When something fails

Read the message: the tool says which flag or file is missing. A database that fails
(key refused, quota) does not stop the others; the merge says which one is missing, and
it can be added later with `--merge`. Do not retry downloads in a loop.
