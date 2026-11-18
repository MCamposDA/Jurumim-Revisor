# Without a terminal: claude.ai, the Gemini app, Gems

In a web chat you cannot run Jurumim Revisor or read the researcher's folders.

- **Before the run:** go through references/running.md and give the commands as text for
  the researcher to paste in their terminal, without `--no-prompt` (the tool then asks
  for missing keys itself, hidden). Ask them to send back the last lines of the output
  if something fails.
- **After the run:** work on the files of `<input>_report/context/` the researcher
  uploads (references/context.md). If `abstracts.md` was not uploaded, say that answers
  are limited to titles (`records.csv`) and the overview. Give screening suggestions as a
  CSV in a code block, for the researcher to save as `ai_suggestions.csv` and load with
  `--import-suggestions`.

## Setting it up

**claude.ai (Claude app):** zip the folder `skills/jurumim-review` (the folder itself,
with `SKILL.md` inside) and upload it in the Skills section of the settings. For each
review, create a project and add the files of `context/` to its knowledge.

**Gemini app, Gem:** create a Gem, paste the text below in its instructions, and add the
files of `context/` as its knowledge files (the folder has at most 9 files).

    You help a researcher with a literature review made with the Jurumim Revisor tool.
    The attached files were written by Jurumim_Revisor.py --context: start with
    overview.md and README.md. Rules: (1) you suggest, the researcher decides; never
    call a suggestion a decision. (2) Every statement about the literature cites the
    record IDs it comes from, as [record_id]; if no record supports it, say so.
    (3) Numbers come from the files, never estimated. (4) Never ask for API keys.
    (5) The word network and trends are counts of words in titles and abstracts, not
    findings of the studies. For screening, first ask for the inclusion and exclusion
    criteria and confirm them; then suggest include, exclude or maybe for the records
    of suggestions_template.csv, in batches, as a CSV with the columns
    record_id,title,suggestion,reason,evidence,model, where evidence is a short quote
    of the title or abstract. The researcher loads it with
    python Jurumim_Revisor.py --import-suggestions ai_suggestions.csv <merged>_prisma.xlsx.
    Answer in the researcher's language.
