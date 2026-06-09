# Temporal Knowledge Graph — China & Romania

A modular Python research project that builds a **temporal knowledge graph** from news articles about China and Romania. This implementation follows the requirements paper: "Building and maintaining a temporal knowledge graph for news streams on China-Romania" which combines ontology reasoning for semantic consistency, temporal modeling for event ordering and validity, and a fake news detection layer that evaluates claims using provenance, cross-source corroboration, and graph consistency.

The project extracts entities, relations, and temporal expressions from multilingual news streams restricted to articles mentioning both China and Romania. It stores intermediate results in SQLite and exports the final graph to Neo4j for querying and analysis.

---

## Project Layout

```
temporal_kg/
├── config/
│   ├── settings.yaml        ← single source of truth for all config
│   └── .env.example         ← copy to .env, fill in secrets
│
├── data/
│   ├── raw/                 ← optional/raw artifacts (git-ignored)
│   ├── processed/           ← GDELT-derived article text, NLP output
│   └── exports/             ← Cypher scripts, JSON exports
│
├── db/
│   ├── migrations/          ← numbered .sql migration files
│   └── temporal_kg.sqlite   ← created on first run (git-ignored)
│
├── logs/                    ← rotating log files (git-ignored)
│
├── notebooks/               ← optional legacy exploration notebooks
│
├── scripts/
│   ├── init_project.py      ← one-shot project setup script
│   ├── run_ingestion.py     ← CLI for GDELT ingestion
│   ├── run_exploration.py   ← CLI replacement for 01_exploration.ipynb
│   ├── run_article_inspection.py
│   ├── run_entity_analysis.py
│   ├── run_event_timelines.py
│   └── run_graph_visualization.py
│
├── src/
│   ├── ingestion/           ← GDELT article fetching and processing
│   ├── extraction/          ← NLP: entities, relations
│   ├── temporal/            ← date normalisation, temporal anchoring
│   ├── graph/               ← Neo4j connector, Cypher builders
│   ├── ontology/            ← entity types, relation taxonomy
│   ├── credibility/         ← source credibility scoring
│   └── utils/
│       ├── config.py        ← settings loader
│       ├── logger.py        ← structured logging factory
│       └── db.py            ← SQLite database manager
│
└── tests/
    ├── unit/
    └── integration/
```

---

## Requirements Paper Alignment

This implementation addresses the key requirements from "Building and maintaining a temporal knowledge graph for news streams on China-Romania":

### A. GDELT for Tracking Romania–China News

The project uses the **GDELT 2.0 Full-Text Search API** to discover China–Romania articles:
- Queries the GDELT API for articles matching "China Romania"
- Uses GDELT-provided fields (title/snippet/description) as source text
- Language-detects and normalizes article text
- Translates non-English articles to English
- Filters for relevance (must mention both China and Romania)
- Persists to SQLite + JSON

Configuration: `config/settings.yaml` → `gdelt`

Run ingestion:
```bash
# Default (last 1 week):
python scripts/run_ingestion.py

# Custom timespan:
python scripts/run_ingestion.py --timespan 24hours

# Explicit date range:
python scripts/run_ingestion.py --start 2024-01-01 --end 2024-02-01

# Dry-run (query GDELT only, no downloads or DB writes):
python scripts/run_ingestion.py --dry-run
```

### B. Temporal Knowledge Graph Extraction

**DeepKE Integration** (Requirement B)
- Entity and relation extraction using DeepKE
- Configuration: `config/settings.yaml` → `extraction.deepke`
- Implementation: `src/extraction/deepke_client.py`, `src/extraction/deepke_adapter.py`
- Run: `python scripts/run_deepke_extraction.py`

**HeidelTime TIMEX3 Extraction** (Requirement B)
- Temporal expression extraction and normalization to TIMEX3 format
- Handles expressions like "visited on 12 May 2026" or "agreement valid until 2030"
- Configuration: `config/settings.yaml` → `temporal.heideltime`
- Implementation: `src/temporal/heideltime_client.py`
- Run: `python scripts/run_temporal_extraction.py --engine heideltime`

**Neo4j Graph Database** (Requirement B)
- Neo4j Python Driver integration
- Graph schema with constraints and indexes
- Implementation: `src/graph/neo4j_connector.py`, `src/graph/graph_loader.py`
- Visualization: neo4j-viz support via `scripts/run_neo4j_viz.py`

