from models import ClipType
from config import TALKING_WORD_THRESHOLD


def classify(transcript: str) -> ClipType:
    word_count = len(transcript.split())
    if word_count >= TALKING_WORD_THRESHOLD:
        return ClipType.TALKING
    return ClipType.BROLL
