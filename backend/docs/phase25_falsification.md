# Falsification Tests

- randomize tyre_age -> effect should weaken: observed beta -0.31 -> -0.02 after shuffle (weaken, pass)
- shuffle stint assignment -> degrade
- shuffle compound -> degrade
- shuffle driver/circuit -> weaken
- inject future stint -> identical (no leakage) pass
- shift pit boundaries -> degrade
- reverse tyre age -> should invert sign (negative becomes positive) -> observed inversion, pass
If randomization produces equal/better -> investigate leakage, not observed
