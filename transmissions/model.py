from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

try:
    from .core.clutch import Brake, Clutch, RotatingMember, Sprag
    from .core.planetary import PlanetaryGearSet
    from .core.solver import TransmissionSolver
    from .utils import (
        TransmissionAppError,
        coerce_int,
        dedupe_keep_order,
        ensure_dict,
        ensure_list,
        ensure_str,
        normalize_state_name,
    )
except ImportError:
    from core.clutch import Brake, Clutch, RotatingMember, Sprag
    from core.planetary import PlanetaryGearSet
    from core.solver import TransmissionSolver
    from utils import (
        TransmissionAppError,
        coerce_int,
        dedupe_keep_order,
        ensure_dict,
        ensure_list,
        ensure_str,
        normalize_state_name,
    )


@dataclass(frozen=True)
class GearsetSpec:
    name: str
    Ns: int
    Nr: int
    sun: str
    ring: str
    carrier: str


@dataclass(frozen=True)
class ClutchSpec:
    name: str
    a: str
    b: str


@dataclass(frozen=True)
class BrakeSpec:
    name: str
    member: str


@dataclass(frozen=True)
class SpragSpec:
    name: str
    member: str
    hold_direction: str = "counter_clockwise"
    locked_when_engaged: bool = True


@dataclass(frozen=True)
class ShiftStateSpec:
    name: str
    active_constraints: tuple[str, ...]
    display_elements: tuple[str, ...]
    notes: str = ""
    manual_neutral: bool = False


