from typing import TypedDict


class RegionResult(TypedDict, total=False):
    regionCode: str
    displayName: str
    description: str
