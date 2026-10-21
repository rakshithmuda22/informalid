"""
core/models.py - Pydantic data models for the financial identity profile.
Pure data: no API calls, no side effects.

The same model is used three ways:
  * as the `input_schema` of the Claude extraction tool (via anthropic.transform_schema),
  * to validate whatever the model returns (ValidationError -> retry with feedback),
  * as the typed record the scheme matcher and card formatter consume.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

WorkType = Literal["self_employed", "wage_worker", "both"]


class _Strict(BaseModel):
    # Reject keys the schema does not define instead of silently dropping them.
    model_config = ConfigDict(extra="forbid")


class IncomeSource(_Strict):
    description: str = Field(..., description="What the person does to earn")
    frequency: Literal["daily", "weekly", "monthly", "seasonal"] = Field(
        ..., description="How often the money arrives"
    )
    estimated_monthly_inr: int = Field(..., ge=0, description="Estimated monthly income in INR")


class Asset(_Strict):
    item: str = Field(..., description="Name of the asset")
    estimated_value_inr: int = Field(..., ge=0, description="Rough market value in INR")


class FinancialProfile(_Strict):
    """
    A structured financial identity card generated from a conversational interview.
    No formal documents required as input - only what the person says.
    """
    full_name: str
    age: int = Field(..., ge=14, le=100)
    occupation: str
    years_in_occupation: int = Field(..., ge=0, le=80)
    work_type: WorkType = Field(
        ...,
        description=(
            "self_employed: runs own stall/shop/vehicle/craft and keeps the earnings; "
            "wage_worker: paid by employers or households; both: a mix"
        ),
    )

    # Income
    income_sources: list[IncomeSource]
    total_monthly_income_inr: int = Field(..., ge=0)
    monthly_expenses_inr: int = Field(..., ge=0)
    monthly_savings_inr: int = Field(..., ge=0)

    # Assets and formal-identity status
    assets: list[Asset]
    has_bank_account: bool
    has_aadhaar: bool
    has_mobile_phone: bool

    # Work history
    previous_occupations: list[str]
    skills: list[str]
    references_available: bool

    # Profile metadata
    location_city_or_area: str
    languages_spoken: list[str]

    # Narrative fields (written by the model from the transcript)
    summary_paragraph: str = Field(
        ..., description="2-sentence plain-English summary of this person's financial situation"
    )
    loan_readiness_note: str = Field(
        ...,
        description=(
            "One or two sentences on repayment capacity and formal-banking readiness. "
            "Do not name schemes or rupee limits; the scheme matcher does that."
        ),
    )

    @model_validator(mode="after")
    def _savings_cannot_exceed_income(self) -> "FinancialProfile":
        if self.monthly_savings_inr > self.total_monthly_income_inr:
            raise ValueError(
                f"monthly_savings_inr ({self.monthly_savings_inr}) is larger than "
                f"total_monthly_income_inr ({self.total_monthly_income_inr})"
            )
        return self