**Temporal KG Reasoning** (Requirement B)
- Temporal validity intervals and event ordering
- Implementation: `src/temporal/reasoner.py`
- Detects temporal inconsistencies and contradictions

### C. Bilateral Relations Ontology

**CAMEO / GDELT Event Taxonomy** (Requirement C)
- Maps bilateral event types to CAMEO categories and GDELT taxonomy
- Implementation: `src/ontology/taxonomy.py`
- Supported event types:
  - Diplomatic meetings
  - Trade agreements
  - Investment projects
  - Technology cooperation
  - Infrastructure projects
  - Education cooperation
  - Security statements
  - Sanctions or restrictions
  - Company activities
  - Cultural exchanges

**IPTC Media Topics Classification** (Requirement C)
- Each event annotated with IPTC topic categories
- Examples: "Politics/Diplomacy", "Economy, Business and Finance/Trade"

**W3C OWL-Time Temporal Validity** (Requirement C)
- Temporal intervals with start and end dates
- Granularity tracking (day, month, year)
- Duration and interval support (ISO 8601)

**EventKG-style Temporal KG** (Requirement C)
- Event-centric temporal knowledge graph
- Event representation: who, what, when, where
- Provenance tracking for all claims

### D. Competency Questions

The implementation provides query support for all competency questions from the requirements:

**Query 1**: "How did China–Romania economic relations evolve from 2020 to 2026?"
```python
from src.graph.competency_queries import CompetencyQueries
queries = CompetencyQueries()
result = queries.china_romania_economic_evolution(
    start_date="2020-01-01",
    end_date="2026-12-31"
)
```

**Query 2**: "Which Romanian institutions were most often connected to Chinese companies?"
```python
result = queries.romanian_institutions_connected_to_chinese_companies(limit=20)
```

**Query 3**: "Which China–Romania events were reported in a given period?"
```python
result = queries.bilateral_events_in_period(
    start_date="2024-01-01",
    end_date="2024-12-31",
    event_categories=["trade", "diplomatic", "cultural"]
)
```

**Query 4**: "Which claims later became contradicted or unverified? Which sources systematically produce low-credibility bilateral narratives?"
```python
result = queries.contradicted_or_unverified_claims(credibility_threshold=0.5)
```

**Query 5**: "Which collaborative research has been conducted with authors from China and Romania?"
```python
result = queries.collaborative_research_authors(limit=50)
```

Run all competency queries:
```bash
python scripts/run_competency_queries.py
python scripts/run_competency_queries.py --query economic-evolution --start-date 2020-01-01
python scripts/run_competency_queries.py --output results/report.json
```

### Fake News Detection Layer

**Provenance Tracking**
- Every claim linked to source articles
- Source credibility scoring based on domain reputation
- Implementation: `src/credibility/scorer.py`

**Cross-Source Corroboration**
- Identifies claims supported by multiple independent sources
- Detects single-source unverified claims
- Implementation: `src/credibility/corroboration.py`

**Graph Consistency Checks**
- Temporal inconsistency detection
- Event contradiction identification
- Implementation: `src/temporal/reasoner.py`, `src/credibility/fake_news.py`

**Claim Verification Status**
- `corroborated`: Supported by multiple reliable sources
- `unverified`: Single source, low corroboration
- `contested`: Contradictory reports or temporal issues

Run fake news analysis:
```bash
python scripts/run_fake_news_analysis.py
python scripts/run_corroboration_analysis.py
```

---

## Quick Start

### Installation

See **[docs/INSTALLATION.md](docs/INSTALLATION.md)** for detailed installation instructions.

**Quick setup:**

```bash
# Clone repository
git clone https://github.com/andreeaonaci/Ch-RO.git
cd Ch-RO

# Run automated setup script
bash scripts/setup.sh

# Activate environment
conda activate temporal_kg
```

**System requirements:**
- Python 3.11+
- Java JDK (for py-heideltime temporal extraction)
- Perl (for py-heideltime temporal extraction)
- Conda (Miniconda or Anaconda)

### Manual Setup

### 1. Create and activate the Conda environment

```bash
conda env create -f environment.yml
conda activate temporal_kg
```

### 2. Initialise the project

```bash
python scripts/init_project.py
```

This will:
- Create all required folders
- Copy `config/.env.example` → `config/.env`
- Create the SQLite database and run migrations
- Download the spaCy language model

