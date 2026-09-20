"""Era model reuse - curated regulations."""
from __future__ import annotations
from app.data.regulations.curated import regulations_for_season

def era_for_season(season: int):
    # reuse phase23 era definitions, not invention
    eras=[(1950,1969),(1970,1982),(1983,1996),(1997,2008),(2009,2013),(2014,2021),(2022,2026)]
    for s,e in eras:
        if s <= season <= e:
            return f"{s}-{e}"
    return "unknown"
