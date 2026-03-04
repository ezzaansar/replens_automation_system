"""
Tests for src/models/discovery_model.py

Covers:
- DiscoveryModel.predict() with various feature combinations
- Scoring weights produce expected relative ordering
- Edge cases: missing features, all zeros, extreme values, negative values
- Weight sum verification
- Clamping behavior (output always 0.0 to 1.0)
"""

import pytest

from src.models.discovery_model import DiscoveryModel


@pytest.fixture
def model():
    """Create a fresh DiscoveryModel instance."""
    return DiscoveryModel()


# ============================================================================
# Basic functionality
# ============================================================================
class TestDiscoveryModelBasic:
    """Tests for basic DiscoveryModel.predict() functionality."""

    def test_all_ones_gives_max_score(self, model):
        """All features at 1.0 should give a score of 1.0 (sum of all weights)."""
        features = [1.0, 1.0, 1.0, 1.0, 1.0, 1.0]
        score = model.predict(features)
        assert score == pytest.approx(1.0)

    def test_all_zeros_gives_zero_score(self, model):
        """All features at 0.0 should give a score of 0.0."""
        features = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        score = model.predict(features)
        assert score == pytest.approx(0.0)

    def test_half_values(self, model):
        """All features at 0.5 should give half the max score."""
        features = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        score = model.predict(features)
        assert score == pytest.approx(0.5)

    def test_score_is_float(self, model):
        features = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        score = model.predict(features)
        assert isinstance(score, float)


# ============================================================================
# Weight verification
# ============================================================================
class TestDiscoveryModelWeights:
    """Tests verifying the model's weight configuration."""

    def test_weights_sum_to_one(self, model):
        """All weights should sum to 1.0 for proper normalization."""
        total = sum(model.weights.values())
        assert total == pytest.approx(1.0)

    def test_expected_weight_keys(self, model):
        """Model should have the expected feature weight keys."""
        expected_keys = {
            "price_stability",
            "low_competition",
            "good_sales_rank",
            "sales_velocity",
            "profit_margin",
            "roi",
        }
        assert set(model.weights.keys()) == expected_keys

    def test_all_weights_positive(self, model):
        """All weights should be positive."""
        for key, weight in model.weights.items():
            assert weight > 0, f"Weight for '{key}' should be positive, got {weight}"

    def test_competition_weight(self, model):
        assert model.weights["low_competition"] == 0.20

    def test_sales_rank_weight(self, model):
        assert model.weights["good_sales_rank"] == 0.20

    def test_sales_velocity_weight(self, model):
        assert model.weights["sales_velocity"] == 0.20


# ============================================================================
# Relative ordering
# ============================================================================
class TestDiscoveryModelOrdering:
    """Tests that scoring weights produce expected relative ordering."""

    def test_high_competition_beats_low(self, model):
        """A product with low competition (high feature value) should score
        higher than one with high competition (low feature value),
        holding all else equal."""
        # Only low_competition differs
        low_comp = [0.5, 1.0, 0.5, 0.5, 0.5, 0.5]  # Good (few competitors)
        high_comp = [0.5, 0.0, 0.5, 0.5, 0.5, 0.5]  # Bad (many competitors)
        assert model.predict(low_comp) > model.predict(high_comp)

    def test_good_rank_beats_bad_rank(self, model):
        """Better sales rank should score higher."""
        good_rank = [0.5, 0.5, 1.0, 0.5, 0.5, 0.5]
        bad_rank = [0.5, 0.5, 0.0, 0.5, 0.5, 0.5]
        assert model.predict(good_rank) > model.predict(bad_rank)

    def test_high_velocity_beats_low(self, model):
        """Higher sales velocity should score higher."""
        high_vel = [0.5, 0.5, 0.5, 1.0, 0.5, 0.5]
        low_vel = [0.5, 0.5, 0.5, 0.0, 0.5, 0.5]
        assert model.predict(high_vel) > model.predict(low_vel)

    def test_competition_has_more_weight_than_roi(self, model):
        """low_competition (0.20) should have more impact than roi (0.10)."""
        # Only competition feature is 1.0, rest 0.0
        comp_only = [0.0, 1.0, 0.0, 0.0, 0.0, 0.0]
        roi_only = [0.0, 0.0, 0.0, 0.0, 0.0, 1.0]
        assert model.predict(comp_only) > model.predict(roi_only)

    def test_three_dominant_features_beat_three_minor(self, model):
        """The three highest-weighted features (competition, rank, velocity at 0.20 each)
        should outscore price_stability (0.15), profit_margin (0.15), and roi (0.10)."""
        dominant = [0.0, 1.0, 1.0, 1.0, 0.0, 0.0]  # 0.60 total
        minor = [1.0, 0.0, 0.0, 0.0, 1.0, 1.0]  # 0.40 total
        assert model.predict(dominant) > model.predict(minor)

    def test_single_feature_contribution(self, model):
        """Each single feature at 1.0 should produce a score equal to its weight."""
        for i, key in enumerate(["price_stability", "low_competition",
                                  "good_sales_rank", "sales_velocity",
                                  "profit_margin", "roi"]):
            features = [0.0] * 6
            features[i] = 1.0
            score = model.predict(features)
            assert score == pytest.approx(model.weights[key], abs=1e-9), \
                f"Feature '{key}' at index {i} produced score {score}, expected {model.weights[key]}"


