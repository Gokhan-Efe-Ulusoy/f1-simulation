import numpy as np
import pytest

from app.simulation.core.random import RandomProvider


class TestRandomProvider:
    """Tests for RandomProvider deterministic behavior."""

    def test_same_seed_produces_same_sequence(self):
        """Same seed should produce identical random sequences."""
        rng1 = RandomProvider(seed=42)
        rng2 = RandomProvider(seed=42)

        for _ in range(100):
            assert rng1.random() == rng2.random()
            assert rng1.normal() == rng2.normal()
            assert rng1.uniform(0, 10) == rng2.uniform(0, 10)

    def test_different_seeds_produce_different_sequences(self):
        """Different seeds should produce different sequences."""
        rng1 = RandomProvider(seed=42)
        rng2 = RandomProvider(seed=43)

        # Very unlikely to be the same for 100 consecutive calls
        same_count = 0
        for _ in range(100):
            if rng1.random() == rng2.random():
                same_count += 1
        assert same_count < 5  # Should be essentially 0

    def test_seed_none_produces_non_deterministic(self):
        """Seed=None should produce different sequences each time."""
        rng1 = RandomProvider(seed=None)
        rng2 = RandomProvider(seed=None)

        # Should be different (extremely unlikely to be same)
        assert rng1.random() != rng2.random()

    def test_get_stream_creates_independent_streams(self):
        """Named streams should be independent."""
        rng = RandomProvider(seed=42)
        stream1 = rng.get_stream("test1")
        stream2 = rng.get_stream("test2")

        # Main RNG should be unaffected
        main_val = rng.random()

        # Streams should produce different values
        assert stream1.random() != stream2.random()

    def test_distributions_work(self):
        """All distribution methods should work."""
        rng = RandomProvider(seed=123)

        # Test ranges
        assert 0 <= rng.random() < 1
        assert 5 <= rng.uniform(5, 10) < 10
        assert rng.integers(0, 10) in range(0, 10)
        assert rng.binomial(10, 0.5) in range(0, 11)
        assert rng.poisson(5) >= 0

        # Normal distribution (just check it returns float)
        assert isinstance(rng.normal(0, 1), float)
        assert isinstance(rng.lognormal(0, 1), float)
        assert isinstance(rng.exponential(1), float)
        assert isinstance(rng.beta(2, 2), float)
        assert isinstance(rng.gamma(2, 1), float)

    def test_choice_and_shuffle(self):
        """Choice and shuffle should work."""
        rng = RandomProvider(seed=123)

        # Choice from array
        arr = np.array([1, 2, 3, 4, 5])
        choice = rng.choice(arr)
        assert choice in [1, 2, 3, 4, 5]

        # Choice with probabilities
        p = np.array([0.1, 0.2, 0.3, 0.2, 0.2])
        choices = [rng.choice(arr, p=p) for _ in range(1000)]
        # 3 should be most common
        assert choices.count(3) > choices.count(1)

        # Shuffle
        test_arr = np.array([1, 2, 3, 4, 5])
        rng.shuffle(test_arr)
        assert set(test_arr) == {1, 2, 3, 4, 5}

        # Permutation
        perm = rng.permutation(5)
        assert set(perm) == {0, 1, 2, 3, 4}


class TestRandomProviderReproducibility:
    """Test that simulation-level reproducibility works."""

    def test_full_simulation_reproducibility(self):
        """A full 'simulation' with multiple random calls should be reproducible."""
        def run_simulation(seed: int) -> list:
            rng = RandomProvider(seed=seed)
            results = []
            for i in range(10):
                # Simulate a lap with multiple random calls
                lap_time = 90 + rng.normal(0, 0.5)
                overtake = rng.random() < 0.1
                incident = rng.random() < 0.02
                tyre_deg = rng.uniform(0.02, 0.08)
                results.append((lap_time, overtake, incident, tyre_deg))
            return results

        results1 = run_simulation(42)
        results2 = run_simulation(42)

        assert results1 == results2

        # Different seed should give different results
        results3 = run_simulation(43)
        assert results1 != results3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
