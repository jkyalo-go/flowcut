from dataclasses import dataclass


@dataclass(frozen=True)
class RouterModule:
    prefix: str
    tags: list[str]
    router: object
