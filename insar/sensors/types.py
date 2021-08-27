from dataclasses import dataclass
from typing import List

@dataclass
class SensorMetadata:
    name: str
    constellation_name: str
    constellation_members: List[str]
    mean_altitude_km: float
    center_frequency_ghz: float
    polarisations: List[str]
