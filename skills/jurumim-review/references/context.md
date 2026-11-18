# After the run: reading the context folder

`--context` writes `<input>_report/context/` (all plain text):

| File | Use it for |
|---|---|
| `README.md` | the same rules as this skill, for chats that only get the files |
| `overview.md` | read first: search, PRISMA counts, options, top words, communities, strongest links, trends |
| `records.csv` | metadata of every record and its screening columns (`screening_decision`, `rules_*`, `ai_*`) |
| `abstracts.md` | `## [record_id] Title`, then year, first author, journal, DOI, and the abstract |
| `network_terms.csv` | word, frequency, articles, community, degree, up to 25 record IDs |
| `network_links.csv` | pair of words, times side by side, times in each order, record IDs |
| `trends.csv` | per year and followed term: articles, share of the year's articles, 3-year share |
| `methods_en.txt` | methods text; `[brackets]` are left for the researcher |
| `suggestions_template.csv` | records without a screening decision, to be filled in |

The report folder above it also has `network.html` (open it in a browser),
`trends.png` and `prisma_flow.png`, for the researcher.

## Reading large folders

Read `overview.md` whole. Do not load all of `abstracts.md` at once when it is large:
search it for the terms of the question (or for `[record_id]`), and read the matching
records. `records.csv` and the network CSVs can be filtered with a short script.

## Answering questions

- Ground every claim in records and cite them: "Light traps were the most used
  collection method [record_id] [record_id]". Quote short passages when the wording matters.
- Separate what the records say from your interpretation, and say when the answer
  depends on records you did not read (e.g. "in the 40 records mentioning X").
- Counts (how many records mention X, per year, per database) come from the CSVs or a
  search of `abstracts.md`, stated with the method: "N of the M abstracts contain
  'light trap' (literal search)".

## Screening suggestions

1. Get the researcher's criteria: their question (population, exposure, outcome,
   design) and the inclusion/exclusion rules. Show your reading of them and wait for
   confirmation before suggesting anything.
2. Work on the records of `suggestions_template.csv` (not yet screened), in batches the
   researcher agrees to (e.g. 50 at a time), reading each title and abstract in
   `abstracts.md`. The `rules_*` columns of `records.csv`, when present, are another
   opinion: you may disagree, and say why.
3. Write a CSV with the template's columns, one row per record:

       record_id,title,suggestion,reason,evidence,model
       12345678,"Title of the record",include,"field survey of the target population","...short quote of the abstract...",<your model name>

   - `suggestion`: `include`, `exclude` or `maybe` (when title and abstract are not
     enough, or the criteria do not settle it).
   - `reason`: the criterion that decided it, in a few words.
   - `evidence`: a short literal quote of the title/abstract supporting the reason.
   - `model`: your model name and version.
   Save it as `results/<Topic>/ai_suggestions.csv` (or give it to the researcher to save).
4. The researcher loads it into the PRISMA table (closed in Excel):

       JR --import-suggestions ai_suggestions.csv Merged_X_prisma.xlsx --outdir results/TOPIC

   It fills `ai_suggestion`, `ai_reason`, `ai_evidence`, `ai_model`; the researcher then
   fills `screening_decision` themselves. Rows for record IDs not in the table, or with
   another word than include/exclude/maybe, are reported and skipped. Importing again
   replaces the previous `ai_*` values.
5. Remind the researcher that the methods text mentions the AI suggestions (it reads
   the `ai_*` columns) and that every decision is theirs.

## Network and trends

- **Communities** (`overview.md`, `network_terms.csv`): groups of words written near each
  other more than with the rest. Name each one by its words ("trap types", "Leishmania
  detection") and cite records where the group's words appear together
  (`network_links.csv`, `record_ids`).
- **Strongest links**: frequent two-word expressions of the field ("light trap",
  "cutaneous leishmaniasis"). The order counts (`a_before_b`, `b_before_a`) show how the
  pair is usually written.
- **Bridges**: words with links into several communities connect subjects; check them
  in `network_links.csv`.
- **Small separate groups**: a theme or a name that the rest of the literature does not
  mention (a species pair, a method, a place).
- **Trends** (`overview.md`, `trends.csv`): use `share_3yr_percent` (the year with its
  neighbours, left empty when fewer than 5 records). A rise in share means the subject is
  more frequent among the records of those years, not that it was studied more in
  absolute terms. Sparse early years are noisy: say so.
- Suggest thresholds when the network is crowded or empty: `--net-min` higher for a
  dense hairball, lower when few links remain.

Always describe these as patterns of words in titles and abstracts, with the record IDs
that show them.
