# Source Reconciliation

Jolpica laps 552656 (1996-2026) vs OpenF1 laps 93650 (2023-2026) and stints 4840
Systematic differences: lap-1 offset (Jolpica 1-indexed per driver, OpenF1 includes formation lap differences), missing laps (Jolpica truncated for DNF, OpenF1 more complete), different retirement handling (Jolpica truncated, OpenF1 retains), stint numbering both 1-indexed but OpenF1 more granular, compound Jolpica 0 before 2023 vs OpenF1 2023+ only
Rule: select strongest evidence per variable per era: for tyre-age use OpenF1 exact join 2023+; for historical laps use Jolpica baseline without tyre; never overwrite one source merely because newer
