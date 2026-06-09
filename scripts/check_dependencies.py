#!/usr/bin/env python3
"""System dependency checker for Ch-RO Temporal Knowledge Graph.

Checks if all required system dependencies are installed:
- Java JDK (for py-heideltime)
- Perl (for py-heideltime)
- Python packages
"""

import shutil
import subprocess
import sys
from pathlib import Path


def check_command(command: str, name: str, min_version: str = None) -> bool:
    """Check if a command exists and optionally check version."""
    if shutil.which(command):
        try:
            result = subprocess.run(
                [command, "--version"] if command != "perl" else [command, "-v"],
                capture_output=True,
                text=True,
                timeout=5
            )
            version_output = result.stdout + result.stderr
            print(f"  ✓ {name} found: {version_output.split()[0] if version_output else 'installed'}")
            return True
        except (subprocess.TimeoutExpired, Exception) as e:
            print(f"  ✓ {name} found (version check failed: {e})")
            return True
    else:
        print(f"  ✗ {name} NOT FOUND")
        return False


def check_python_package(package: str, import_name: str = None) -> bool:
    """Check if a Python package is installed."""
    if import_name is None:
        import_name = package.replace("-", "_")

    try:
        __import__(import_name)
        print(f"  ✓ {package} installed")
        return True
    except ImportError:
        print(f"  ✗ {package} NOT INSTALLED")
        return False


def main():
    print("=" * 60)
    print("Ch-RO Temporal KG - System Dependency Check")
    print("=" * 60)
    print()

    all_ok = True

    # Check Python version
    print("1. Python Version:")
    python_version = sys.version_info
    if python_version >= (3, 11):
        print(f"  ✓ Python {python_version.major}.{python_version.minor}.{python_version.micro}")
    else:
        print(f"  ✗ Python {python_version.major}.{python_version.minor}.{python_version.micro} (requires 3.11+)")
        all_ok = False
    print()

    # Check Java (required for py-heideltime)
    print("2. Java JDK (required for py-heideltime):")
    java_ok = check_command("java", "Java JDK")
    if not java_ok:
        print()
        print("  Install instructions:")
        print("    Ubuntu/Debian: sudo apt install default-jdk")
        print("    macOS:         brew install openjdk")
        print("    Windows:       https://www.oracle.com/java/technologies/downloads/")
        all_ok = False
    print()

    # Check Perl (required for py-heideltime)
    print("3. Perl (required for py-heideltime):")
    perl_ok = check_command("perl", "Perl")
    if not perl_ok:
        print()
        print("  Install instructions:")
        print("    Linux/macOS:   Usually pre-installed")
        print("    Windows:       https://strawberryperl.com/")
        all_ok = False
    print()

    # Check key Python packages
    print("4. Key Python Packages:")
    packages_to_check = [
        ("py-heideltime", "py_heideltime"),
        ("deepke", "deepke"),
        ("spacy", "spacy"),
        ("neo4j", "neo4j"),
        ("pandas", "pandas"),
        ("requests", "requests"),
    ]

    for package, import_name in packages_to_check:
        pkg_ok = check_python_package(package, import_name)
        if not pkg_ok:
            all_ok = False

    if not all_ok:
        print()
        print("  Missing packages can be installed with:")
        print("    conda env update -f environment.yml")
        print("    or")
        print("    pip install py-heideltime deepke spacy neo4j pandas requests")
    print()

    # Check spaCy language model
    print("5. spaCy Language Model:")
    try:
        import spacy
        try:
            nlp = spacy.load("en_core_web_sm")
            print("  ✓ en_core_web_sm loaded")
        except OSError:
            print("  ✗ en_core_web_sm NOT FOUND")
            print()
            print("  Install with:")
            print("    python -m spacy download en_core_web_sm")
            all_ok = False
    except ImportError:
        print("  ✗ spaCy not installed")
        all_ok = False
    print()

    # Check project structure
    print("6. Project Structure:")
    required_dirs = ["data", "logs", "config"]
    for dir_name in required_dirs:
        dir_path = Path(dir_name)
        if dir_path.exists():
            print(f"  ✓ {dir_name}/ exists")
        else:
            print(f"  ✗ {dir_name}/ missing")
            all_ok = False

    if not all_ok:
        print()
        print("  Initialize project structure with:")
        print("    python scripts/init_project.py")
    print()

    # Final summary
    print("=" * 60)
    if all_ok:
        print("✓ All dependencies satisfied!")
        print()
        print("You're ready to run the temporal knowledge graph pipeline.")
        print()
        print("Quick start:")
        print("  python -m src.ingestion.pipeline")
        print("  python scripts/run_entity_extraction.py")
        print("  python scripts/run_temporal_extraction.py --engine heideltime")
        return 0
    else:
        print("✗ Some dependencies are missing or incorrect.")
        print()
        print("Please install missing dependencies and run this check again.")
        print()
        print("For detailed installation instructions, see:")
        print("  docs/INSTALLATION.md")
        return 1


if __name__ == "__main__":
    sys.exit(main())
