import re

# eBird subnational2 codes: country (2 alpha) + subnational1
# (alpha-or-num) + numeric county.
# Examples that must pass: US-CO-013, US-TX-453, MX-ROO-006, CA-ON-001
# Examples that must fail: US, US-CO, us-co-013, US-CO-ABC, US-CO-12345
_COUNTY_RE = re.compile(r"^[A-Z]{2}-[A-Z0-9]{1,3}-\d{1,4}$")


def is_county_region(code: str) -> bool:
    return bool(_COUNTY_RE.fullmatch(code))