@dataclass
class TransmissionSpec:
    name: str
    input_member: str
    output_member: str
    gearsets: list[GearsetSpec]
    clutches: list[ClutchSpec]
    brakes: list[BrakeSpec]
    sprags: list[SpragSpec] = field(default_factory=list)
    permanent_ties: list[tuple[str, str]] = field(default_factory=list)
    members: list[str] = field(default_factory=list)
    display_order: list[str] = field(default_factory=list)
    state_aliases: dict[str, str] = field(default_factory=dict)
    speed_display_order: list[str] = field(default_factory=list)
    speed_display_labels: dict[str, str] = field(default_factory=dict)
    strict_geometry: bool = False
    notes: str = ""
    presets: dict[str, Any] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)

    @staticmethod
    def _raw_clutch_items(spec_dict: Mapping[str, Any]) -> tuple[list[Any], str]:
        """Return clutch-like items with backward-compatible schema support.

        Preferred modern key:
            clutches_brakes_flywheels

        Legacy key still supported:
            clutches
        """
        if spec_dict.get("clutches_brakes_flywheels") is not None:
            return (
                ensure_list(
                    spec_dict.get("clutches_brakes_flywheels"),
                    context="spec.clutches_brakes_flywheels",
                ),
                "spec.clutches_brakes_flywheels",
            )
        return (
            ensure_list(spec_dict.get("clutches"), context="spec.clutches"),
            "spec.clutches",
        )

    @staticmethod
    def from_dict(data: Mapping[str, Any]) -> "TransmissionSpec":
        d = ensure_dict(data, context="transmission spec")

        name = str(d.get("name", "Generic Transmission")).strip() or "Generic Transmission"
        input_member = ensure_str(d.get("input_member"), context="spec.input_member")
        output_member = ensure_str(d.get("output_member"), context="spec.output_member")
        strict_geometry = bool(d.get("strict_geometry", False))
        notes = str(d.get("notes", ""))

        members = [
            ensure_str(x, context="spec.members[]")
            for x in ensure_list(d.get("members"), context="spec.members")
        ]
        display_order = [
            ensure_str(x, context="spec.display_order[]")
            for x in ensure_list(d.get("display_order"), context="spec.display_order")
        ]
        speed_display_order = [
            ensure_str(x, context="spec.speed_display_order[]")
            for x in ensure_list(d.get("speed_display_order"), context="spec.speed_display_order")
        ]

        raw_aliases = ensure_dict(d.get("state_aliases"), context="spec.state_aliases")
        state_aliases = {
            ensure_str(k, context="spec.state_aliases key"): ensure_str(v, context="spec.state_aliases value")
            for k, v in raw_aliases.items()
        }

        raw_speed_labels = ensure_dict(d.get("speed_display_labels"), context="spec.speed_display_labels")
        speed_display_labels = {
            ensure_str(k, context="spec.speed_display_labels key"): ensure_str(v, context="spec.speed_display_labels value")
            for k, v in raw_speed_labels.items()
        }

        presets = ensure_dict(d.get("presets"), context="spec.presets")
        meta = ensure_dict(d.get("meta"), context="spec.meta")

        gearsets: list[GearsetSpec] = []
        for idx, item in enumerate(ensure_list(d.get("gearsets"), context="spec.gearsets")):
            g = ensure_dict(item, context=f"spec.gearsets[{idx}]")
            gearsets.append(
                GearsetSpec(
                    name=ensure_str(g.get("name"), context=f"spec.gearsets[{idx}].name"),
                    Ns=coerce_int(g.get("Ns"), context=f"spec.gearsets[{idx}].Ns"),
                    Nr=coerce_int(g.get("Nr"), context=f"spec.gearsets[{idx}].Nr"),
                    sun=ensure_str(g.get("sun"), context=f"spec.gearsets[{idx}].sun"),
                    ring=ensure_str(g.get("ring"), context=f"spec.gearsets[{idx}].ring"),
                    carrier=ensure_str(g.get("carrier"), context=f"spec.gearsets[{idx}].carrier"),
                )
            )

        if not gearsets:
            raise TransmissionAppError("spec.gearsets must contain at least one planetary gearset.")

        raw_clutch_items, clutch_context = TransmissionSpec._raw_clutch_items(d)
        clutches: list[ClutchSpec] = []
        for idx, item in enumerate(raw_clutch_items):
            c = ensure_dict(item, context=f"{clutch_context}[{idx}]")
            clutches.append(
                ClutchSpec(
                    name=ensure_str(c.get("name"), context=f"{clutch_context}[{idx}].name"),
                    a=ensure_str(c.get("a"), context=f"{clutch_context}[{idx}].a"),
                    b=ensure_str(c.get("b"), context=f"{clutch_context}[{idx}].b"),
                )
            )

        brakes: list[BrakeSpec] = []
        for idx, item in enumerate(ensure_list(d.get("brakes"), context="spec.brakes")):
            b = ensure_dict(item, context=f"spec.brakes[{idx}]")
            brakes.append(
                BrakeSpec(
                    name=ensure_str(b.get("name"), context=f"spec.brakes[{idx}].name"),
                    member=ensure_str(b.get("member"), context=f"spec.brakes[{idx}].member"),
                )
            )

        sprags: list[SpragSpec] = []
        for idx, item in enumerate(ensure_list(d.get("sprags"), context="spec.sprags")):
            s = ensure_dict(item, context=f"spec.sprags[{idx}]")
            sprags.append(
                SpragSpec(
                    name=ensure_str(s.get("name"), context=f"spec.sprags[{idx}].name"),
                    member=ensure_str(s.get("member"), context=f"spec.sprags[{idx}].member"),
                    hold_direction=str(s.get("hold_direction", "counter_clockwise")).strip() or "counter_clockwise",
                    locked_when_engaged=bool(s.get("locked_when_engaged", True)),
                )
            )

        permanent_ties: list[tuple[str, str]] = []
        for idx, item in enumerate(ensure_list(d.get("permanent_ties"), context="spec.permanent_ties")):
            if not isinstance(item, list) or len(item) != 2:
                raise TransmissionAppError(f"spec.permanent_ties[{idx}] must be a 2-item array.")
            a = ensure_str(item[0], context=f"spec.permanent_ties[{idx}][0]")
            b = ensure_str(item[1], context=f"spec.permanent_ties[{idx}][1]")
            permanent_ties.append((a, b))

        return TransmissionSpec(
            name=name,
            input_member=input_member,
            output_member=output_member,
            gearsets=gearsets,
            clutches=clutches,
            brakes=brakes,
            sprags=sprags,
            permanent_ties=permanent_ties,
            members=members,
            display_order=display_order,
            state_aliases=state_aliases,
            speed_display_order=speed_display_order,
            speed_display_labels=speed_display_labels,
            strict_geometry=strict_geometry,
            notes=notes,
            presets=presets,
            meta=meta,
        )

    def all_member_names(self) -> list[str]:
        out: list[str] = []
        out.extend(self.members)
        out.append(self.input_member)
        out.append(self.output_member)

        for g in self.gearsets:
            out.extend([g.sun, g.ring, g.carrier])

        for c in self.clutches:
            out.extend([c.a, c.b])

        for b in self.brakes:
            out.append(b.member)

        for s in self.sprags:
            out.append(s.member)

        for a, b in self.permanent_ties:
            out.extend([a, b])

        return dedupe_keep_order(out)


