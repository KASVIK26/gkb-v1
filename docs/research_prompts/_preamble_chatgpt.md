# TASK FOR CHATGPT DEEP RESEARCH

You are running as a deep-research agent with browsing, PDF reading and (if available) a Python sandbox. **Do not ask clarifying questions** -
every parameter is specified below; where something is unclear, take the conservative option and say so in `note`.

How to use your strengths:
- **Open PDFs fully** and read tables page by page; AICRP and ICAR reports hide most facts in tables on page 40-200 of a long PDF. If you have
  a Python sandbox, download the PDF and extract tables programmatically, then **re-check each emitted quote against the extracted text**.
- When a table row carries the variety and the disease name only appears in the table header/caption, build the quote as
  `<caption or header fragment> ... <row fragment>` (see rule 2 and 3).
- Work source by source and write candidates as you go; do not hold everything until the end. Prefer 150 solid candidates to 400 doubtful ones.
- Where a document can be opened but is long, say in `source_log.csv` which page range you covered so that I can ask you to continue.
- Deliver Part A also as a downloadable `candidates.jsonl` file if your interface allows, **and** in the chat as code blocks.
