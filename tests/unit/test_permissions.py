"""Phase 6 unit tests: the permission rule and the Qdrant filter (no DB/Qdrant)."""

from __future__ import annotations

from qdrant_client import models

from securerag.retrieval.permissions import Principal, build_filter, is_allowed

CEO = Principal("u_ceo", ["leadership", "hr", "finance", "engineering", "all"])
INTERN = Principal("u_int", ["all"])

HR_DOC = {"allowed_groups": ["hr", "leadership"], "allowed_users": []}
PUBLIC_DOC = {"allowed_groups": ["all"], "allowed_users": []}


def test_group_overlap_grants_access():
    assert is_allowed(HR_DOC, CEO) is True
    assert is_allowed(HR_DOC, INTERN) is False


def test_everyone_can_read_company_wide_docs():
    assert is_allowed(PUBLIC_DOC, INTERN) is True


def test_allowed_users_exception_grants_access():
    user = Principal("u_x", ["engineering"])  # not in hr
    doc = {"allowed_groups": ["hr"], "allowed_users": ["u_x"]}
    assert is_allowed(doc, user) is True


def test_build_filter_uses_groups_and_user_id():
    filt = build_filter(INTERN)
    assert isinstance(filt, models.Filter)
    assert filt.should is not None and len(filt.should) == 2

    group_cond, user_cond = filt.should
    assert group_cond.key == "allowed_groups"
    assert "all" in group_cond.match.any
    assert user_cond.key == "allowed_users"
    assert user_cond.match.any == ["u_int"]

    # By default the filter also requires the chunk to be the current version.
    assert filt.must is not None and len(filt.must) == 1
    assert filt.must[0].key == "is_current"
    assert filt.must[0].match.value is True


def test_build_filter_can_disable_current_only():
    filt = build_filter(INTERN, current_only=False)
    assert not filt.must
