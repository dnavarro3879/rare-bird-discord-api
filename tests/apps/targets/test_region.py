import pytest

from apps.targets.region import is_county_region


@pytest.mark.parametrize(
    "code",
    [
        "US-CO-013",
        "US-TX-453",
        "MX-ROO-006",
        "CA-ON-001",
        "US-NY-9999",  # four-digit county still accepted
    ],
)
def test_is_county_region_accepts_valid_codes(code: str) -> None:
    assert is_county_region(code) is True


@pytest.mark.parametrize(
    "code",
    [
        "US",
        "US-CO",
        "us-co-013",
        "US-CO-ABC",
        "US-CO-12345",  # too many county digits
        "",
        "  ",
        "US-CO-",
        "US--013",
        "USA-CO-013",  # country too long
        "U-CO-013",  # country too short
        "US-CO-013-1",  # trailing extra segment
    ],
)
def test_is_county_region_rejects_invalid_codes(code: str) -> None:
    assert is_county_region(code) is False
