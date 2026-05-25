from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from math import isfinite
from typing import Any, TypeVar, cast

_EnumT = TypeVar("_EnumT", bound=Enum)


def _check_dict(name: str, value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise TypeError(f"{name} must be a dict")
    if any(not isinstance(key, str) for key in value):
        raise TypeError(f"{name} must have string keys")
    return cast(dict[str, Any], value)


def _require_field(d: dict[str, Any], key: str, *, context: str) -> Any:
    if key not in d:
        raise ValueError(f"{context} missing required field {key!r}")
    return d[key]


def _require_dict_field(
    d: dict[str, Any],
    key: str,
    *,
    context: str,
) -> dict[str, Any]:
    return _check_dict(f"{context}.{key}", _require_field(d, key, context=context))


def _require_str_field(d: dict[str, Any], key: str, *, context: str) -> str:
    value = _require_field(d, key, context=context)
    if not isinstance(value, str):
        raise TypeError(f"{context}.{key} must be a string")
    return value


def _enum_from_value(name: str, value: object, enum_type: type[_EnumT]) -> _EnumT:
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")

    members_by_value = {member.value: member for member in enum_type}
    if value not in members_by_value:
        allowed = ", ".join(repr(member.value) for member in enum_type)
        raise ValueError(f"{name} must be one of {allowed}")

    return members_by_value[value]


def _check_kind(d: dict[str, Any], expected_kind: str) -> dict[str, Any]:
    d = _check_dict("label spec", d)
    kind = _require_str_field(d, "kind", context="label spec")
    if kind != expected_kind:
        raise ValueError(f"expected label spec kind {expected_kind!r}, got {kind!r}")
    return d


class IndexSpace(str, Enum):
    EVENT = "event"
    TIME = "time"


class ReferenceMode(str, Enum):
    ANCHOR = "anchor"
    BEFORE_WINDOW_START = "before_window_start"


class ThresholdMode(str, Enum):
    ABSOLUTE = "absolute"
    RELATIVE = "relative"


class ThresholdSpace(str, Enum):
    PRICE = "price"
    TICK = "tick"


class SmoothMethod(str, Enum):
    LAST = "last"
    MEAN = "mean"
    EXTREMUM = "extremum"
    FIRST_MOVE = "first_move"

class CrossSelection(str, Enum):
    FIRST_MOVE = "first_move"
    LAST_MOVE = "last_move"
    EXTREMUM = "extremum"


def _index_space_code(space: IndexSpace) -> str:
    return "e" if space is IndexSpace.EVENT else "t"


def _reference_mode_code(mode: ReferenceMode) -> str:
    return "a" if mode is ReferenceMode.ANCHOR else "b"


def _threshold_mode_code(mode: ThresholdMode) -> str:
    return "a" if mode is ThresholdMode.ABSOLUTE else "r"


def _threshold_space_code(space: ThresholdSpace) -> str:
    return "p" if space is ThresholdSpace.PRICE else "t"


def _smooth_method_code(method: SmoothMethod) -> str:
    match method:
        case SmoothMethod.LAST:
            return "l"
        case SmoothMethod.MEAN:
            return "m"
        case SmoothMethod.EXTREMUM:
            return "x"
        case SmoothMethod.FIRST_MOVE:
            return "f"


def _cross_selection_code(selection: CrossSelection) -> str:
    match selection:
        case CrossSelection.FIRST_MOVE:
            return "f"
        case CrossSelection.LAST_MOVE:
            return "l"
        case CrossSelection.EXTREMUM:
            return "x"



def _check_int(name: str, value: int, *, minimum: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be an integer")
    if value < minimum:
        raise ValueError(f"{name} must be >= {minimum}")


def _check_float(name: str, value: float) -> None:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise TypeError(f"{name} must be numeric")
    if not isfinite(float(value)):
        raise ValueError(f"{name} must be finite")


def _check_enum(name: str, value: object, enum_type: type[Enum]) -> None:
    if not isinstance(value, enum_type):
        raise TypeError(f"{name} must be a {enum_type.__name__}")


@dataclass(frozen=True)
class IndexSpec:
    space: IndexSpace
    value: int

    @classmethod
    def events(cls, value: int) -> IndexSpec:
        return cls(space=IndexSpace.EVENT, value=value)

    @classmethod
    def nanoseconds(cls, value: int) -> IndexSpec:
        return cls(space=IndexSpace.TIME, value=value)

    def __post_init__(self) -> None:
        _check_enum("index space", self.space, IndexSpace)
        _check_int("index value", self.value, minimum=0)

    def require_positive(self, name: str) -> None:
        _check_int(name, self.value, minimum=1)

    def to_dict(self) -> dict[str, Any]:
        return {"space": self.space.value, "value": self.value}

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> IndexSpec:
        d = _check_dict("index spec", d)
        return cls(
            space=_enum_from_value(
                "index space",
                _require_field(d, "space", context="index spec"),
                IndexSpace,
            ),
            value=_require_field(d, "value", context="index spec"),
        )
    
@dataclass(frozen=True)
class ThresholdSpec:
    mode: ThresholdMode
    value: float
    space: ThresholdSpace

    @classmethod
    def absolute_ticks(cls, value: float) -> ThresholdSpec:
        return cls(ThresholdMode.ABSOLUTE, value, ThresholdSpace.TICK)

    @classmethod
    def absolute_price(cls, value: float) -> ThresholdSpec:
        return cls(ThresholdMode.ABSOLUTE, value, ThresholdSpace.PRICE)

    @classmethod
    def relative(cls, value: float) -> ThresholdSpec:
        # Space is irrelevant to Rust's relative logic.
        # Use PRICE consistently to keep task_id stable.
        return cls(ThresholdMode.RELATIVE, value, ThresholdSpace.PRICE)

    # Optional ergonomic aliases
    @classmethod
    def ticks(cls, value: float) -> "ThresholdSpec":
        return cls.absolute_ticks(value)

    @classmethod
    def price(cls, value: float) -> "ThresholdSpec":
        return cls.absolute_price(value)

    def __post_init__(self) -> None:
        _check_enum("threshold mode", self.mode, ThresholdMode)
        _check_enum("threshold space", self.space, ThresholdSpace)
        _check_float("threshold value", self.value)

        if self.value < 0:
            raise ValueError("threshold value must be >= 0")

        if self.mode is ThresholdMode.RELATIVE and self.space is not ThresholdSpace.PRICE:
            raise ValueError(
                "relative thresholds are unitless; use ThresholdSpec.relative(value)"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode.value,
            "value": float(self.value),
            "space": self.space.value,
        }
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ThresholdSpec:
        d = _check_dict("threshold spec", d)
        return cls(
            mode=_enum_from_value(
                "threshold mode",
                _require_field(d, "mode", context="threshold spec"),
                ThresholdMode,
            ),
            value=_require_field(d, "value", context="threshold spec"),
            space=_enum_from_value(
                "threshold space",
                _require_field(d, "space", context="threshold spec"),
                ThresholdSpace,
            ),
        )

# Generic label spec

class LabelSpec(ABC):

    @abstractmethod
    def task_id(self) -> str:
        pass

    @property
    @abstractmethod
    def num_classes(self) -> int:
        pass

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        pass

    @classmethod
    @abstractmethod
    def from_dict(cls, d: dict[str, Any]) -> LabelSpec:
        raise NotImplementedError("from_dict must be implemented by subclasses")

    

@dataclass(frozen=True)
class MidpriceMoveThreeClassSpec(LabelSpec):
    horizon: IndexSpec
    delay: IndexSpec
    reference_mode: ReferenceMode
    threshold: ThresholdSpec
    smoothing: SmoothMethod

    def __post_init__(self) -> None:
        if not isinstance(self.horizon, IndexSpec):
            raise TypeError("horizon must be an IndexSpec")
        if not isinstance(self.delay, IndexSpec):
            raise TypeError("delay must be an IndexSpec")
        _check_enum("reference_mode", self.reference_mode, ReferenceMode)
        if not isinstance(self.threshold, ThresholdSpec):
            raise TypeError("threshold must be a ThresholdSpec")
        _check_enum("smoothing", self.smoothing, SmoothMethod)

        self.horizon.require_positive("horizon")
        _check_int("delay", self.delay.value, minimum=0)

    @property
    def num_classes(self) -> int:
        return 3

    def task_id(self) -> str:
        return (
            f"mp3_h{_index_space_code(self.horizon.space)}{self.horizon.value}"
            f"_d{_index_space_code(self.delay.space)}{self.delay.value}"
            f"_ref-{_reference_mode_code(self.reference_mode)}"
            f"_thr-{_threshold_mode_code(self.threshold.mode)}{self.threshold.value}"
            f"{_threshold_space_code(self.threshold.space)}"
            f"_sm-{_smooth_method_code(self.smoothing)}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "midprice_move_three_class",
            "horizon": self.horizon.to_dict(),
            "delay": self.delay.to_dict(),
            "reference_mode": self.reference_mode.value,
            "threshold": self.threshold.to_dict(),
            "smoothing": self.smoothing.value,
        }
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MidpriceMoveThreeClassSpec:
        d = _check_kind(d, "midprice_move_three_class")
        return cls(
            horizon=IndexSpec.from_dict(
                _require_dict_field(d, "horizon", context="midprice_move_three_class")
            ),
            delay=IndexSpec.from_dict(
                _require_dict_field(d, "delay", context="midprice_move_three_class")
            ),
            reference_mode=_enum_from_value(
                "reference_mode",
                _require_field(d, "reference_mode", context="midprice_move_three_class"),
                ReferenceMode,
            ),
            threshold=ThresholdSpec.from_dict(
                _require_dict_field(d, "threshold", context="midprice_move_three_class")
            ),
            smoothing=_enum_from_value(
                "smoothing",
                _require_field(d, "smoothing", context="midprice_move_three_class"),
                SmoothMethod,
            ),
        )


@dataclass(frozen=True)
class MidpriceTwoClassSpec(LabelSpec):
    delay: IndexSpec
    reference_mode: ReferenceMode
    threshold: ThresholdSpec

    def __post_init__(self) -> None:
        if not isinstance(self.delay, IndexSpec):
            raise TypeError("delay must be an IndexSpec")
        if not isinstance(self.threshold, ThresholdSpec):
            raise TypeError("threshold must be a ThresholdSpec")

        _check_enum("reference_mode", self.reference_mode, ReferenceMode)
        _check_int("delay", self.delay.value, minimum=0)

    @property
    def num_classes(self) -> int:
        return 2

    def task_id(self) -> str:
        return (
            f"mp2_d{_index_space_code(self.delay.space)}{self.delay.value}"
            f"_ref-{_reference_mode_code(self.reference_mode)}"
            f"_thr-{_threshold_mode_code(self.threshold.mode)}{self.threshold.value}"
            f"{_threshold_space_code(self.threshold.space)}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "midprice_two_class",
            "delay": self.delay.to_dict(),
            "reference_mode": self.reference_mode.value,
            "threshold": self.threshold.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> MidpriceTwoClassSpec:
        d = _check_kind(d, "midprice_two_class")
        return cls(
            delay=IndexSpec.from_dict(
                _require_dict_field(d, "delay", context="midprice_two_class")
            ),
            reference_mode=_enum_from_value(
                "reference_mode",
                _require_field(d, "reference_mode", context="midprice_two_class"),
                ReferenceMode,
            ),
            threshold=ThresholdSpec.from_dict(
                _require_dict_field(d, "threshold", context="midprice_two_class")
            ),
        )


@dataclass(frozen=True)
class SpreadCrossTwoClassSpec(LabelSpec):
    delay: IndexSpec
    reference_mode: ReferenceMode
    threshold: ThresholdSpec
    cross_selection: CrossSelection = CrossSelection.FIRST_MOVE

    def __post_init__(self) -> None:
        if not isinstance(self.delay, IndexSpec):
            raise TypeError("delay must be an IndexSpec")
        if not isinstance(self.threshold, ThresholdSpec):
            raise TypeError("threshold must be a ThresholdSpec")

        _check_enum("reference_mode", self.reference_mode, ReferenceMode)
        _check_enum("cross_selection", self.cross_selection, CrossSelection)

        _check_int("delay", self.delay.value, minimum=0)

        if self.cross_selection is not CrossSelection.FIRST_MOVE:
            raise ValueError(
                "SpreadCrossTwoClassSpec currently supports only "
                "CrossSelection.FIRST_MOVE"
            )

    @property
    def num_classes(self) -> int:
        return 2

    def task_id(self) -> str:
        return (
            f"sc2_d{_index_space_code(self.delay.space)}{self.delay.value}"
            f"_ref-{_reference_mode_code(self.reference_mode)}"
            f"_thr-{_threshold_mode_code(self.threshold.mode)}{self.threshold.value}"
            f"{_threshold_space_code(self.threshold.space)}"
            f"_sel-{_cross_selection_code(self.cross_selection)}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "spread_cross_two_class",
            "delay": self.delay.to_dict(),
            "reference_mode": self.reference_mode.value,
            "threshold": self.threshold.to_dict(),
            "cross_selection": self.cross_selection.value,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SpreadCrossTwoClassSpec:
        d = _check_kind(d, "spread_cross_two_class")
        cross_selection = CrossSelection.FIRST_MOVE
        if "cross_selection" in d:
            cross_selection = _enum_from_value(
                "cross_selection",
                d["cross_selection"],
                CrossSelection,
            )

        return cls(
            delay=IndexSpec.from_dict(
                _require_dict_field(d, "delay", context="spread_cross_two_class")
            ),
            reference_mode=_enum_from_value(
                "reference_mode",
                _require_field(d, "reference_mode", context="spread_cross_two_class"),
                ReferenceMode,
            ),
            threshold=ThresholdSpec.from_dict(
                _require_dict_field(d, "threshold", context="spread_cross_two_class")
            ),
            cross_selection=cross_selection,
        )


@dataclass(frozen=True)
class SpreadCrossThreeClassSpec(LabelSpec):
    horizon: IndexSpec
    delay: IndexSpec
    reference_mode: ReferenceMode
    threshold: ThresholdSpec
    cross_selection: CrossSelection

    def __post_init__(self) -> None:
        if not isinstance(self.horizon, IndexSpec):
            raise TypeError("horizon must be an IndexSpec")
        if not isinstance(self.delay, IndexSpec):
            raise TypeError("delay must be an IndexSpec")
        if not isinstance(self.threshold, ThresholdSpec):
            raise TypeError("threshold must be a ThresholdSpec")

        _check_enum("reference_mode", self.reference_mode, ReferenceMode)
        _check_enum("cross_selection", self.cross_selection, CrossSelection)

        self.horizon.require_positive("horizon")
        _check_int("delay", self.delay.value, minimum=0)

    @property
    def num_classes(self) -> int:
        return 3

    def task_id(self) -> str:
        return (
            f"sc3_h{_index_space_code(self.horizon.space)}{self.horizon.value}"
            f"_d{_index_space_code(self.delay.space)}{self.delay.value}"
            f"_ref-{_reference_mode_code(self.reference_mode)}"
            f"_thr-{_threshold_mode_code(self.threshold.mode)}{self.threshold.value}"
            f"{_threshold_space_code(self.threshold.space)}"
            f"_sel-{_cross_selection_code(self.cross_selection)}"
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": "spread_cross_three_class",
            "horizon": self.horizon.to_dict(),
            "delay": self.delay.to_dict(),
            "reference_mode": self.reference_mode.value,
            "threshold": self.threshold.to_dict(),
            "cross_selection": self.cross_selection.value,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SpreadCrossThreeClassSpec:
        d = _check_kind(d, "spread_cross_three_class")
        return cls(
            horizon=IndexSpec.from_dict(
                _require_dict_field(d, "horizon", context="spread_cross_three_class")
            ),
            delay=IndexSpec.from_dict(
                _require_dict_field(d, "delay", context="spread_cross_three_class")
            ),
            reference_mode=_enum_from_value(
                "reference_mode",
                _require_field(d, "reference_mode", context="spread_cross_three_class"),
                ReferenceMode,
            ),
            threshold=ThresholdSpec.from_dict(
                _require_dict_field(d, "threshold", context="spread_cross_three_class")
            ),
            cross_selection=_enum_from_value(
                "cross_selection",
                _require_field(d, "cross_selection", context="spread_cross_three_class"),
                CrossSelection,
            ),
        )