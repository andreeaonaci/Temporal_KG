# Copyright (c) 2026 Macarie Mihaela-Ancau, Onaci Andreea-Maria, Paul Petrut-Betuel.
# Provided as-is, without warranty.
# If this code contributes to a paper or publication, please credit the authors above.

from __future__ import annotations

from src.credibility.publisher_networks import resolve_publisher


def test_xinhua_mirrors_resolve_to_the_same_network():
    assert resolve_publisher("xinhuanet.com") == "xinhua"
    assert resolve_publisher("french.xinhuanet.com") == "xinhua"
    assert resolve_publisher("news.cn") == "xinhua"
    assert resolve_publisher("arabic.news.cn") == "xinhua"


def test_peoples_daily_mirrors_resolve_to_the_same_network():
    assert resolve_publisher("people.com.cn") == "peoples_daily"
    assert resolve_publisher("french.people.com.cn") == "peoples_daily"
    assert resolve_publisher("arabic.peopledaily.com.cn") == "peoples_daily"


def test_cgtn_mirrors_resolve_to_the_same_network():
    assert resolve_publisher("cgtn.com") == "cgtn"
    assert resolve_publisher("radio.cgtn.com") == "cgtn"


def test_unmatched_domain_resolves_to_itself():
    assert resolve_publisher("romania-insider.com") == "romania-insider.com"
    assert resolve_publisher("qianlong.com") == "qianlong.com"


def test_similar_but_unrelated_domain_is_not_falsely_merged():
    # "news.cn" is a real Xinhua short-URL brand; a domain that merely
    # contains "news" should not accidentally match via a loose substring check.
    assert resolve_publisher("somenewsagency.com") != "xinhua"


def test_none_and_empty_domain_pass_through_unchanged():
    assert resolve_publisher(None) is None
    assert resolve_publisher("") == ""
