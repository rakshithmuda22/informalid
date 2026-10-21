"""FinancialProfile: validation rules and the tool schema derived from it."""
import json

import anthropic
import pytest
from pydantic import ValidationError

from core.mock import MEENA, RAMESH
from core.models import FinancialProfile


def _data(**overrides) -> dict:
    data = MEENA.profile.model_dump(mode="json")
    data.update(overrides)
    return data


def test_persona_profiles_are_valid():
    assert isinstance(MEENA.profile, FinancialProfile)
    assert isinstance(RAMESH.profile, FinancialProfile)


def test_json_roundtrip():
    restored = FinancialProfile.model_validate_json(MEENA.profile.model_dump_json())
    assert restored == MEENA.profile


@pytest.mark.parametrize("age", [13, 101])
def test_age_out_of_range_rejected(age):
    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(_data(age=age))


@pytest.mark.parametrize("field", ["total_monthly_income_inr", "monthly_expenses_inr", "monthly_savings_inr"])
def test_negative_money_rejected(field):
    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(_data(**{field: -1}))


def test_savings_cannot_exceed_income():
    with pytest.raises(ValidationError, match="larger than"):
        FinancialProfile.model_validate(_data(monthly_savings_inr=9001))


def test_unknown_work_type_rejected():
    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(_data(work_type="freelancer"))


def test_unknown_frequency_rejected():
    data = _data()
    data["income_sources"][0]["frequency"] = "whenever"
    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(data)


def test_extra_keys_rejected():
    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(_data(credit_score=700))


def test_string_amount_rejected():
    with pytest.raises(ValidationError):
        FinancialProfile.model_validate(_data(total_monthly_income_inr="nine thousand"))


def test_income_math_in_personas():
    for p in (MEENA.profile, RAMESH.profile):
        assert p.total_monthly_income_inr == sum(s.estimated_monthly_inr for s in p.income_sources)
        assert abs(p.total_monthly_income_inr - p.monthly_expenses_inr - p.monthly_savings_inr) <= 1000


def _objects(schema):
    """Yield every object-typed subschema."""
    if isinstance(schema, dict):
        if schema.get("type") == "object":
            yield schema
        for value in schema.values():
            yield from _objects(value)
    elif isinstance(schema, list):
        for value in schema:
            yield from _objects(value)


def test_tool_schema_is_strict_compatible():
    schema = anthropic.transform_schema(FinancialProfile)
    objects = list(_objects(schema))
    assert len(objects) >= 3  # profile, IncomeSource, Asset
    assert all(o.get("additionalProperties") is False for o in objects)
    assert set(schema["required"]) == set(FinancialProfile.model_fields)
    json.dumps(schema)  # serialisable