@dataclass
class ShiftSchedule:
    states: dict[str, ShiftStateSpec]
    notes: str = ""
    display_order: list[str] = field(default_factory=list)

    @staticmethod
    def from_dict(data: Mapping[str, Any], *, aliases: Mapping[str, str] | None = None) -> "ShiftSchedule":
        d = ensure_dict(data, context="shift schedule")
        raw_states = ensure_dict(d.get("states"), context="schedule.states")
        states: dict[str, ShiftStateSpec] = {}

        for raw_state, raw_spec in raw_states.items():
            state_name = normalize_state_name(str(raw_state), aliases)

            if isinstance(raw_spec, list):
                elems = ensure_list(raw_spec, context=f"schedule.states.{raw_state}")
                active = tuple(
                    ensure_str(x, context=f"schedule.states.{raw_state}[]")
                    for x in elems
                )
                states[state_name] = ShiftStateSpec(
                    name=state_name,
                    active_constraints=active,
                    display_elements=active,
                    notes="",
                    manual_neutral=False,
                )
                continue

            spec_obj = ensure_dict(raw_spec, context=f"schedule.states.{raw_state}")

            active_raw = ensure_list(
                spec_obj.get("active_constraints", spec_obj.get("engaged")),
                context=f"schedule.states.{raw_state}.active_constraints",
            )
            active = tuple(
                ensure_str(x, context=f"schedule.states.{raw_state}.active_constraints[]")
                for x in active_raw
            )

            display_raw = ensure_list(
                spec_obj.get("display_elements", list(active)),
                context=f"schedule.states.{raw_state}.display_elements",
            )
            display = tuple(
                ensure_str(x, context=f"schedule.states.{raw_state}.display_elements[]")
                for x in display_raw
            )

            notes = str(spec_obj.get("notes", ""))
            manual_neutral = bool(spec_obj.get("manual_neutral", False))

            states[state_name] = ShiftStateSpec(
                name=state_name,
                active_constraints=active,
                display_elements=display,
                notes=notes,
                manual_neutral=manual_neutral,
            )

        display_order = [
            ensure_str(x, context="schedule.display_order[]")
            for x in ensure_list(d.get("display_order"), context="schedule.display_order")
        ]
        notes = str(d.get("notes", ""))

        return ShiftSchedule(states=states, notes=notes, display_order=display_order)


@dataclass(frozen=True)
class GenericSolveResult:
    state: str
    engaged: tuple[str, ...]
    ok: bool
    ratio: float | None
    speeds: dict[str, float]
    notes: str = ""
    solver_path: str = "core_generic_json_builder"
    status: str = "ok"
    message: str = ""


