"""Pure-math tests for episode retrieval scoring — no external deps."""

import math

import pytest

from samantha.memory import score_episode


def test_score_high_similarity_recent():
    # High similarity, just happened (0 days), mid importance
    s = score_episode(similarity=0.9, days_since=0, importance=0.5)
    recency = math.exp(0)  # = 1.0
    expected = 0.5 * 0.9 + 0.3 * recency + 0.2 * 0.5
    assert abs(s - expected) < 1e-6


def test_score_old_memory_decays():
    recent = score_episode(similarity=0.8, days_since=1, importance=0.5)
    old = score_episode(similarity=0.8, days_since=90, importance=0.5)
    assert recent > old


def test_score_importance_matters():
    low = score_episode(similarity=0.7, days_since=10, importance=0.1)
    high = score_episode(similarity=0.7, days_since=10, importance=0.9)
    assert high > low


def test_threshold_boundary():
    # Score right at and just below threshold
    s_above = score_episode(similarity=0.8, days_since=0, importance=0.0)
    assert s_above >= 0.4
    # Very old, low everything → below threshold
    s_below = score_episode(similarity=0.1, days_since=365, importance=0.1)
    assert s_below < 0.4


def test_score_bounds():
    # Maximum possible: sim=1, days=0, importance=1
    s_max = score_episode(1.0, 0.0, 1.0)
    assert s_max <= 1.0 + 1e-9
    # Minimum: all zeros
    s_min = score_episode(0.0, 10000.0, 0.0)
    assert s_min >= 0.0


@pytest.mark.parametrize(
    "similarity,days,importance,expected_min",
    [
        (0.9, 0, 0.8, 0.7),  # very fresh, high sim+importance
        (0.5, 30, 0.5, 0.3),  # month old, middling
        (0.2, 180, 0.1, 0.0),  # old and weak
    ],
)
def test_score_parametrized(similarity, days, importance, expected_min):
    s = score_episode(similarity, days, importance)
    assert s >= expected_min
