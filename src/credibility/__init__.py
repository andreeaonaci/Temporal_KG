# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""Credibility and corroboration helpers.

No eager re-exports here: src.credibility.corroboration depends on
src.temporal.lifecycle, which depends on src.credibility.contradiction_nli
-- importing anything from src.credibility.contradiction_nli always runs
this __init__.py first (Python package semantics), so eagerly importing
CorroborationAnalyzer here creates a real circular import the moment
lifecycle.py is imported before corroboration.py. Nothing in the codebase
uses the package-level re-export (everyone imports the submodule directly,
e.g. ``from src.credibility.corroboration import CorroborationAnalyzer``),
so there's no cost to leaving it out.
"""
