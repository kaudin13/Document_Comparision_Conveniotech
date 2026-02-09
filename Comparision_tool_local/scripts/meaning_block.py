import re
from typing import List

try:
    import spacy

    nlp = spacy.load("en_core_web_sm")
except Exception:
    nlp = None

MODAL_PATTERN = re.compile(r"\b(shall|must|may|required|not exceed|maximum|minimum)\b", re.I)
NUMBER_PATTERN = re.compile(r"\b\d+(?::\d{2})?(?:\.\d+)?\s*(hours?|hrs?|days?|landings?|minutes?|mins?)?\b", re.I)


def clean_text(text: str) -> str:
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        l = line.strip()
        if not l:
            continue

        low = l.lower()
        if "table of contents" in low:
            continue
        if low.startswith("page "):
            continue
        if low.startswith("dgca") and ("car" in low or "issue" in low):
            continue

        cleaned.append(l)

    return " ".join(cleaned)


def split_sentences(text: str) -> List[str]:
    if not text:
        return []

    if nlp is not None:
        return [s.text.strip() for s in nlp(text).sents if s.text.strip()]

    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]


def build_meaning_block(heading: str, body_text: str) -> str:
    cleaned = clean_text(body_text or "")
    if heading:
        cleaned = f"{heading.strip()}. {cleaned}".strip()

    important_sentences = []

    for sentence in split_sentences(cleaned):
        if MODAL_PATTERN.search(sentence) or NUMBER_PATTERN.search(sentence):
            important_sentences.append(sentence)

    if not important_sentences:
        return cleaned[:1200]

    return " ".join(important_sentences[:8])
