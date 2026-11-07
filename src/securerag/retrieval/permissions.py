"""Permission model: turn a user into a Qdrant filter, enforced in the query.

The rule (group-based ACLs): a user may read a chunk if the user's groups overlap
the chunk's allowed_groups, OR the user's id is in the chunk's allowed_users. Since
every user is in the 'all' group, company-wide docs (allowed_groups=['all']) are
covered by the same overlap check.

The filter is applied INSIDE the Qdrant query (pre-filtering), never by discarding
results afterwards -- post-filtering would let forbidden chunks take top-k slots and
risks leaking data. `is_allowed` is a second, independent check for defense in depth.
"""

from __future__ import annotations

from dataclasses import dataclass

from qdrant_client import models


@dataclass
class Principal:
    """A user's identity and permission context, as used by retrieval."""

    id: str
    groups: list[str]


def build_filter(principal: Principal, current_only: bool = True) -> models.Filter:
    """Build a Qdrant filter admitting only readable (and current) chunks.

    `must` AND `should`: the chunk must be current (not a superseded version), and
    at least one `should` must hold -- its groups overlap the user's groups, or its
    allowed_users contains this user's id.
    """
    must = []
    if current_only:
        must.append(models.FieldCondition(key="is_current", match=models.MatchValue(value=True)))
    return models.Filter(
        must=must,
        should=[
            models.FieldCondition(
                key="allowed_groups",
                match=models.MatchAny(any=list(principal.groups)),
            ),
            models.FieldCondition(
                key="allowed_users",
                match=models.MatchAny(any=[principal.id]),
            ),
        ],
    )


def is_allowed(payload: dict, principal: Principal) -> bool:
    """Independently verify a chunk is readable by the user (defense in depth)."""
    allowed_groups = set(payload.get("allowed_groups") or [])
    allowed_users = set(payload.get("allowed_users") or [])
    return bool(allowed_groups & set(principal.groups)) or principal.id in allowed_users
