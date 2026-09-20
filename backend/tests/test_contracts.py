"""
Unit tests for Fallow Pydantic contracts and invariants.
"""

import pytest
from pydantic import ValidationError

from app.contracts import (
    FarmerProfile,
    IrrigationAccess,
    Season,
    ForecastResult,
    Confidence,
    Claim,
    CropOption,
    Viability,
    Advisory,
    RetrievedPassage,
)


def test_farmer_profile_validation():
    """FarmerProfile enforces required fields and constraints."""
    profile = FarmerProfile(
        district_id="IN-MH-AUR",
        district_name="Aurangabad",
        land_size_acres=3.5,
        irrigation_access=IrrigationAccess.RAINFED,
        crop_history=["cotton", "bajra"],
        season=Season.KHARIF,
        language="mr",
    )
    assert profile.land_size_acres == 3.5
    assert profile.district_id == "IN-MH-AUR"

    # Land size must be positive
    with pytest.raises(ValidationError):
        FarmerProfile(
            district_id="IN-MH-AUR",
            district_name="Aurangabad",
            land_size_acres=-1.0,
            irrigation_access=IrrigationAccess.RAINFED,
            season=Season.KHARIF,
        )


def test_claim_enforces_non_empty_citations():
    """ORC-2: Claims MUST have non-empty citation_ids."""
    # Valid claim
    claim = Claim(statement="Bajra requires 350mm water.", citation_ids=["P-1001"])
    assert len(claim.citation_ids) == 1

    # Empty citations rejected at Claim level
    with pytest.raises(ValidationError):
        Claim(statement="No citation here.", citation_ids=[])


def test_advisory_rejects_empty_crop_claim_citations():
    """ORC-2: Advisory validator blocks empty citation lists in CropOption rationale."""
    passage = RetrievedPassage(
        passage_id="P-001",
        text="Test agronomic guidance",
        relevance_score=0.9,
        doc_title="Dryland Farming",
        publishing_body="ICAR",
        source_uri="https://icar.org.in/guide.pdf",
    )

    farmer = FarmerProfile(
        district_id="IN-MH-AUR",
        district_name="Aurangabad",
        land_size_acres=2.0,
        irrigation_access=IrrigationAccess.RAINFED,
        season=Season.KHARIF,
    )

    forecast = ForecastResult(
        district_id="IN-MH-AUR",
        season="kharif",
        projected_rainfall_mm=450.0,
        historical_mean_mm=700.0,
        deviation_pct=-35.7,
        confidence=Confidence.MEDIUM,
        anomaly_flag=True,
        baseline_years=15,
    )

    # Valid advisory
    adv = Advisory(
        farmer=farmer,
        forecast=forecast,
        recommended=[
            CropOption(
                crop="bajra",
                rank=1,
                rationale=[Claim(statement="High drought tolerance", citation_ids=["P-001"])],
                expected_viability=Viability.GOOD,
            )
        ],
        irrigation_guidance=[
            Claim(statement="Mulching conserves moisture", citation_ids=["P-001"])
        ],
        citations={"P-001": passage},
    )
    assert len(adv.recommended) == 1
