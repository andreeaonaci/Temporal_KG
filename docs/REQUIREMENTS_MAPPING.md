# Requirements Paper Implementation Mapping

This document provides a detailed mapping between the requirements paper "Building and maintaining a temporal knowledge graph for news streams on China-Romania" and the implementation.

## Overview

The system implements a temporal knowledge graph (TKG) from a multilingual news stream restricted to articles that mention both China and Romania. It combines:
- **Ontology reasoning** for semantic consistency and inference
- **Temporal modeling** for event ordering and validity
- **Fake news detection** layer using provenance, cross-source corroboration, graph consistency, and fact-check resources

## Section A: RSS Feeds for Tracking Romania–China News

### Requirements
- Google News RSS feed: `https://news.google.com/rss/search?q=%22Romania%22%20%22China%22&hl=en-US&gl=US&ceid=US:en`
- Radio Romania International (RRI): `https://www.rri.ro/en/feed`
- Bursa Romania feeds:
  - `https://www.bursa.ro/titluribursa.xml`
  - `https://www.bursa.ro/piata-capital-bursa.xml`
- Radio Free Europe: `https://www.rferl.org/api/ziiivl-vomx-tpemgmt`
- CGTN feeds (filtered for Romania content)

### Implementation
**Location**: `config/settings.yaml` → `ingestion.rss_feeds`

**Status**: ✅ Complete
- All specified RSS feeds configured
- Additional credibility scores assigned to each feed
- Country and focus area tags for filtering
- Support for bilateral-specific feeds (Google News)

**Files**:
- `config/settings.yaml` (lines 49-119)
- `src/ingestion/rss_fetcher.py`
- `src/ingestion/feed_parser.py`

## Section B: Temporal Knowledge Graph Extraction

### Requirement B.1: DeepKE for Entity and Relation Extraction

**Status**: ✅ Complete

**Implementation**:
- DeepKE client for running external DeepKE commands
- Adapter for normalizing DeepKE output to project schema
- Integration with main entity extraction pipeline
- Merge strategy for combining rule-based and DeepKE entities

**Files**:
- `src/extraction/deepke_client.py`
- `src/extraction/deepke_adapter.py`
- `src/extraction/entity_extractor.py` (lines 171-251)
- `scripts/run_deepke_extraction.py`

**Configuration**:
```yaml
extraction:
  use_deepke: false  # Enable when DeepKE is installed
  deepke:
    enabled: false
    command_template: "python ../../scripts/deepke_runner.py --input {input} --output {output}"
    working_dir: "tools/deepke"
    output_dir: "data/exports/deepke"
    timeout_seconds: 600
```

### Requirement B.2: HeidelTime for TIMEX3 Temporal Extraction

**Status**: ✅ Complete

**Implementation**:
- **Python Package**: `py-heideltime` (version 1.0.6+)
- HeidelTime Python wrapper for easy integration
- TIMEX3 XML parsing and normalization
- Normalization of temporal expressions to ISO 8601
- Support for:
  - Absolute dates: "12 May 2026"
  - Relative dates: "yesterday", "last week"
  - Durations: "for 3 months"
  - Intervals: "from 2020 to 2026", "valid until 2030"
- Automatic fallback to regex-based extraction when py-heideltime unavailable
- **System Requirements**: Java JDK and Perl (required by py-heideltime)

**Files**:
- `src/temporal/heideltime_client.py` (rewritten to use py-heideltime)
- `src/temporal/temporal_extractor.py`
- `src/temporal/date_normaliser.py`
- `scripts/run_temporal_extraction.py`

**Configuration**:
```yaml
temporal:
  engine: "heideltime"  # Use py-heideltime
  heideltime:
    enabled: true
    language: "en"
    document_type: "news"
```

**Installation**:
```bash
# Install via conda environment
conda env create -f environment.yml

# Or install manually
pip install py-heideltime

# System dependencies (required)
# Ubuntu/Debian:
sudo apt install default-jdk perl

# macOS:
brew install openjdk
# Perl is pre-installed

# Windows:
# Install Java JDK from Oracle
# Install Strawberry Perl from strawberryperl.com
```

