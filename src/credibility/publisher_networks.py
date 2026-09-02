# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

"""
temporal_kg.src.credibility.publisher_networks
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Maps a raw domain to a shared publisher/institution identifier, so
corroboration's source_diversity counts independent newsrooms rather than
independent *websites*.

Confirmed as a real overcount on real ingested data (2026-08-24): a single
Xinhua/People's Daily wire story about a CPC official's Romania visit
showed source_diversity=8 across domains including arabic.news.cn,
french.xinhuanet.com, and spanish.peopledaily.com.cn -- eight regional/
language mirrors of two institutions (Xinhua, People's Daily), not eight
independently-reporting outlets. Counting raw domains treats "the same
story republished across a wire service's language editions" identically
to "eight different newsrooms independently verified this," which
overstates corroboration strength specifically for large state media
networks that publish the same wire copy across many domains.

Domains not matched to a configured network resolve to themselves --
unmatched, ordinary domains are unaffected (each remains its own network of
one), so this only ever *reduces* diversity for known multi-domain
networks, never inflates or fabricates it elsewhere.
"""

from __future__ import annotations

from src.utils.config import settings


def _load_networks() -> dict[str, list[str]]:
    return settings("credibility.publisher_networks", {})


def resolve_publisher(domain: str | None) -> str | None:
    """Return the shared publisher identifier for *domain*, or *domain*
    itself unchanged if it doesn't match any configured network."""
    if not domain:
        return domain
    for network_name, domain_suffixes in _load_networks().items():
        for suffix in domain_suffixes:
            if domain == suffix or domain.endswith("." + suffix):
                return network_name
    return domain
