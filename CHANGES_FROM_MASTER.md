# What's new on `andreea` vs. `master`

Full diff: `git diff master...andreea --stat` (70 files changed, ~14,500 insertions,
1 commit: `92c77bd`). This document groups those changes by what they actually do,
not by file — useful as a "what did we add" reference alongside the diff itself.

## 1. Ingestion pipeline fixes (real bugs, not refinements)

- **Full-text scraping** (`src/ingestion/article_scraper.py`, new): GDELT-sourced
  articles previously never got their body text fetched — `content_clean` was built
  from title + GDELT snippet only, and GDELT's API essentially never returns a
  snippet. Confirmed 100% of the corpus had empty `content_raw` before this fix.
  Now downloads and extracts real article text via `trafilatura`, falls back to
  title-only on scrape failure rather than dropping the article.
- **Translator rate-limiting + corrupted-response detection** (`src/ingestion/translator.py`):
  translating full article bodies (vs. short titles) tripped Google Translate's
  free-endpoint rate limiting almost immediately, and the client library did not
  always raise on failure — under sustained rate limiting it silently returned the
  endpoint's own HTML error page as if it were a translation. Added an explicit
  inter-request delay and a defensive check that rejects responses matching the
  error page's signature.
- **Sports-content relevance exclusion** (`src/ingestion/relevance_filter.py`): a
  real China-vs-Romania table-tennis match satisfies plain co-occurrence but is out
  of scope for the bilateral-relations ontology; a multi-match roundup article could
  leak an unrelated match's sentence into event extraction. Added a narrow,
  low-false-positive exclusion (competition-governing-body acronyms, explicit sports
  section tags).
- **Google News wrapper-URL resolution** (`src/ingestion/google_news_resolver.py`,
  new) and **RSS/Atom feed ingestion** (`src/ingestion/rss_fetcher.py`,
  `src/ingestion/rss_pipeline.py`, `src/ingestion/feed_parser.py`, all new): the
  RSS ingestion path referenced in the project's requirements doc didn't actually
  exist before this branch; this is its first real implementation, plus a
  one-time reset script (`scripts/reset_google_news_articles.py`) for articles
  ingested before the wrapper-URL resolver existed.

## 2. Credibility layer: new detection pipeline

This is the largest substantive addition — a chain of new components in
`src/credibility/` and `src/temporal/`:

- **`semantic_similarity.py`** (new): sentence-embedding (MiniLM) corroboration
  matching, so independently-worded reports of the same event get merged into one
  corroboration group instead of only exact-signature duplicates.
- **`contradiction_nli.py`** (new): pretrained NLI cross-encoder
  (DeBERTaV3-based) contradiction detection between claim sentences within a group,
  with a cosine-similarity relevance pre-filter.
- **`src/temporal/reasoner.py`** (rewritten): replaced an informal 5-bucket
  temporal model with the complete 13-relation Allen Interval Algebra.
- **Temporal gate** (in `corroboration.py`): uses the Allen relations to
  distinguish genuine contradiction from ordinary claim evolution (e.g.
  "proposed" → "signed" → "ratified" are sequential stages, not a contradiction).
- **`src/temporal/lifecycle.py`** (new): explicit per-event-type claim-lifecycle
  finite-state machines (11 event types) with zero-shot NLI state classification,
  catching illegal state transitions (e.g. "ratified" reported chronologically
  before "signed") that the pairwise temporal gate alone can't see.
