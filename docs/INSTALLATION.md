<!--
Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
Provided as-is, without warranty.
If this code contributes to a paper or publication, please credit the authors above.
-->

# Installation Guide

This guide covers the complete setup for the Ch-RO Temporal Knowledge Graph project.

## Prerequisites

### Required System Dependencies

1. **Python 3.11+**
   - Download from [python.org](https://www.python.org/downloads/) or use conda

2. **Java JDK** (for HeidelTime temporal extraction)
   - **Ubuntu/Debian:**
     ```bash
     sudo apt update
     sudo apt install default-jdk
     ```
   - **macOS:**
     ```bash
     brew install openjdk
     ```
   - **Windows:**
     Download from [Oracle JDK](https://www.oracle.com/java/technologies/downloads/)

3. **Perl** (for HeidelTime temporal extraction)
   - **Linux/macOS:** Usually pre-installed
   - **Windows:** Download [Strawberry Perl](https://strawberryperl.com/)

4. **Conda** (Miniconda or Anaconda)
   - Download from [Miniconda](https://docs.conda.io/en/latest/miniconda.html)

## Quick Setup (Recommended)

Use the automated setup script:

```bash
# Clone the repository
git clone https://github.com/andreeaonaci/Ch-RO.git
cd Ch-RO

# Run the setup script
bash scripts/setup.sh
```

This script will:
1. Create the conda environment with all dependencies
2. Install Python packages (py-heideltime, deepke, etc.)
3. Download the spaCy language model
4. Check for system dependencies
5. Initialize project directories

## Manual Setup

If you prefer to set up manually:

### 1. Create Conda Environment

```bash
conda env create -f environment.yml
conda activate temporal_kg
```

### 2. Install spaCy Language Model

```bash
python -m spacy download en_core_web_sm
```

### 3. Verify Dependencies

```bash
# Check Java
java -version

# Check Perl
perl -v

# Test py-heideltime
python -c "from py_heideltime import heideltime; print('py-heideltime OK')"
```

### 4. Initialize Project

```bash
python scripts/init_project.py
```

## Python Dependencies

All Python dependencies are managed through `environment.yml`:

### Core Dependencies
- **pandas, numpy**: Data manipulation
- **spacy, nltk**: NLP processing
- **neo4j**: Graph database driver
- **requests, httpx, beautifulsoup4**: Article downloading and HTML cleaning

### Key Packages

#### py-heideltime (Temporal Extraction)
- **Package:** `py-heideltime>=1.0.6`
- **Purpose:** Python wrapper for HeidelTime temporal tagger
- **Requirements:** Java JDK, Perl
- **Documentation:** [GitHub](https://github.com/hmosousa/py_heideltime)

#### DeepKE (Knowledge Extraction)
- **Package:** `deepke`
- **Purpose:** Deep learning-based knowledge extraction (entities, relations)
- **Documentation:** [GitHub](https://github.com/zjunlp/deepke)

#### Other Key Packages
- `deep-translator`: Multilingual translation
- `langdetect`: Language detection
- `python-dateutil`: Date parsing
- `tenacity`: Retry logic
- `pyyaml`: Configuration management

## Configuration

### 1. Neo4j Database (Optional but Recommended)

Install Neo4j for graph storage and queries:

```bash
# Using Docker (easiest)
docker run -d \
  --name neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/password \
  neo4j:latest

# Or download from https://neo4j.com/download/
```

Update `config/settings.yaml`:
```yaml
database:
  neo4j_uri: "bolt://localhost:7687"
  neo4j_user: "neo4j"
  neo4j_password: "password"
```

### 2. Configure GDELT Ingestion

Edit `config/settings.yaml`:

```yaml
gdelt:
  query: "China Romania"
  max_records: 250
  default_timespan: "1week"
  default_credibility: 0.7
```

### 3. Configure Temporal Extraction

Edit `config/settings.yaml`:

```yaml
temporal:
  engine: "heideltime"  # Use py-heideltime
  heideltime:
    enabled: true
    language: "en"
    document_type: "news"
```

### 4. Configure DeepKE (Optional)

```yaml
extraction:
  use_deepke: true
  deepke:
    enabled: true
    command_template: "python ../../scripts/deepke_runner.py --input {input} --output {output}"
    conda_env: "deepke_py38"
    working_dir: "tools/deepke"
    output_dir: "data/exports/deepke"
    timeout_seconds: 600
```

## Troubleshooting

### py-heideltime Issues

**Error: "Java not found"**
```bash
# Verify Java installation
java -version

# Linux: Set JAVA_HOME
export JAVA_HOME=/usr/lib/jvm/default-java
```

**Error: "Perl not found"**
```bash
# Verify Perl installation
perl -v

# On Windows, ensure Perl is in PATH
```

**Error: "HeidelTime resources not found"**
- py-heideltime downloads resources automatically on first use
- If issues persist, check network connection

### DeepKE Issues

**Error: "deepke module not found"**
```bash
# Reinstall with pip
pip install deepke --upgrade
```

**CUDA/GPU Issues**
```bash
# For CPU-only installation
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### General Issues

**Environment activation fails**
```bash
# Recreate environment
conda env remove -n temporal_kg
conda env create -f environment.yml
```

**Import errors**
```bash
# Ensure you're in the project root and environment is activated
conda activate temporal_kg
export PYTHONPATH="${PYTHONPATH}:$(pwd)"
```

## Verifying Installation

Run the test suite to verify everything is set up correctly:

```bash
# Run unit tests
pytest tests/unit/

# Run integration tests (requires Neo4j)
pytest tests/integration/

# Quick functional test
python -c "
from src.temporal.heideltime_client import HeidelTimeClient
from src.extraction.entity_extractor import EntityExtractor

print('✓ HeidelTime client loaded')
print('✓ Entity extractor loaded')
print('Installation verified!')
"

# Test GDELT ingestion (dry-run, no DB writes)
python scripts/run_ingestion.py --dry-run
```

## Next Steps

After installation, see the main [README.md](../README.md) for:
- Quick start guide
- Running the pipeline
- Competency queries
- Requirements paper alignment

## Development Setup

For development with additional tools:

```bash
# Install dev dependencies
pip install -r requirements-extended.txt

# Install pre-commit hooks (if available)
pre-commit install

# Run linters
black src/ tests/
isort src/ tests/
flake8 src/ tests/
```

## Docker Setup (Alternative)

A Docker setup is available for containerized deployment:

```bash
# Build container
docker build -t ch-ro-kg .

# Run with docker-compose
docker-compose up -d
```

See `docker/` directory for details.

## Support

For issues or questions:
- Check [GitHub Issues](https://github.com/andreeaonaci/Ch-RO/issues)
- Review [Requirements Mapping](docs/REQUIREMENTS_MAPPING.md)
- See [README](../README.md) for usage examples
