import re

SPACE_RE = re.compile(r"\s+")
NUM_RE = re.compile(r"\b\d+(?::\d{2})?(?:\.\d+)?\b")


def _clean(text: str) -> str:
    return SPACE_RE.sub(" ", (text or "").strip())


def _lower(text: str) -> str:
    return _clean(text).lower()


def _extract_numbers(text: str):
    return NUM_RE.findall(text or "")


def _first_sentence(text: str, max_words: int = 30) -> str:
    txt = _clean(text)
    if not txt:
        return ""

    parts = re.split(r"(?<=[.!?])\s+", txt)
    sent = parts[0] if parts else txt
    words = sent.split()
    if len(words) > max_words:
        sent = " ".join(words[:max_words]) + "..."
    return sent


def _context_label(text: str) -> str:
    low = _lower(text)

    if "flight duty" in low or "fdp" in low:
        return "flight duty period"
    if "flight time" in low:
        return "flight time"
    if "rest" in low and "standby" in low:
        return "rest after standby"
    if "rest" in low:
        return "rest requirement"
    if "standby" in low:
        return "standby limit"
    if "applicable" in low or "applicability" in low or "operators" in low:
        return "applicability"

    return "operational requirement"


def _sentence_case(text: str) -> str:
    text = _clean(text)
    if not text:
        return text
    return text[0].upper() + text[1:]


def _numeric_summary(old_text: str, new_text: str) -> str:
    old_nums = _extract_numbers(old_text)
    new_nums = _extract_numbers(new_text)

    old_set = set(old_nums)
    new_set = set(new_nums)

    removed = [n for n in old_nums if n not in new_set]
    added = [n for n in new_nums if n not in old_set]

    ctx = _context_label(f"{old_text} {new_text}")

    if removed and added:
        return f"The {ctx} has changed from {', '.join(removed)} to {', '.join(added)}."
    if added and not removed:
        return f"The {ctx} now includes {', '.join(added)}, which was not specified earlier."
    if removed and not added:
        return f"The {ctx} no longer includes {', '.join(removed)}."

    return "Operational numeric limits were revised."


def _applicability_summary(old_text: str, new_text: str) -> str:
    old_sent = _first_sentence(old_text)
    new_sent = _first_sentence(new_text)

    if old_sent and new_sent:
        return (
            "Applicability has been revised. "
            f"Earlier: {old_sent} Now: {new_sent}"
        )

    return "Applicability scope has changed for operators or operations covered by this rule."


def _added_summary(new_text: str) -> str:
    sent = _first_sentence(new_text)
    if sent:
        return f"A new operational requirement has been added: {sent}"
    return "A new operational requirement has been added."


def _removed_summary(old_text: str) -> str:
    sent = _first_sentence(old_text)
    if sent:
        return f"This operational requirement has been removed: {sent}"
    return "An existing operational requirement has been removed."


def _modified_summary(old_text: str, new_text: str) -> str:
    ctx = _context_label(f"{old_text} {new_text}")
    old_sent = _first_sentence(old_text)
    new_sent = _first_sentence(new_text)

    if old_sent and new_sent:
        return (
            f"The {ctx} has been revised. "
            f"Earlier: {old_sent} Now: {new_sent}"
        )

    return f"The {ctx} has been revised with operational impact."


def generate_change_summary(old_text: str, new_text: str, subtype: str) -> str:
    """
    Generate a concise, factual summary of the exact operational difference.
    Output is 1-3 sentences and avoids generic phrasing.
    """
    old_text = _clean(old_text)
    new_text = _clean(new_text)
    subtype = _clean(subtype)

    if subtype == "Numeric limit changed":
        summary = _numeric_summary(old_text, new_text)
    elif subtype == "Applicability changed":
        summary = _applicability_summary(old_text, new_text)
    elif subtype == "New rule added":
        summary = _added_summary(new_text)
    elif subtype == "Rule removed":
        summary = _removed_summary(old_text)
    else:
        summary = _modified_summary(old_text, new_text)

    return _sentence_case(summary)


def generate_summary(text):
    """
    Backward-compatible wrapper for older callers.
    """
    text = _clean(text)
    if not text:
        return "No substantive text available for summary."
    return _first_sentence(text)