- **`src/credibility/publisher_networks.py`** (new): resolves mirror domains
  (e.g. Xinhua's regional/language editions) to a shared publisher identifier
  before computing source diversity, so a wire story republished across 8 domains
  counts as 1-2 independent networks, not 8 independent sources.
- **`src/credibility/veracity_score.py`** (new) and **`lexical_similarity.py`**
  (new): composite, ablatable veracity scoring and a lexical-overlap baseline.
- **`src/temporal/time_bucket_gate.py`** (new): a rule-based, same-mechanism-class
  reproduction of Allein et al. (EACL 2023)'s coarse time-bucket temporal
  representation, used as a fair ablation baseline against the exact Allen-relation
  gate.

## 3. Evaluation & annotation tooling (all new)

- `scripts/label_pairs.py` — blind relabeling CLI for a second annotator, with an
  enforced minimum-time-per-answer safeguard (added after repeated rushed-labeling
  incidents produced sub-second, invalid timing patterns).
- `scripts/compute_iaa.py` — Cohen's kappa between two label sets.
- `scripts/mine_real_candidate_pairs.py`, `mine_semantic_ablation_pairs.py`,
  `mine_nli_ablation_pairs.py` — mine real (not hand-constructed) candidate pairs
  from the live corpus for blind human/LLM-judge review, the last two specifically
  using uncertainty-sampling-style selection (stratified toward each threshold's
  decision boundary) rather than random sampling.
- `scripts/evaluate_{contradiction,corroboration,extraction,temporal_contradiction,veracity}.py`
  — precision/recall/F1 ablation scripts against the gold fixtures in
  `tests/fixtures/` (also new).
- `scripts/run_competency_queries_direct.py` — replicates the five competency-question
  query logic directly against the JSON exports (used once, before Neo4j was set up
  this session; superseded by real Cypher execution once Neo4j was running, but kept
  since it revealed a real, quantified finding — see the paper).
- `scripts/generate_experiment_report.py` — aggregates corroboration + veracity
  output into a readable markdown report.
- `scripts/run_big_experiment.sh`, `retry_gdelt_backfill.sh` — end-to-end
  ingestion→extraction→corroboration→veracity→mining pipeline runners.

## 4. The paper itself

`paper/paper.tex` (new, ~1,400 lines) — did not exist on `master`. Built from a
baseline draft the user supplied mid-session, then substantially revised:
corrected real bugs in that baseline (a duplicate-figure-caption LaTeX bug, a false
claim about MarianMT that doesn't exist in the codebase, a fabricated "ClaimFlow
κ=0.77" citation that turned out to reference an unrelated real paper), and added,
with real evidence behind every number:
- Allen's Interval Algebra as the temporal reasoning formalism (Section VI-C)
- The full semantic-merge → NLI → temporal-gate → lifecycle-verification
  credibility chain (Section VIII), with a rebuilt sequence diagram
  (`docs/plantuml/16_seq_module_credibility.puml` → `paper/16_seq_module_credibility.png`)
  matching the real code, not the old pre-session architecture
- Component ablations at two scales: small hand-labeled gold sets (10-12 pairs,
  threshold calibration) and large real-data pools (134 and 142 pairs, mined from
  the corpus and independently judged) — the large-scale NLI ablation surfaced a
  real, previously-hidden precision collapse (P=R=F1=0.000 on real formulaic
  press-release text) that the small hand-authored set never exposed
- LLM-judge concordance (κ=0.731) as an honestly-labeled substitute for a human
  second annotator, after repeated attempts to obtain real human labels failed
- Real competency-question (CQ1-CQ5) results computed against an actual populated
  Neo4j graph (Docker deployment), including a quantified finding that
  article-level co-occurrence overcounts true per-event bilateral linkage by
  2.7x-9.3x depending on the question
- Two corpus-level ablations (publisher-network dedup, sports-content exclusion)
  with real before/after numbers

## 5. What's *not* resolved yet (honestly still open)

- GDELT's DOC 2.0 Search API has been unreachable for an extended period; the
  historical 2017-2026 backfill that would substantially grow the corpus beyond
  its current RSS-only scale has not landed. `backfill_run.log` and
  `gdelt_backfill_retry.log` (both new, both large) document the attempts.
- A genuine human second annotator was never obtained (three attempts produced
  invalid, rushed, or admitted-non-independent data); the paper is honest about
  this and reports the LLM-judge substitute instead.
- No external system/benchmark comparison exists yet beyond the mechanism-level
  Allein et al. reproduction already in the ablations.