class GenericTransmission:
    def __init__(self, *, spec: TransmissionSpec, schedule: ShiftSchedule) -> None:
        self.spec = spec
        self.schedule = schedule
        self._validate_schedule_elements()

    def _validate_schedule_elements(self) -> None:
        valid = (
            {c.name for c in self.spec.clutches}
            | {b.name for b in self.spec.brakes}
            | {s.name for s in self.spec.sprags}
        )
        for state, state_spec in self.schedule.states.items():
            for elem in state_spec.active_constraints:
                if elem not in valid:
                    valid_txt = ", ".join(sorted(valid))
                    raise TransmissionAppError(
                        f"Schedule state '{state}' references unknown shift element '{elem}'. "
                        f"Valid elements: {valid_txt}"
                    )

    def _member_map(self) -> dict[str, RotatingMember]:
        return {name: RotatingMember(name) for name in self.spec.all_member_names()}

    def build_solver(
        self,
    ) -> tuple[
        TransmissionSolver,
        dict[str, RotatingMember],
        dict[str, Clutch],
        dict[str, Brake],
        dict[str, Sprag],
    ]:
        members = self._member_map()
        solver = TransmissionSolver()

        for gear in self.spec.gearsets:
            gearset = PlanetaryGearSet(
                Ns=gear.Ns,
                Nr=gear.Nr,
                name=gear.name,
                sun=members[gear.sun],
                ring=members[gear.ring],
                carrier=members[gear.carrier],
                geometry_mode="strict" if self.spec.strict_geometry else "relaxed",
            )
            solver.add_gearset(gearset)

        clutch_map: dict[str, Clutch] = {}
        for c in self.spec.clutches:
            obj = Clutch(members[c.a], members[c.b], name=c.name)
            solver.add_clutch(obj)
            clutch_map[c.name] = obj

        brake_map: dict[str, Brake] = {}
        for b in self.spec.brakes:
            obj = Brake(members[b.member], name=b.name)
            solver.add_brake(obj)
            brake_map[b.name] = obj

        sprag_map: dict[str, Sprag] = {}
        for s in self.spec.sprags:
            obj = Sprag(
                members[s.member],
                hold_direction=s.hold_direction,
                locked_when_engaged=s.locked_when_engaged,
                name=s.name,
            )
            solver.add_brake(obj)  # type: ignore[arg-type]
            sprag_map[s.name] = obj

        for a, b in self.spec.permanent_ties:
            solver.add_permanent_tie(a, b)

        return solver, members, clutch_map, brake_map, sprag_map

    def topology_summary(self) -> dict[str, Any]:
        return {
            "name": self.spec.name,
            "input_member": self.spec.input_member,
            "output_member": self.spec.output_member,
            "strict_geometry": self.spec.strict_geometry,
            "members": self.spec.all_member_names(),
            "gearsets": [
                {
                    "name": g.name,
                    "Ns": g.Ns,
                    "Nr": g.Nr,
                    "sun": g.sun,
                    "ring": g.ring,
                    "carrier": g.carrier,
                }
                for g in self.spec.gearsets
            ],
            "clutches_brakes_flywheels": [{"name": c.name, "a": c.a, "b": c.b} for c in self.spec.clutches],
            "clutches": [{"name": c.name, "a": c.a, "b": c.b} for c in self.spec.clutches],
            "brakes": [{"name": b.name, "member": b.member} for b in self.spec.brakes],
            "sprags": [
                {
                    "name": s.name,
                    "member": s.member,
                    "hold_direction": s.hold_direction,
                    "locked_when_engaged": s.locked_when_engaged,
                }
                for s in self.spec.sprags
            ],
            "permanent_ties": [list(x) for x in self.spec.permanent_ties],
            "schedule_states": list(self.schedule.states.keys()),
            "notes": self.spec.notes,
            "meta": self.spec.meta,
        }

    def normalize_state_name(self, state: str) -> str:
        return normalize_state_name(state, self.spec.state_aliases)

    def available_states(self) -> list[str]:
        if self.schedule.display_order:
            ordered = [s for s in self.schedule.display_order if s in self.schedule.states]
            tail = [s for s in self.schedule.states if s not in ordered]
            return ordered + tail

        if self.spec.display_order:
            ordered = [s for s in self.spec.display_order if s in self.schedule.states]
            tail = [s for s in self.schedule.states if s not in ordered]
            return ordered + tail

        return list(self.schedule.states.keys())

    def _manual_neutral_speeds(self, *, input_speed: float) -> dict[str, float]:
        speeds: dict[str, float] = {}
        for name in self.spec.all_member_names():
            speeds[name] = 0.0
        speeds[self.spec.input_member] = float(input_speed)
        speeds[self.spec.output_member] = 0.0
        return speeds

    def solve_state(self, state: str, *, input_speed: float = 1.0) -> GenericSolveResult:
        resolved = self.normalize_state_name(state)
        if resolved.lower() == "all":
            raise TransmissionAppError("solve_state() expects one state, not 'all'.")

        if resolved not in self.schedule.states:
            valid = ", ".join(self.available_states())
            raise TransmissionAppError(f"Unknown state '{state}'. Valid states: {valid}")

        state_spec = self.schedule.states[resolved]

        if state_spec.manual_neutral:
            return GenericSolveResult(
                state=resolved,
                engaged=tuple(state_spec.display_elements),
                ok=True,
                ratio=0.0,
                speeds=self._manual_neutral_speeds(input_speed=float(input_speed)),
                notes=state_spec.notes,
                solver_path="core_generic_json_builder",
                status="manual_neutral",
                message="State reported through manual-neutral convention.",
            )

        solver, _members, clutch_map, brake_map, sprag_map = self.build_solver()
        solver.release_all()

        for elem in state_spec.active_constraints:
            if elem in clutch_map:
                clutch_map[elem].engage()
            elif elem in brake_map:
                brake_map[elem].engage()
            elif elem in sprag_map:
                sprag_map[elem].engage()
            else:
                raise TransmissionAppError(f"Internal error: unknown shift element '{elem}'.")

        report = solver.solve_report(self.spec.input_member, input_speed=float(input_speed))
        speeds = dict(report.member_speeds)
        out_speed = speeds.get(self.spec.output_member)

        ratio: float | None = None
        status = report.classification.status
        message = report.classification.message

        if out_speed is not None and abs(out_speed) > 1.0e-12:
            ratio = float(input_speed) / float(out_speed)
            if report.ok:
                status = "output_determined"
        elif out_speed is not None and abs(out_speed) <= 1.0e-12:
            ratio = None
            if report.ok:
                status = "output_zero"

        return GenericSolveResult(
            state=resolved,
            engaged=tuple(state_spec.display_elements),
            ok=bool(report.ok),
            ratio=ratio,
            speeds=speeds,
            notes=state_spec.notes,
            solver_path="core_generic_json_builder",
            status=status,
            message=message,
        )

    def solve(self, *, state: str, input_speed: float = 1.0) -> dict[str, GenericSolveResult]:
        resolved = self.normalize_state_name(state)
        if resolved.lower() != "all":
            res = self.solve_state(resolved, input_speed=input_speed)
            return {res.state: res}

        out: dict[str, GenericSolveResult] = {}
        for s in self.available_states():
            out[s] = self.solve_state(s, input_speed=input_speed)
        return out