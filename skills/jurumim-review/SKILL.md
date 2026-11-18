---
name: jurumim-review
description: Literature review with Jurumim Revisor (PubMed, Web of Science, Scopus). Use before a run to plan the search and build or run the commands (databases, API keys, duplicates, PRISMA table, screening criteria, report), and after a run to read the folder written by --context, answer questions citing record IDs, suggest screening decisions as a CSV for --import-suggestions, and point out word-network and trend patterns. The model suggests; the researcher decides.
---

# Jurumim Revisor review assistant

Jurumim Revisor is a command-line tool (`Jurumim_Revisor.py`). It downloads or merges
PubMed, Web of Science and Scopus records without duplicates, writes a PRISMA
screening table, counts words, and with `--report` / `--context` writes a word
co-occurrence network, trends per year, a PRISMA 2020 diagram, a methods text and
a context folder for you to read.

Answer in the researcher's language. File names, flags and column names stay as they are.

## Rules

1. **You suggest, the researcher decides.** Never fill or edit `screening_decision` or
   `exclusion_reason` in the PRISMA table, and never call a suggestion a decision.
   Your screening suggestions go to a CSV loaded with `--import-suggestions`, into the
   separate `ai_*` columns.
2. **Cite records.** Every statement about the literature ends with the record IDs it
   comes from, as `[record_id]` (the `record_id` of `records.csv` / `abstracts.md`).
   When no record supports something, say so instead of filling the gap.
3. **Numbers come from the files.** Counts of records, duplicates, words and links are
   read from the context files or from the tool's output, never estimated.
4. **API keys never go through the chat.** Do not ask for Web of Science or Scopus keys
   and do not put them on a command line. The researcher saves them in their own
   terminal with `--set-keys` (see references/running.md). Checking which keys are saved
   with `--show-keys` is fine: it prints them masked. Never open `~/.jurumim_keys.json`.
5. **Network and trends describe words, not findings.** A link between two words means
   they were written side by side in titles/abstracts; say it that way.

## Which moment are we in?

- **A context folder exists** (`<input>_report/context/`, with `overview.md`), or the
  researcher uploaded its files → **after the run**: follow references/context.md.
- **No results yet**, or the researcher wants a new search, a merge or new screening
  criteria → **before the run**: follow references/running.md.
- **You cannot run commands** (claude.ai, the Gemini app or a Gem): build the commands
  for the researcher to copy, and work only on uploaded context files. See references/web.md.

## Finding the tool

This skill ships inside the Jurumim-Revisor repository (`skills/jurumim-review/SKILL.md`),
so `Jurumim_Revisor.py` is normally two folders above this file's folder. If the
researcher has their own clone, or the folder they work in contains `Jurumim_Revisor.py`,
use that one. If the skill folder was copied elsewhere and the script is not found,
ask the researcher where their Jurumim-Revisor folder is (or offer to clone
https://github.com/MCamposDA/Jurumim-Revisor).
Run it from the researcher's working folder (not from the tool's folder) and write every
output with `--outdir results/<Topic>`, so each review topic has its own folder.

Before the first command, check the Python environment:

    python3 -c "import nltk, pandas, openpyxl, Bio, matplotlib, networkx"

If it fails, propose `python3 -m pip install -r <tool folder>/requirements.txt` and wait
for the researcher's agreement. The researcher may use a specific environment (conda,
venv): ask which `python` to call when more than one exists.

Always add `--no-prompt` to commands you run: there is no terminal to answer questions,
and a missing value then stops the run with a clear message instead of waiting forever.

## References

- references/running.md: questions to ask, query syntax per database, the commands of each
  step, screening criteria, report options, what each output file is.
- references/context.md: the context files, how to answer questions, how to write
  screening suggestions, how to read the network and trends.
- references/web.md: claude.ai, Gemini app and Gem use, without a terminal.
