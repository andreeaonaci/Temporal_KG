#!/bin/bash
# Setup script for Ch-RO Temporal Knowledge Graph project
# This script installs all necessary dependencies and sets up the environment

set -e  # Exit on error

echo "========================================="
echo "Ch-RO Temporal KG - Setup Script"
echo "========================================="
echo ""

# Check if conda is available
if ! command -v conda &> /dev/null; then
    echo "ERROR: Conda is not installed or not in PATH"
    echo "Please install Miniconda or Anaconda first:"
    echo "  https://docs.conda.io/en/latest/miniconda.html"
    exit 1
fi

echo "Step 1: Creating/updating conda environment from environment.yml..."
conda env create -f environment.yml --force || conda env update -f environment.yml --prune

echo ""
echo "Step 2: Activating environment..."
eval "$(conda shell.bash hook)"
conda activate temporal_kg

echo ""
echo "Step 3: Installing spaCy language model..."
python -m spacy download en_core_web_sm

echo ""
echo "Step 4: Checking system dependencies for HeidelTime..."
echo "  Checking for Java JDK..."
if command -v java &> /dev/null; then
    JAVA_VERSION=$(java -version 2>&1 | head -n 1)
    echo "    ✓ Java found: $JAVA_VERSION"
else
    echo "    ✗ Java JDK not found!"
    echo ""
    echo "    HeidelTime (py-heideltime) requires Java JDK."
    echo "    Install instructions:"
    echo ""
    echo "    Ubuntu/Debian:"
    echo "      sudo apt update"
    echo "      sudo apt install default-jdk"
    echo ""
    echo "    macOS:"
    echo "      brew install openjdk"
    echo ""
    echo "    Windows:"
    echo "      Download from: https://www.oracle.com/java/technologies/downloads/"
    echo ""
fi

echo "  Checking for Perl..."
if command -v perl &> /dev/null; then
    PERL_VERSION=$(perl -v | grep -oP 'v\d+\.\d+\.\d+' | head -1)
    echo "    ✓ Perl found: $PERL_VERSION"
else
    echo "    ✗ Perl not found!"
    echo ""
    echo "    HeidelTime (py-heideltime) requires Perl."
    echo "    Install instructions:"
    echo ""
    echo "    Ubuntu/Debian:"
    echo "      Perl is usually pre-installed"
    echo ""
    echo "    macOS:"
    echo "      Perl is usually pre-installed"
    echo ""
    echo "    Windows:"
    echo "      Download Strawberry Perl: https://strawberryperl.com/"
    echo ""
fi

echo ""
echo "Step 5: Setting up project directories..."
python scripts/init_project.py

echo ""
echo "Step 6: Running dependency check..."
python scripts/check_dependencies.py || echo "Some dependencies missing - see above for details"

echo ""
echo "Step 7 (optional): DeepKE manual setup"
echo "  DeepKE is not installed from PyPI in environment.yml because that package"
echo "  can fail to build in this environment."
echo "  If you need DeepKE, install it manually:"
echo "    git clone https://github.com/zjunlp/DeepKE.git tools/deepke"
echo "    pip install -r tools/deepke/requirements.txt"
echo "  Then enable it in config/settings.yaml (extraction.deepke.enabled: true)."

echo ""
echo "========================================="
echo "Setup Complete!"
echo "========================================="
echo ""
echo "To activate the environment, run:"
echo "  conda activate temporal_kg"
echo ""
echo "Quick start commands:"
echo "  # Fetch and process news articles"
echo "  python -m src.ingestion.pipeline"
echo ""
echo "  # Extract entities"
echo "  python scripts/run_entity_extraction.py"
echo ""
echo "  # Extract temporal expressions (using py-heideltime)"
echo "  python scripts/run_temporal_extraction.py --engine heideltime"
echo ""
echo "  # Extract events"
echo "  python scripts/run_event_extraction.py"
echo ""
echo "  # Load to Neo4j"
echo "  python scripts/load_graph.py"
echo ""
echo "  # Run competency queries"
echo "  python scripts/run_competency_queries.py"
echo ""
echo "For more information, see README.md"
echo ""
