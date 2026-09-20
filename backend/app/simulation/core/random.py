from __future__ import annotations

import numpy as np
from numpy.typing import NDArray


class RandomProvider:
    """Centralized random number generator for deterministic simulations.
    
    All simulation randomness must go through this provider to ensure
    reproducibility when a seed is provided.
    """

    def __init__(self, seed: int | None = None):
        self._seed = seed
        self._rng = np.random.default_rng(seed)
        self._streams: dict[str, np.random.Generator] = {}

    @property
    def seed(self) -> int | None:
        return self._seed

    def random(self) -> float:
        """Return random float in [0, 1)."""
        return float(self._rng.random())

    def uniform(self, low: float = 0.0, high: float = 1.0) -> float:
        """Return random float in [low, high)."""
        return float(self._rng.uniform(low, high))

    def normal(self, mean: float = 0.0, std: float = 1.0) -> float:
        """Return random float from normal distribution."""
        return float(self._rng.normal(mean, std))

    def lognormal(self, mean: float = 0.0, sigma: float = 1.0) -> float:
        """Return random float from log-normal distribution."""
        return float(self._rng.lognormal(mean, sigma))

    def exponential(self, scale: float = 1.0) -> float:
        """Return random float from exponential distribution."""
        return float(self._rng.exponential(scale))

    def choice(self, a: int | NDArray, size: int | None = None, replace: bool = True, p: NDArray | None = None) -> NDArray | int:  # noqa: E501
        """Random choice from array or integer range."""
        return self._rng.choice(a, size=size, replace=replace, p=p)

    def integers(self, low: int, high: int | None = None, size: int | None = None) -> NDArray | int:
        """Return random integers from [low, high)."""
        return self._rng.integers(low, high, size=size)

    def binomial(self, n: int, p: float, size: int | None = None) -> NDArray | int:
        """Return random integers from binomial distribution."""
        return self._rng.binomial(n, p, size=size)

    def poisson(self, lam: float = 1.0, size: int | None = None) -> NDArray | int:
        """Return random integers from Poisson distribution."""
        return self._rng.poisson(lam, size=size)

    def get_stream(self, name: str) -> np.random.Generator:
        """Get or create a named independent random stream.
        
        Useful for separating different sources of randomness
        (e.g., tyre degradation vs overtaking vs weather).
        """
        if name not in self._streams:
            # Derive stream seed from main seed + hash of name
            stream_seed = None
            if self._seed is not None:
                stream_seed = hash((self._seed, name)) & 0xFFFFFFFF
            self._streams[name] = np.random.default_rng(stream_seed)
        return self._streams[name]

    def shuffle(self, x: NDArray) -> None:
        """Shuffle array in-place."""
        self._rng.shuffle(x)

    def permutation(self, x: int | NDArray) -> NDArray:
        """Return randomly permuted array or range."""
        return self._rng.permutation(x)

    def beta(self, a: float, b: float, size: int | None = None) -> NDArray | float:
        """Return random float from Beta distribution."""
        result = self._rng.beta(a, b, size=size)
        return float(result) if size is None else result

    def gamma(self, shape: float, scale: float = 1.0, size: int | None = None) -> NDArray | float:
        """Return random float from Gamma distribution."""
        result = self._rng.gamma(shape, scale, size=size)
        return float(result) if size is None else result
