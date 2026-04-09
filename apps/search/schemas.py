from typing import TypedDict


class Sighting(TypedDict, total=False):
    locationName: str
    dateTime: str
    checklistUrl: str
    googleMapsUrl: str


class Species(TypedDict, total=False):
    commonName: str
    scientificName: str
    allAboutBirdsUrl: str
    sightings: list[Sighting]
