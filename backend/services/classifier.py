from config import TALKING_WORD_THRESHOLD
from domain.shared import ClipType


def classify(transcript: str) -> ClipType:
    word_count = len(transcript.split())
    if word_count >= TALKING_WORD_THRESHOLD:
        return ClipType.TALKING
    return ClipType.BROLL