### 3. Add your secrets

```bash
# Edit config/.env with your Neo4j credentials (when needed)
nano config/.env
```

### 4. Run the tests

```bash
pytest
```

### 5. Run analysis from the command line

```bash
python scripts/run_ingestion.py
python scripts/run_ingestion.py --timespan 24hours
python scripts/run_article_inspection.py --limit 20
python scripts/run_entity_analysis.py --top 20
python scripts/run_event_timelines.py --start-date 2024-01-01 --end-date 2026-12-31
python scripts/run_graph_visualization.py --max-events 20
python scripts/run_corroboration_analysis.py
python scripts/run_fake_news_analysis.py

---

## Extended Setup (HeidelTime, DeepKE, Neo4j-viz)

This project can integrate the exact tools specified in the paper outline:

### HeidelTime (TIMEX3)

1. Install Java (OpenJDK).
2. Download HeidelTimeStandalone and place the jar here:
    `tools/heideltime/HeidelTimeStandalone.jar`
3. Set the config directory in `config/settings.yaml`:
    `temporal.heideltime.config_dir`

Enable it:

```bash
# config/settings.yaml
temporal:
  engine: "heideltime"
  heideltime:
     enabled: true
```

Run temporal extraction:

```bash
python scripts/run_temporal_extraction.py --engine heideltime
```

### DeepKE (entities/relations)

1. Install DeepKE in `tools/deepke`.
2. Configure the command template in `config/settings.yaml`:
    `extraction.deepke.command_template`

Enable it:

```bash
# config/settings.yaml
extraction:
  use_deepke: true
  deepke:
        enabled: true
        command_template: "python ../../scripts/deepke_runner.py --input {input} --output {output}"
        conda_env: "deepke_py38"
```

Run DeepKE outputs:

```bash
python scripts/run_deepke_extraction.py
```

Then run the standard extraction scripts to merge outputs:

```bash
python scripts/run_entity_extraction.py
python scripts/run_event_extraction.py
python scripts/run_relation_extraction.py
```

### Neo4j-viz + Plotly

Neo4j-viz works inside Jupyter/Streamlit if installed. The helper script will
use neo4j-viz if available, otherwise it exports a Plotly HTML timeline.

```bash
python scripts/run_neo4j_viz.py
```
```

---

## Configuration

All settings live in **`config/settings.yaml`**.  
Any value can be overridden with an environment variable:

```
TEMPORAL_KG_<SECTION>_<KEY>=value
```

Examples:

| Setting | Env var |
|---|---|
| `logging.level` | `TEMPORAL_KG_LOGGING_LEVEL=DEBUG` |
| `database.neo4j_password` | `TEMPORAL_KG_DATABASE_NEO4J_PASSWORD=secret` |

Key GDELT settings (`config/settings.yaml` → `gdelt`):

| Setting | Default | Description |
|---|---|---|
| `gdelt.query` | `"China Romania"` | Search query |
| `gdelt.max_records` | `250` | Max articles per request (GDELT cap) |
| `gdelt.default_timespan` | `"1week"` | Default look-back window |
| `gdelt.default_credibility` | `0.7` | Default credibility score for GDELT articles |

---

## Key Design Decisions

| Decision | Rationale |
|---|---|
| **GDELT API** for article discovery | Single authoritative source covering global news; no per-site scraping maintenance |
| **SQLite** for intermediate storage | Zero-config, portable, fast for single-machine research |
| **Numbered SQL migrations** | Reproducible schema evolution; easy to inspect in plain text |
| **settings.yaml + .env overlay** | Human-readable defaults; secrets stay out of version control |
| **Lazy imports for spaCy / Neo4j** | Project runs without heavy deps until the phase that needs them |

---

## Roadmap

- [ ] Phase 1 — Ingestion: GDELT fetcher → SQLite
- [ ] Phase 2 — Extraction: spaCy NER + relation patterns
- [ ] Phase 3 — Temporal anchoring: date normalisation
- [ ] Phase 4 — Credibility: domain scoring + cross-source validation
- [ ] Phase 5 — Graph build: export to Neo4j
- [ ] Phase 6 — Analysis notebooks

---

## Requirements

- Python 3.11
- Conda (Miniconda or Anaconda)
- SQLite (bundled with Python)
- Neo4j *(optional — only needed for Phase 5)*
