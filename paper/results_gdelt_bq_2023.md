# GDELT BigQuery ingest, 2023: run results

Corpus build for China–Romania articles published in 2023, run 2026-10-31 to 2026-11-08.
Numbers come from `db/temporal_kg.sqlite` (articles with `fetched_at >= 2026-10-31`) and
from the run logs `gdelt_bq_ingest.log`, `gdelt_bq_full.log`, `gdelt_bq_resume{,2,3}.log`.

## Setup

- **Candidate source:** GDELT GKG v2 (`gdelt-bq.gdeltv2.gkg_partitioned`), queried in the BigQuery sandbox
  (`scripts/gdelt_bigquery.sql`). Partition window 2023-01-01 to 2024-01-01.
- **Precision filters in SQL:** at least two `#RO#` and at least two `#CH#` FIPS location mentions
  (country fields, not name substrings), and no `SPORT` themes. `LIMIT 20000`.
- **Export:** 19,996 unique article URLs (`data/raw/gdelt_bq_2023.csv`).
- **Pipeline** (`scripts/ingest_gdelt_csv.py`): scrape, language detection, translation to English
  (local NLLB-200 distilled-600M), China+Romania relevance filter (sports excluded), deduplication
  (URL and content hash), then persist to SQLite plus one JSON file per article.
- **Pilot:** a 200-URL run on an earlier, looser query (`data/raw/gdelt_bq.csv`, 2026-10-31) is
  included in the database totals below.

## Runs

| Run | URLs processed | Wall time |
|---|---:|---:|
| Pilot (looser query) | 200 | 0:19 |
| Full run (interrupted) | 7,506 | 4:53 |
| Resume 1 (interrupted) | 4,080 | 2:01 |
| Resume 2 (stopped manually) | 1,075 | 0:29 |
| Resume 3 (completed) | 7,346 | 3:26 |
| **Total** | **≈20,200** | **≈11:09** |

- Average throughput is about 2.0 s per URL, end to end (scrape + translate + filter + store).
  Most of the time goes to network scraping and translation.
- The resumes used `--skip`. A few URLs were reprocessed at each cut-over and were caught by
  deduplication.
- Only the pilot and Resume 3 printed a summary line:
  - Pilot: 117 new, 83 dup, 21 relevant, 0 errors.
  - Resume 3: 6,579 new, 757 dup, 613 relevant, 10 errors.

## Outcome (database, all runs)

| | Count | Share |
|---|---:|---:|
| Articles stored | 18,002 | 100% |
| Relevant (China+Romania co-occurrence) | **2,010** | **11.2%** |
| Status `cleaned` | 17,948 | 99.7% |
| Status `error` (mandatory translation failed) | 54 | 0.3% |

### Relevance-filter decisions

| Reason | Articles |
|---|---:|
| `no_match` | 11,391 |
| `china_only` | 3,845 |
| `china+romania_co-occurrence` (relevant) | 2,010 |
| `romania_only` | 497 |
| `excluded_sports_content` | 205 |
| `translation_failed_from_*` | 54 |

### Scraping failures

9,564 stored articles (53%) have a `fetch_error`. Their full text could not be scraped, so
only GDELT metadata (title, URL, date) was available to the relevance filter. Only 15 of them
ended up relevant.

| Failure | Articles |
|---|---:|
| HTTP 403 Forbidden (anti-bot) | 5,104 |
| Connect timeout | 916 |
| Connection error | 703 |
| No extractable text | 701 |
| HTTP 404 Not Found | 629 |
| Read timeout | 77 |
| HTTP 429 Too Many Requests | 54 |
| Translation failed | 54 |

### Relevant corpus

- **Published:** 2023-01-01 to 2023-12-31, spread evenly across the year:

  | Month | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
  |---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
  | Relevant articles | 171 | 165 | 110 | 129 | 219 | 151 | 182 | 106 | 201 | 148 | 205 | 223 |

- **Average cleaned length:** about 8,800 characters. 17 relevant articles have under 200 characters.
- **Top domains:** 163.com (72), sohu.com (59), actualno.com (42), ziaruldevrancea.ro (26),
  fakti.bg (25), menafn.com (24), evz.ro (20), bursa.ro (19), ziare.com (18), newsru.co.il (18).

### Translation

- 13,349 unique URLs passed through the translator (from the logs).
- Detected source languages: ru 5,012, zh-CN 3,538, ro 927, sv 798, da 581, fr 515, vi 324,
  ko 218, bg 161, it 131, es 120, ar 120, el 116, de 107, hu 89, plus a long tail.

## What the collected data means (analysis, 2026-11-08)

### Most "relevant" articles are not about China–Romania relations

The relevance filter only checks that both countries appear somewhere in the article. That is
a much weaker test than "the article is about the two countries".

- **Same-sentence test:** only **693 of the 2,010** relevant articles (34%) mention both
  countries in the same sentence.
- **Manual audit:** I read a random sample of 40 relevant articles (seed 7). Only **3 of 40
  (about 8%)** are actually about China–Romania relations: a Romanian held in a Chinese prison,
  Romanian tourists returning to China, and Romanian imports from China by county.

| Category (manual audit, n=40) | Articles |
|---|---:|
| About China–Romania relations | 3 |
| Lists of countries (rankings, market reports, participant lists, casualty lists) | 13 |
| Story about one country, other mentioned in passing | 14 |
| Calendars, almanacs, currency-rate tables | 4 |
| Sports and chess leftovers (the sports filter missed them) | 3 |
| US politics (Biden-family business in Romania and China) | 2 |
| Alias false positive (Korean name "Ro") | 1 |

