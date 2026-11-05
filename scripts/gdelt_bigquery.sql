-- China+Romania article URLs from GDELT GKG, for scripts/ingest_gdelt_csv.py.
-- Run in the BigQuery console (sandbox, no billing). Widen the date range one
-- year at a time. Then: "Save results" -> CSV (local download) -> data/raw/gdelt_bq.csv
--
-- Precision filters (the first version, a bare LIKE '%Romania%', pulled blogs and
-- sports pages that merely mention both countries once):
--   * location FIPS codes #RO# / #CH# -- the country field, not a name substring
--   * each country mentioned >= 2 times, i.e. the article is about both
--   * sports-themed pages dropped (the pipeline excludes them anyway, later and
--     after paying for scrape + translate)
SELECT
  DATE AS date,
  DocumentIdentifier AS url,
  SourceCommonName AS domain,
  REGEXP_EXTRACT(Extras, r'<PAGE_TITLE>(.*?)</PAGE_TITLE>') AS title
FROM `gdelt-bq.gdeltv2.gkg_partitioned`
WHERE _PARTITIONTIME >= TIMESTAMP('2023-01-01')
  AND _PARTITIONTIME <  TIMESTAMP('2024-01-01')
  AND ARRAY_LENGTH(REGEXP_EXTRACT_ALL(V2Locations, r'#RO#')) >= 2
  AND ARRAY_LENGTH(REGEXP_EXTRACT_ALL(V2Locations, r'#CH#')) >= 2
  AND IFNULL(V2Themes, '') NOT LIKE '%SPORT%'
LIMIT 20000
