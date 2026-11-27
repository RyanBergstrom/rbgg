"""Communication helpers for Fields of Fire."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Any


class Entity(Protocol):
    """Minimal protocol for an entity that can communicate."""

    @property
    def position(self) -> int | None:
        """Terrain card position, or None if off-map/staging."""

    @property
    def is_staging(self) -> bool:
        """True if the entity is in the staging area."""


def _get_position(entity: Any) -> int | None:
    """Extract position from entity (dict or object with .position)."""
    if isinstance(entity, dict):
        return entity.get("position")
    return getattr(entity, "position", None)


def _get_is_staging(entity: Any) -> bool:
    """Extract is_staging from entity (dict or object with .is_staging)."""
    if isinstance(entity, dict):
        return entity.get("is_staging", False)
    return getattr(entity, "is_staging", False)


class CommunicationRule(Protocol):
    """Protocol for a single communication rule."""

    def check(self, a: Any, b: Any, ctx: CommunicationContext) -> bool:
        """Return True if this rule says a and b are in communication."""


@dataclass(frozen=True)
class CommunicationContext:
    """Context available to communication rules.

    Extend with additional game state (e.g., radio nets, leaders, LOS) as needed.
    """

    # Future: add radio_net_map, leader_positions, los_matrix, etc.


class SameCardRule:
    """Entities on the same terrain card are in communication."""

    def check(self, a: Any, b: Any, ctx: CommunicationContext) -> bool:
        return _get_position(a) is not None and _get_position(a) == _get_position(b)


class StagingAreaRule:
    """All entities in the staging area are in communication with each other."""

    def check(self, a: Any, b: Any, ctx: CommunicationContext) -> bool:
        return _get_is_staging(a) and _get_is_staging(b)


DEFAULT_RULES: list[CommunicationRule] = [
    SameCardRule(),
    StagingAreaRule(),
]


def check_in_communication(
    a: Any,
    b: Any,
    ctx: CommunicationContext | None = None,
    rules: list[CommunicationRule] | None = None,
) -> bool:
    """Return True if ``a`` and ``b`` are in communication.

    Two entities are in communication if *any* rule says they are
    (OR semantics). Rules are evaluated in order; the first match wins.

    Args:
        a: First entity (dict or object with position/is_staging).
        b: Second entity (dict or object with position/is_staging).
        ctx: Optional communication context (radio nets, LOS, etc.).
        rules: Optional custom rule list. Defaults to ``DEFAULT_RULES``.

    Returns:
        True if the entities can communicate, False otherwise.
    """
    if ctx is None:
        ctx = CommunicationContext()
    if rules is None:
        rules = DEFAULT_RULES
    for rule in rules:
        if rule.check(a, b, ctx):
            return True
    return False


def add_communication_rule(rule: CommunicationRule, *, before: CommunicationRule | None = None) -> None:
    """Register a new rule globally (affects future calls with default rules)."""
    if before is not None:
        try:
            idx = DEFAULT_RULES.index(before)
            DEFAULT_RULES.insert(idx, rule)
        except ValueError:
            DEFAULT_RULES.append(rule)
    else:
        DEFAULT_RULES.append(rule)


def remove_communication_rule(rule: CommunicationRule) -> bool:
    """Remove a rule from the default chain. Returns True if removed."""
    try:
        DEFAULT_RULES.remove(rule)
        return True
    except ValueError:
        return False