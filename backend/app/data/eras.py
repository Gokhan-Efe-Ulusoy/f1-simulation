"""F1 era classification (Phase 9D).

A season belongs to multiple overlapping eras (technical, sporting, tyre,
power-unit, regulation). Boundaries below are major, widely documented
rule/technology changes only; each carries a confidence score and the set
is intentionally small. Extend, don't hard-code new consumers.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class Era(BaseModel):
    """One era interval of a given kind."""

    era_id: str
    kind: str = ""  # technical | sporting | tyre | power_unit | regulation
    name: str = ""
    start_year: int = Field(ge=1950, le=2026)
    end_year: int | None = Field(default=None, ge=1950, le=2026)
    confidence: float = Field(default=0.9, ge=0.0, le=1.0)
    notes: str = ""

    model_config = {"use_enum_values": True}

    def covers(self, year: int) -> bool:
        """True when the era includes the given season."""
        if year < self.start_year:
            return False
        return self.end_year is None or year <= self.end_year


BUILTIN_ERAS: list[Era] = [
    # Historical era dataset (Phase 11 — hypotheses, not unquestionable truth)
    Era(era_id="era-1950-1957", kind="historical", name="Front-engine & early championship",
        start_year=1950, end_year=1957, confidence=0.85, notes="Front-engine, no constructors title until 1958."),  # noqa: E501
    Era(era_id="era-1958-1967", kind="historical", name="Rear-engine & British garagistes",
        start_year=1958, end_year=1967, confidence=0.85, notes="Rear-engine revolution, Lotus/Coooper."),  # noqa: E501
    Era(era_id="era-1968-1977", kind="historical", name="Wings & sponsorship",
        start_year=1968, end_year=1977, confidence=0.85, notes="Aero wings, commercial sponsorship."),  # noqa: E501
    Era(era_id="era-1978-1982", kind="historical", name="Ground effect I",
        start_year=1978, end_year=1982, confidence=0.85, notes="Venturi ground effect, sliding skirts."),  # noqa: E501
    Era(era_id="era-1983-1987", kind="historical", name="Turbo era peak",
        start_year=1983, end_year=1987, confidence=0.85, notes="1.5L turbo, 1000+ bhp qualifying."),
    Era(era_id="era-1988-1994", kind="historical", name="Normally aspirated & electronics",
        start_year=1988, end_year=1994, confidence=0.85, notes="3.5L NA, active suspension, traction control."),  # noqa: E501
    Era(era_id="era-1995-2005", kind="historical", name="V10 & refuelling",
        start_year=1995, end_year=2005, confidence=0.85, notes="3.0L V10, refuelling, grooved tyres from 1998."),  # noqa: E501
    Era(era_id="era-2006-2013", kind="historical", name="V8 & frozen development",
        start_year=2006, end_year=2013, confidence=0.85, notes="2.4L V8, homologation, KERS 2009."),
    Era(era_id="era-2014-2021", kind="historical", name="Turbo-hybrid",
        start_year=2014, end_year=2021, confidence=0.9, notes="1.6L V6 hybrid, DRS, halo 2018."),
    Era(era_id="era-2022-2026", kind="historical", name="Ground effect return & cost cap",
        start_year=2022, end_year=2026, confidence=0.9, notes="Venturi tunnels, cost cap, sprint weekends."),  # noqa: E501
    # Power-unit eras (detailed)
    Era(era_id="pu-v8-2006-2013", kind="power_unit", name="2.4L V8",
        start_year=2006, end_year=2013, confidence=0.9,
        notes="Homologated V8 formula."),
    Era(era_id="pu-v6-hybrid-2014+", kind="power_unit", name="1.6L V6 turbo hybrid",
        start_year=2014, end_year=None, confidence=0.95,
        notes="Turbo-hybrid power units with ERS."),
    Era(era_id="tyre-grooved-1998-2008", kind="tyre", name="Grooved dry tyres",
        start_year=1998, end_year=2008, confidence=0.9,
        notes="Grooved dry-weather tyres mandated."),
    Era(era_id="tyre-slick-2009+", kind="tyre", name="Slick dry tyres",
        start_year=2009, end_year=None, confidence=0.9,
        notes="Return to slick dry-weather tyres."),
    Era(era_id="sport-refuelling-ban-2010+", kind="sporting",
        name="Refuelling ban", start_year=2010, end_year=None, confidence=0.95,
        notes="No in-race refuelling."),
    Era(era_id="sport-drs-2011+", kind="sporting", name="DRS",
        start_year=2011, end_year=None, confidence=0.95,
        notes="Drag Reduction System in designated zones."),
    Era(era_id="sport-halo-2018+", kind="sporting", name="Halo cockpit protection",
        start_year=2018, end_year=None, confidence=0.9,
        notes="Halo device mandatory."),
    Era(era_id="sport-sprint-2021+", kind="sporting", name="Sprint weekends",
        start_year=2021, end_year=None, confidence=0.9,
        notes="Selected weekends include a sprint race."),
    Era(era_id="tech-groundeffect-2022+", kind="technical",
        name="Ground-effect return", start_year=2022, end_year=None,
        confidence=0.9, notes="Venturi-tunnel based regulations."),
]


def season_eras(year: int, eras: list[Era] | None = None) -> list[str]:
    """Return era IDs covering a season, sorted for determinism."""
    table = eras if eras is not None else BUILTIN_ERAS
    return sorted(era.era_id for era in table if era.covers(year))


def eras_by_kind(year: int, kind: str, eras: list[Era] | None = None) -> list[str]:
    """Return covering era IDs of one kind."""
    table = eras if eras is not None else BUILTIN_ERAS
    return sorted(era.era_id for era in table if era.kind == kind and era.covers(year))
