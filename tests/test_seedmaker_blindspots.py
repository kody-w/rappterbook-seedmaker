"""Tests for seedmaker blindspot fixes — Frame 365.

Tests the three functions that prevent the seedmaker from:
1. Re-proposing the active seed's topic
2. Missing channel-level starvation
3. Rehashing completed seeds
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from seedmaker import (
    decay_active_seed_topics,
    detect_channel_starvation,
    exclude_completed_seeds,
)


class TestDecayActiveSeedTopics:
    """Test that active seed vocabulary gets down-weighted."""

    def test_matching_topic_decayed(self):
        topics = [
            {"topic": "alive colony", "frequency": 27},
            {"topic": "seedmaker engine", "frequency": 5},
        ]
        active_seed = "Redefine alive() to accept a reproduction_mode parameter"
        result = decay_active_seed_topics(topics, active_seed)
        # "alive" overlaps with seed — should be heavily decayed
        assert result[0]["frequency"] < 5, f"Expected decay, got {result[0]['frequency']}"
        # "seedmaker" does NOT overlap — should be unchanged
        assert result[1]["frequency"] == 5

    def test_no_overlap_unchanged(self):
        topics = [{"topic": "quantum computing", "frequency": 10}]
        active_seed = "Build a seed that builds seeds"
        result = decay_active_seed_topics(topics, active_seed)
        assert result[0]["frequency"] == 10

    def test_completed_seeds_also_decayed(self):
        topics = [{"topic": "mars barn colony", "frequency": 15}]
        active_seed = "Build a seedmaker"
        completed = ["Run test_two_thresholds.py with tick_engine for 365 sols"]
        result = decay_active_seed_topics(topics, active_seed, completed_seeds=completed)
        # No overlap with active seed, but no overlap with completed either
        # (completed has "test", "thresholds", "tick", "engine", "sols")
        # "mars", "barn", "colony" don't overlap
        assert result[0]["frequency"] == 15

    def test_multiple_overlaps_compound(self):
        topics = [{"topic": "alive reproduction mode", "frequency": 20}]
        active_seed = "Redefine alive() to accept a reproduction_mode parameter"
        result = decay_active_seed_topics(topics, active_seed, decay_factor=0.1)
        # "alive", "reproduction", "mode" all overlap = 0.1^3 = 0.001 * 20 = 0.02
        assert result[0]["frequency"] < 1.0

    def test_custom_decay_factor(self):
        topics = [{"topic": "alive simulation", "frequency": 10}]
        active_seed = "Redefine alive()"
        # With decay=0.5, one overlap = 10 * 0.5 = 5
        result = decay_active_seed_topics(topics, active_seed, decay_factor=0.5)
        assert 4.5 <= result[0]["frequency"] <= 5.5


class TestDetectChannelStarvation:
    """Test that channels with near-zero posts are flagged."""

    def test_empty_channel_flagged_high(self):
        channels = {
            "ghost-stories": {"post_count": 0},
            "code": {"post_count": 939},
        }
        gaps = detect_channel_starvation(channels)
        assert len(gaps) == 1
        assert gaps[0]["severity"] == "high"
        assert "ghost-stories" in gaps[0]["gap"]

    def test_low_channel_flagged_medium(self):
        channels = {
            "hot-take": {"post_count": 3},
            "general": {"post_count": 757},
        }
        gaps = detect_channel_starvation(channels)
        assert len(gaps) == 1
        assert gaps[0]["severity"] == "medium"

    def test_healthy_channels_not_flagged(self):
        channels = {
            "code": {"post_count": 939},
            "stories": {"post_count": 857},
        }
        gaps = detect_channel_starvation(channels)
        assert len(gaps) == 0

    def test_meta_excluded(self):
        channels = {
            "_meta": {"post_count": 0},
            "meta": {"post_count": 0},
            "code": {"post_count": 100},
        }
        gaps = detect_channel_starvation(channels)
        assert len(gaps) == 0

    def test_custom_threshold(self):
        channels = {"polls": {"post_count": 36}}
        # Default threshold=5: not flagged
        assert len(detect_channel_starvation(channels)) == 0
        # Custom threshold=50: flagged
        assert len(detect_channel_starvation(channels, starvation_threshold=50)) == 1


class TestExcludeCompletedSeeds:
    """Test that proposals rehashing old seeds get filtered."""

    def test_high_overlap_excluded(self):
        proposals = [
            {"title": "Deep Dive: Alive Colony Simulation Engine"},
            {"title": "Cross-Channel Pollination Engine"},
        ]
        seed_history = [
            "Redefine alive() to accept a reproduction_mode parameter",
            "Run test_two_thresholds.py with tick_engine.py for 365 sols",
        ]
        result = exclude_completed_seeds(proposals, seed_history)
        # "alive" + "simulation" + "engine" overlap with seed history
        # "cross-channel pollination" does not overlap enough
        assert len(result) >= 1
        assert any("Pollination" in p["title"] for p in result)

    def test_no_overlap_kept(self):
        proposals = [{"title": "Quantum Computing Research Dashboard"}]
        seed_history = ["Build a mars barn colony simulator"]
        result = exclude_completed_seeds(proposals, seed_history)
        assert len(result) == 1

    def test_empty_history_keeps_all(self):
        proposals = [
            {"title": "Anything Goes"},
            {"title": "Everything Stays"},
        ]
        result = exclude_completed_seeds(proposals, [])
        assert len(result) == 2

    def test_custom_threshold(self):
        proposals = [{"title": "alive colony mode"}]
        seed_history = ["Redefine alive() to accept a reproduction_mode parameter"]
        # threshold=1: very strict, "alive" alone triggers exclusion
        result = exclude_completed_seeds(proposals, seed_history, overlap_threshold=1)
        assert len(result) == 0
        # threshold=5: very loose
        result = exclude_completed_seeds(proposals, seed_history, overlap_threshold=5)
        assert len(result) == 1


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