**Usage**:
```python
from src.temporal.heideltime_client import HeidelTimeClient
from datetime import datetime

client = HeidelTimeClient()
text = "The meeting was held on August 31st and lasted for 3 hours."
anchor = datetime(2024, 8, 30)

temporals = client.extract_timex3(
    text,
    article_id="test_001",
    anchor=anchor
)

# Returns:
# [
#   {
#     "text": "August 31st",
#     "kind": "absolute_date",
#     "normalized": "2024-08-31",
#     "granularity": "day",
#     "source": "py-heideltime"
#   },
#   {
#     "text": "3 hours",
#     "kind": "duration",
#     "normalized": "PT3H",
#     "granularity": None,
#     "source": "py-heideltime"
#   }
# ]
```

### Requirement B.3: Neo4j Graph Database

**Status**: ✅ Complete

**Implementation**:
- Neo4j Python driver integration
- Graph schema with constraints and unique indexes
- Batch loading for performance (500 records per batch)
- Node types:
  - `Article`: Source articles with metadata
  - `Entity`: People, organizations, locations, countries
  - `Event`: Bilateral events with taxonomy
  - `TemporalExpression`: TIMEX3 temporal expressions
  - `Claim`: Verifiable claims from events
- Relationship types:
  - `REPORTED_IN`: Event → Article
  - `INVOLVES`: Event → Entity (participant)
  - `HAS_TIME`: Event → TemporalExpression
  - `RELATED_TO`: Claim → Event
  - `MENTIONS`: Article → Entity

**Files**:
- `src/graph/neo4j_connector.py`
- `src/graph/graph_loader.py`
- `src/graph/cypher.py` (schema statements)

**Configuration**:
```yaml
database:
  neo4j_uri: "bolt://localhost:7687"
  neo4j_user: "neo4j"
  neo4j_password: ""

graph:
  neo4j_batch_size: 500
```

### Requirement B.4: neo4j-viz Visualization

**Status**: ✅ Complete

**Implementation**:
- Support for neo4j-viz in Jupyter/Streamlit environments
- Fallback to Plotly timeline visualization
- Interactive graph exploration
- Timeline views of bilateral events

**Files**:
- `scripts/run_neo4j_viz.py`
- `src/reporting/plotly_viz.py`

### Requirement B.5: Temporal KG Reasoning

**Status**: ✅ Complete

**Implementation**:
- Temporal consistency checking
- Event ordering and sequencing
- Interval overlap detection
- Contradiction identification based on temporal constraints

**Files**:
- `src/temporal/reasoner.py`

## Section C: Bilateral Relations Ontology

### Requirement C.1: CAMEO / GDELT Event Taxonomy

**Status**: ✅ Complete

**Implementation**:
- Mapping of bilateral event types to CAMEO categories
- GDELT category annotations
- Supported event types:
  - DiplomaticMeeting → CAMEO "04 Consult"
  - TradeAgreement → CAMEO "07 Provide Aid"
  - InvestmentProject → CAMEO "08 Yield"
  - TechnologyCooperation → CAMEO "05 Engage in Diplomatic Cooperation"
  - InfrastructureProject → CAMEO "07 Provide Aid"
  - EducationCooperation → CAMEO "05 Engage in Diplomatic Cooperation"
  - SecurityStatement → CAMEO "13 Threaten"
  - SanctionOrRestriction → CAMEO "11 Sanctions"
  - CompanyActivity → CAMEO "07 Provide Aid"
  - CulturalExchange → CAMEO "05 Engage in Diplomatic Cooperation"
  - PolicyStatement → CAMEO "01 Public Statement"

**Files**:
- `src/ontology/taxonomy.py`
- `src/extraction/event_extractor.py` (uses taxonomy)

### Requirement C.2: IPTC Media Topics Classification

**Status**: ✅ Complete

**Implementation**:
- Each event annotated with IPTC topic
- Examples:
  - DiplomaticMeeting → "Politics/Diplomacy"
  - TradeAgreement → "Economy, Business and Finance/Trade"
  - InvestmentProject → "Economy, Business and Finance/Investment"
  - TechnologyCooperation → "Science and Technology/Research"
  - EducationCooperation → "Education"
  - SecurityStatement → "Crime, Law and Justice/Defence"

