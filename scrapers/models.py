from dataclasses import dataclass, field

@dataclass(slots=True)
class Episode:
    id: str
    number: int
    title: str
    qualities: dict[str, str] = field(default_factory=dict)

@dataclass(slots=True)
class Anime:
    id: str
    title: str
    synopsis: str = ""
    episodes: list[Episode] = field(default_factory=list)