**Takeaway:** at scale, co-occurrence relevance has low precision, roughly 8% by this small
sample. The earlier, smaller corpora used in the paper's evaluation were cleaner because they
came from targeted searches.

### Three concrete failure modes found

1. **The `"ro"` alias.** `config/settings.yaml` lists `"ro"` as a Romania term, and the match is
   case-insensitive, so the name "Ro" or a `.ro` token counts as a Romania mention.
   - **180 of 2,010** relevant articles (9%) match Romania **only** through `ro`.
2. **Sports filter coverage.** **238** relevant articles still match chess, Olympic,
   championship, tournament, FIFA, UEFA or World Cup terms. The sports-marker exclusion
   (205 articles removed) catches governing-body acronyms but misses chess and many
   match-report styles.
3. **NLLB-200 (600M) hallucinates on Chinese.** I compared GDELT's original titles with the
   stored English titles for a random sample of Chinese pages. Many translations are fluent
   but unrelated:
   - 「7天掉粉200万！东方甄选宣布今日停播」 ("lost 2 million followers in 7 days, East Buy stops
     broadcasting") became "The South Korean government has announced that it will stop its
     operations…".
   - 「中国代表团夺金势头强劲」 ("Chinese delegation's strong gold-medal run") became "The Chinese
     government has been trying to get the Chinese government to move forward."

   Russian translations in the same sample were faithful. Among scraped articles longer than
   500 characters, **18% of `no_match` articles** have degenerate repetitive output (more than
   30% repeated 4-grams), compared with **1% of relevant articles**.

   This mostly does not cost relevant articles: the original Chinese titles in the `no_match`
   sample do not mention Romania either. But it would corrupt entity, relation and event
   extraction on any Chinese article that is kept.

### Where the 63% `no_match` comes from

- 8,902 of the 11,391 `no_match` articles **could not be scraped**, so only the GDELT title was
  checked.
- The other 2,489 were scraped and still contain no China or Romania term. Their original
  titles (from the CSV) are domestic Chinese news.
- So GDELT's `#RO#` location tagging, which is translingual and automatic, produces many
  false positives on Chinese pages, even with the "at least two mentions" rule.

### What the relevant set is about (context, keyword counts over the 2,010)

| Context keyword | Articles |
|---|---:|
| Russia | 1,017 |
| Trade, export, import, tariff | 878 |
| Ukraine war | 801 |
| EU | 533 |
| NATO | 285 |
| Covid | 268 |
| Nuclear (incl. Cernavodă) | 220 |
| Tourism, flights | 217 |
| Moldova | 213 |
| Taiwan | 203 |
| Black Sea, Danube | 129 |
| EV, BYD, automotive | 90 |
| Belt and Road, 16+1 | 56 |
| Huawei, 5G | 39 |

- **The war in Ukraine dominates.** In 2023 China and Romania appear together mainly as actors
  around the war: Romania as a NATO frontline state, China as Russia's partner. Direct bilateral
  topics (Belt and Road, Huawei, Chinese investment) are a small minority.
- **Event triggers in the 693 same-sentence articles:**

  | Event type | Articles |
  |---|---:|
  | PolicyStatement | 70 |
  | CompanyActivity | 55 |
  | CulturalExchange | 49 |
  | DiplomaticMeeting | 46 |
  | TechnologyCooperation | 32 |
  | InvestmentProject | 29 |
  | TradeAgreement | 20 |
  | EducationCooperation | 18 |
  | InfrastructureProject | 10 |
  | SecurityStatement | 8 |
  | SanctionOrRestriction | 1 |

  These counts come from regex triggers only, not the full extraction pipeline.
- **Domains:** .com 900, .ro 334, .cn 75, .gr 63, .it 49, .hu 46, .ua 33, .bg 32, .ru 30. The
  Romanian press is the largest national block; Chinese domains are few after filtering.
- **Monthly same-sentence counts:**

  | Month | Jan | Feb | Mar | Apr | May | Jun | Jul | Aug | Sep | Oct | Nov | Dec |
  |---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
  | Same-sentence articles | 53 | 46 | 30 | 30 | 91 | 62 | 67 | 37 | 78 | 59 | 64 | 76 |

  The peak months are not driven by bilateral events. In May the top items are the Biden-family
  Romania story, Huawei Romania's 2022 results, and the China–CEE fair in Ningbo. In December
  they are Israel-war roundups and Egypt's presidential election.

### Status of downstream processing

- Entity, relation, temporal and event extraction have **not** been run on this corpus yet: the
  `entities`, `relations` and `temporal_expressions` tables are empty.
- Original-language text is **not** stored: `content_raw` is empty, set in
  `src/ingestion/pipeline.py:238`. Translation errors therefore cannot be audited from the
  database. Only the GDELT titles in the CSV survive.

## Caveats for the paper

- **Detected languages are not ground truth.** Language detection mislabels some pages: some
  Chinese-language sites were tagged `sv` or `ko`. Treat the language counts as approximate.
- **Database language field.** `articles.language` stores the post-translation language (`en`),
  so source-language counts come from the logs, not the database.
- **Precision gap.** The GKG FIPS filter (both countries mentioned at least twice) is far less
  precise than the pipeline's own relevance filter: only 11% of stored articles pass. Much of
  the gap is scraping failure (53% unscrapable), not off-topic content.
- **Reported numbers.** The 2,010 relevant articles are the BigQuery corpus. The database holds
  2,109 relevant articles in total, including earlier RSS/GDELT-API ingests.