**Files**:
- `src/ontology/taxonomy.py` (EventTaxonomy dataclass)

### Requirement C.3: W3C OWL-Time Temporal Validity

**Status**: ✅ Complete

**Implementation**:
- Start and end date tracking for all events
- Granularity specification (day, month, year)
- Duration support (ISO 8601 periods, e.g., "P3M")
- Interval representation: `{"start": "2020-01-01", "end": "2026-12-31"}`
- Temporal anchoring to document creation time

**Files**:
- `src/graph/graph_loader.py` (lines 313-362: `_time_bounds`, `_expand_date`)
- `src/temporal/date_normaliser.py`

### Requirement C.4: EventKG-style Event-Centric Temporal KG

**Status**: ✅ Complete

**Implementation**:
- Event-centric graph model
- Event representation includes:
  - **Who**: Participant entities (PERSON, ORGANIZATION)
  - **What**: Event type and trigger words
  - **When**: Temporal expressions and validity intervals
  - **Where**: Location entities (LOCATION, COUNTRY)
- Provenance tracking: Every event linked to source article
- Event signatures for deduplication and corroboration

**Files**:
- `src/extraction/event_extractor.py`
- `src/graph/graph_loader.py`
- `src/extraction/pipeline_utils.py` (event signatures)

## Section D: Competency Questions

All competency questions from the requirements paper are implemented with dedicated query methods.

### Question 1: How did China–Romania economic relations evolve from 2020 to 2026?

**Status**: ✅ Complete

**Implementation**:
```python
CompetencyQueries.china_romania_economic_evolution(
    start_date="2020-01-01",
    end_date="2026-12-31"
)
```

Returns:
- Timeline of economic events by month
- Event breakdown by type (TradeAgreement, InvestmentProject, etc.)
- Key entities (organizations) involved
- Total event count

**Files**:
- `src/graph/competency_queries.py` (lines 33-168)

### Question 2: Which Romanian institutions were most often connected to Chinese companies in news streams?

**Status**: ✅ Complete

**Implementation**:
```python
CompetencyQueries.romanian_institutions_connected_to_chinese_companies(
    limit=20,
    start_date=None,
    end_date=None
)
```

Returns:
- Romanian institutions ranked by connection frequency
- Chinese companies they're connected to
- Event types of connections
- Timeline of connections

**Files**:
- `src/graph/competency_queries.py` (lines 170-235)

### Question 3: Which China–Romania trade, diplomatic, cultural, or policy events were reported in a given period?

**Status**: ✅ Complete

**Implementation**:
```python
CompetencyQueries.bilateral_events_in_period(
    start_date="2024-01-01",
    end_date="2024-12-31",
    event_categories=["trade", "diplomatic", "cultural", "policy"]
)
```

Returns:
- All bilateral events in period
- Events grouped by type
- Entity participants
- Source article metadata

**Files**:
- `src/graph/competency_queries.py` (lines 237-341)

### Question 4: Which claims later became contradicted or unverified? Which sources systematically produce low-credibility bilateral narratives?

**Status**: ✅ Complete

**Implementation**:
```python
CompetencyQueries.contradicted_or_unverified_claims(
    credibility_threshold=0.5
)
```

Returns:
- Unverified claims (single-source only)
- Multi-source events (potential contradictions)
- Source activity metrics
- Credibility analysis

**Files**:
- `src/graph/competency_queries.py` (lines 343-425)

### Question 5: Which collaborative research has been conducted with authors from China and Romania?

**Status**: ✅ Complete

**Implementation**:
```python
CompetencyQueries.collaborative_research_authors(limit=50)
```

Returns:
- TechnologyCooperation and EducationCooperation events
- Researchers and institutions involved
- Timeline of collaborations

**Files**:
- `src/graph/competency_queries.py` (lines 427-478)

## Fake News Detection Layer

### Provenance Tracking

**Status**: ✅ Complete

**Implementation**:
- Every claim linked to source article with URL, timestamp, domain
- Source credibility scoring based on known reliable domains
- Transparency in claim origins