# ============================================================================
# Edge cases
# ============================================================================
class TestDiscoveryModelEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_fewer_than_six_features_returns_zero(self, model):
        """With fewer than 6 features, predict should return 0.0."""
        assert model.predict([0.5, 0.5, 0.5]) == 0.0
        assert model.predict([]) == 0.0
        assert model.predict([1.0]) == 0.0

    def test_exactly_five_features_returns_zero(self, model):
        assert model.predict([1.0, 1.0, 1.0, 1.0, 1.0]) == 0.0

    def test_more_than_six_features_uses_first_six(self, model):
        """Extra features beyond the 6th should be ignored."""
        features_6 = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]
        features_8 = [0.5, 0.5, 0.5, 0.5, 0.5, 0.5, 0.9, 0.9]
        assert model.predict(features_6) == model.predict(features_8)

    def test_values_above_one_are_clamped(self, model):
        """Features 3-5 (velocity, margin, roi) are clamped to 1.0 via min()."""
        features = [0.5, 0.5, 0.5, 5.0, 5.0, 5.0]
        score = model.predict(features)
        # velocity, margin, roi each clamped to 1.0
        expected = (
            0.15 * 0.5  # price_stability
            + 0.20 * 0.5  # low_competition
            + 0.20 * 0.5  # good_sales_rank
            + 0.20 * 1.0  # sales_velocity (clamped)
            + 0.15 * 1.0  # profit_margin (clamped)
            + 0.10 * 1.0  # roi (clamped)
        )
        assert score == pytest.approx(expected)

    def test_output_clamped_to_zero_one_range(self, model):
        """Score should always be between 0.0 and 1.0."""
        # Even with extreme values
        features = [10.0, 10.0, 10.0, 10.0, 10.0, 10.0]
        score = model.predict(features)
        assert 0.0 <= score <= 1.0

    def test_negative_features(self, model):
        """Negative features could bring the score below zero,
        but the output is clamped to max(0.0, ...)."""
        features = [-1.0, -1.0, -1.0, -1.0, -1.0, -1.0]
        score = model.predict(features)
        assert score >= 0.0

    def test_negative_velocity_clamped_by_min(self, model):
        """min(features[3], 1.0) with negative value still passes through."""
        features = [0.0, 0.0, 0.0, -0.5, 0.0, 0.0]
        score = model.predict(features)
        # -0.5 * 0.20 = -0.10, total = -0.10, clamped to 0.0
        assert score == 0.0


# ============================================================================
# Train / save / load (no-op stubs)
# ============================================================================
class TestDiscoveryModelStubs:
    """Tests for placeholder methods that don't do real work yet."""

    def test_train_does_not_raise(self, model):
        """train() should not raise even though it's not implemented."""
        import numpy as np
        X = np.array([[1, 2, 3], [4, 5, 6]])
        y = np.array([0, 1])
        model.train(X, y)  # Should not raise

    def test_save_does_not_raise(self, model):
        model.save("/tmp/test_model.pkl")  # Should not raise

    def test_load_does_not_raise(self, model):
        model.load("/tmp/test_model.pkl")  # Should not raise
