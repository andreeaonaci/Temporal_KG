# PlantUML Pipeline Diagrams

This folder contains a full PlantUML documentation set for the project pipeline.

## Top-level

- `01_top_level_pipeline.puml`: end-to-end orchestrator flow from ingestion to exports, optional Neo4j load, and competency queries.
- `11_seq_top_level_pipeline.puml`: top-level sequence interactions for `run_full_pipeline.py`.

## Module diagrams

- `02_module_ingestion.puml`: GDELT acquisition, GDELT-text normalization, language handling, relevance filtering, and persistence.
- `03_module_extraction.puml`: entity, temporal, event, relation extraction, with optional DeepKE path.
- `04_module_temporal.puml`: temporal extraction engines and reasoning checks.
- `05_module_ontology.puml`: bilateral event typing and semantic alignment using taxonomy.
- `06_module_credibility.puml`: corroboration, claim verification, contradiction/fake-news export.
- `07_module_graph_queries.puml`: Neo4j loading and competency query execution.
- `08_module_evaluation_reporting.puml`: metrics and reporting pipeline modules.

## Sequence diagrams

- `12_seq_module_ingestion.puml`: step-by-step GDELT-only ingestion interaction timeline.
- `13_seq_module_extraction.puml`: extraction-stage sequence timeline across layers.
- `14_seq_module_temporal.puml`: temporal engine selection and reasoning timeline.
- `15_seq_module_ontology.puml`: taxonomy alignment and consumer access sequence.
- `16_seq_module_credibility.puml`: corroboration and fake-news labeling sequence.
- `17_seq_module_graph_queries.puml`: graph load and competency query sequence.
- `18_seq_module_evaluation_reporting.puml`: evaluation and reporting sequence.

## Render examples

If PlantUML is installed locally:

```bash
plantuml docs/plantuml/01_top_level_pipeline.puml
plantuml docs/plantuml/*.puml
```