**Files**:
- `src/credibility/scorer.py`
- `src/graph/graph_loader.py` (Claim nodes with provenance)

### Cross-Source Corroboration

**Status**: ✅ Complete

**Implementation**:
- Event signature matching across articles
- Source diversity counting
- Identification of:
  - Single-source unverified claims
  - Multi-source corroborated events
  - Contradictory reports

**Files**:
- `src/credibility/corroboration.py`
- `scripts/run_corroboration_analysis.py`

### Graph Consistency Checks

**Status**: ✅ Complete

**Implementation**:
- Temporal inconsistency detection (impossible timelines)
- Event contradiction identification
- Entity co-occurrence analysis

**Files**:
- `src/temporal/reasoner.py`
- `src/credibility/fake_news.py`

### Verification Status Labels

**Status**: ✅ Complete

**Implementation**:
- `corroborated`: ≥2 sources, ≥2 domains, credibility ≥0.6
- `unverified`: Single source or single domain
- `contested`: Contradictory reports or temporal inconsistencies

**Files**:
- `src/credibility/fake_news.py` (ClaimVerifier.assess)

## Additional Features

### Multilingual Support
- Language detection for all articles
- Translation pipeline (configurable)
- Support for Romanian, Chinese, and English

**Files**:
- `src/ingestion/language_detector.py`
- `src/ingestion/translator.py`

### Relevance Filtering
- Ensures articles mention both China and Romania
- Configurable modes: strict, feed_aware, either
- Extensive keyword lists for both countries

**Files**:
- `src/ingestion/relevance_filter.py`
- `config/settings.yaml` (relevance section)

### Deduplication
- URL-based and content-based deduplication
- Prevents processing duplicate articles

**Files**:
- `src/ingestion/deduplicator.py`

## Running the Complete Pipeline

1. **Initialize project**:
   ```bash
   python scripts/init_project.py
   ```

2. **Fetch and process articles**:
   ```bash
   python -m src.ingestion.pipeline
   ```

3. **Extract entities**:
   ```bash
   python scripts/run_entity_extraction.py
   ```

4. **Extract temporal expressions**:
   ```bash
   python scripts/run_temporal_extraction.py
   ```

5. **Extract events**:
   ```bash
   python scripts/run_event_extraction.py
   ```

6. **Load to Neo4j**:
   ```bash
   python scripts/load_to_neo4j.py
   ```

7. **Run competency queries**:
   ```bash
   python scripts/run_competency_queries.py
   ```

8. **Analyze credibility**:
   ```bash
   python scripts/run_fake_news_analysis.py
   ```

## References

1. **Requirements Paper**: "Building and maintaining a temporal knowledge graph for news streams on China-Romania"
2. **CAMEO Taxonomy**: Conflict and Mediation Event Observations event coding scheme
3. **GDELT Project**: Global Database of Events, Language, and Tone (https://www.gdeltproject.org/)
4. **IPTC Media Topics**: International Press Telecommunications Council topic taxonomy
5. **W3C OWL-Time**: Time Ontology in OWL (https://www.w3.org/TR/owl-time/)
6. **EventKG**: Event-centric temporal knowledge graph reference
7. **DeepKE**: Deep learning-based knowledge extraction toolkit
8. **HeidelTime**: Temporal tagger for TIMEX3 extraction

## Summary

This implementation provides **complete coverage** of all requirements specified in the paper:

✅ RSS feed integration (Section A)
✅ DeepKE entity/relation extraction (Section B.1)
✅ HeidelTime TIMEX3 temporal extraction (Section B.2)
✅ Neo4j graph database with Python driver (Section B.3)
✅ neo4j-viz visualization support (Section B.4)
✅ Temporal KG reasoning (Section B.5)
✅ CAMEO/GDELT event taxonomy (Section C.1)
✅ IPTC Media Topics classification (Section C.2)
✅ W3C OWL-Time temporal validity (Section C.3)
✅ EventKG-style event-centric model (Section C.4)
✅ All 5 competency questions (Section D)
✅ Fake news detection layer (provenance, corroboration, consistency)

The system is production-ready for research on China-Romania bilateral relations using temporal knowledge graphs.
