# TASK FOR GROK (DeepSearch / Think)

You have live web search. **Do not ask clarifying questions** - every parameter is specified below; take the conservative option where unclear.

How to use your strengths and avoid your weak spots:
- You are strongest at **finding** current documents (state-university advisories, institute pages, recent bulletins, pathotype surveys). X/Twitter
  posts, news and YouTube are useful only as **pointers** to a primary document - find the document itself and cite that, never the post.
- PDF table extraction can be unreliable. **If you cannot read a table cell with certainty, do not emit it** - put the document in `leads.md`
  with the page number. A candidate with a quote that is not letter-for-letter on the page is rejected.
- Quote exactly what the page shows, including odd spellings and units (`0.1 %`, `@ 2 g/kg`). Do not normalise.
- Work in chunks of at most 40 candidates per code block and stop cleanly with `CONTINUE AFTER candidate_id=...` rather than shortening quotes
  to fit.
- Verify each paper's PMID by opening its PubMed / Europe PMC record; do not recall PMIDs from memory.
