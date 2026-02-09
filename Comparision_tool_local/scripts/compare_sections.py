import re
from itertools import count

from scripts.semantic_utils import lexical_similarity, semantic_similarity

NUMBER_PATTERN = re.compile(r"\b\d+(?::\d{2})?(?:\.\d+)?\b")
SPACE_RE = re.compile(r"\s+")
TIME_OR_UNIT_PATTERN = re.compile(
    r"\b\d+(?::\d{2})?(?:\.\d+)?\s*(hours?|hrs?|days?|landings?|sectors?|minutes?|mins?|kg|auw)?\b",
    re.I,
)

REGULATORY_TERMS = {
    "shall",
    "must",
    "required",
    "limit",
    "maximum",
    "minimum",
    "rest",
    "flight",
    "duty",
    "crew",
    "operator",
    "standby",
    "landing",
    "applicable",
    "applicability",
    "fdtl",
    "dgca",
    "not exceed",
}

SCOPE_TERMS = {
    "applicable",
    "applicability",
    "all operators",
    "scheduled",
    "non-scheduled",
    "general aviation",
    "private",
    "public sector",
    "state governments",
    "except",
    "only",
}

OPS_NUMERIC_TERMS = {
    "flight time",
    "flight duty",
    "fdp",
    "rest",
    "standby",
    "weekly rest",
    "landings",
    "sectors",
    "wocl",
    "applicable",
    "auw",
    "maximum",
    "minimum",
    "not exceed",
}

NOISE_PHRASES = {
    "table of contents",
    "page",
    "issue",
    "dated",
    "effective",
    "dgca - car",
    "car -",
}

_change_id_gen = count(1)


def _normalize(text: str) -> str:
    return SPACE_RE.sub(" ", (text or "").strip().lower())


def _comparison_text(section: dict) -> str:
    return (section.get("meaning") or section.get("body") or section.get("heading") or "").strip()


def _extract_numbers(text: str):
    return set(NUMBER_PATTERN.findall(text or ""))


def _remove_numbers(text: str) -> str:
    return NUMBER_PATTERN.sub(" ", text or "")


def _numeric_delta(old_text: str, new_text: str):
    old_nums = _extract_numbers(old_text)
    new_nums = _extract_numbers(new_text)
    return sorted(new_nums - old_nums), sorted(old_nums - new_nums)


def _contains_regulatory_signal(text: str) -> bool:
    low = _normalize(text)
    return any(term in low for term in REGULATORY_TERMS)


def _contains_scope_signal(text: str) -> bool:
    low = _normalize(text)
    return any(term in low for term in SCOPE_TERMS)


def _is_substantive_rule(text: str) -> bool:
    low = _normalize(text)
    if len(low) < 45:
        return False
    if len(low.split()) < 8:
        return False
    return _contains_regulatory_signal(low) or bool(TIME_OR_UNIT_PATTERN.search(low))


def _looks_like_noise(text: str) -> bool:
    if not text:
        return True

    low = _normalize(text)

    if len(low) < 8:
        return True

    if any(p in low for p in NOISE_PHRASES) and not _contains_regulatory_signal(low):
        return True

    letters = sum(ch.isalpha() for ch in low)
    digits = sum(ch.isdigit() for ch in low)
    if letters == 0:
        return True

    symbols = max(0, len(low) - letters - digits - low.count(" "))
    if symbols > letters * 0.7:
        return True

    if letters < 6 and digits > 0:
        return True

    return False


def _is_operational_numeric_change(old_text: str, new_text: str) -> bool:
    old_nums = _extract_numbers(old_text)
    new_nums = _extract_numbers(new_text)
    if old_nums == new_nums:
        return False

    combined = _normalize(f"{old_text} {new_text}")

    if all(x.count(".") >= 1 and ":" not in x for x in (old_nums ^ new_nums)):
        if any(w in combined for w in ["para", "sub para", "section", "table"]):
            return False

    has_ops_context = any(term in combined for term in OPS_NUMERIC_TERMS)
    has_unit_or_time = bool(TIME_OR_UNIT_PATTERN.search(combined))

    return has_ops_context and has_unit_or_time


def _severity_from_text(change_type: str, subtype: str, old_text: str, new_text: str) -> str:
    combined = f"{old_text} {new_text}".lower()

    if change_type == "NOISE":
        return "MINOR"

    if subtype in {"Numeric limit changed", "Applicability changed"}:
        return "CRITICAL"

    if subtype in {"Rule removed", "New rule added"}:
        return "CRITICAL" if _is_substantive_rule(f"{old_text} {new_text}") else "MODERATE"

    if any(k in combined for k in ["shall not", "must", "not exceed", "maximum", "minimum"]):
        return "CRITICAL"

    if change_type == "TRUE_CHANGE":
        return "MODERATE"

    return "MINOR"


def _pair_score(old_sec: dict, new_sec: dict) -> float:
    old_heading = old_sec.get("heading", "")
    new_heading = new_sec.get("heading", "")

    old_text = _comparison_text(old_sec)
    new_text = _comparison_text(new_sec)

    heading_score = lexical_similarity(old_heading, new_heading)
    meaning_score = semantic_similarity(old_text, new_text)
    body_score = lexical_similarity(old_sec.get("body", ""), new_sec.get("body", ""))

    return 0.25 * heading_score + 0.65 * meaning_score + 0.10 * body_score


def _best_persistence_match(section, candidates):
    base_text = _comparison_text(section)
    base_heading = section.get("heading", "")

    best_id = None
    best_sem = -1.0
    best_head = -1.0
    best_combo = -1.0

    for cid, cand in candidates.items():
        cand_text = _comparison_text(cand)
        cand_heading = cand.get("heading", "")

        sem = semantic_similarity(base_text, cand_text)
        head = lexical_similarity(base_heading, cand_heading)
        combo = 0.75 * sem + 0.25 * head

        if combo > best_combo:
            best_combo = combo
            best_sem = sem
            best_head = head
            best_id = cid

    return best_id, best_sem, best_head, best_combo


def _build_change(old_sec, new_sec, ctype, severity, subtype, description, why, score=0.0):
    old_section = old_sec.get("section", "") if old_sec else ""
    new_section = new_sec.get("section", "") if new_sec else ""
    old_text = _comparison_text(old_sec or {})
    new_text = _comparison_text(new_sec or {})
    topic = (new_sec or old_sec or {}).get("heading", "")
    added, removed = _numeric_delta(old_text, new_text)

    return {
        "change_id": f"C{next(_change_id_gen):04d}",
        "type": ctype,
        "subtype": subtype,
        "severity": severity,
        "old_section": old_section,
        "new_section": new_section,
        "description": description,
        "why_it_is_a_change": why,
        "section": new_section or old_section,
        "section_old": old_section,
        "section_new": new_section,
        "topic": topic or old_section or new_section,
        "change_type": subtype,
        "old_text": old_text,
        "new_text": new_text,
        "similarity_score": round(score, 3),
        "numeric_delta": {"added": added, "removed": removed},
    }


def _classify_matched_change(old_sec, new_sec, score, unchanged_threshold=0.95):
    old_text = _comparison_text(old_sec)
    new_text = _comparison_text(new_sec)

    old_norm = _normalize(old_text)
    new_norm = _normalize(new_text)

    heading_sim = lexical_similarity(old_sec.get("heading", ""), new_sec.get("heading", ""))
    text_sim = semantic_similarity(old_text, new_text)

    if old_norm == new_norm or score >= unchanged_threshold:
        if old_sec.get("section") != new_sec.get("section"):
            return _build_change(
                old_sec,
                new_sec,
                "STRUCTURAL_CHANGE",
                "MINOR",
                "STRUCTURAL_MOVE",
                "Section was renumbered/moved.",
                "Rule text is materially the same; only numbering/location changed.",
                score,
            )
        return None

    if _looks_like_noise(old_text) and _looks_like_noise(new_text):
        return _build_change(
            old_sec,
            new_sec,
            "NOISE",
            "MINOR",
            "OCR/Parsing artifact",
            "Detected non-regulatory noisy text.",
            "Both sides look like OCR/header/footer artifacts.",
            score,
        )

    if heading_sim < 0.90 and text_sim >= 0.93:
        return _build_change(
            old_sec,
            new_sec,
            "STRUCTURAL_CHANGE",
            "MINOR",
            "Heading changes",
            "Heading wording/format changed with same rule content.",
            "Body meaning is effectively unchanged.",
            score,
        )

    if old_sec.get("section") != new_sec.get("section") and text_sim >= 0.90:
        return _build_change(
            old_sec,
            new_sec,
            "STRUCTURAL_CHANGE",
            "MINOR",
            "STRUCTURAL_MOVE",
            "Content moved/renumbered.",
            "High semantic equivalence indicates identical rule relocated.",
            score,
        )

    if _is_operational_numeric_change(old_text, new_text):
        no_num_sim = semantic_similarity(_remove_numbers(old_text), _remove_numbers(new_text))
        if no_num_sim >= 0.84:
            subtype = "Numeric limit changed"
            sev = _severity_from_text("TRUE_CHANGE", subtype, old_text, new_text)
            return _build_change(
                old_sec,
                new_sec,
                "TRUE_CHANGE",
                sev,
                subtype,
                "Numeric operational limit changed.",
                "Operational context is same while enforceable numeric values differ.",
                score,
            )

    if _contains_scope_signal(old_text) or _contains_scope_signal(new_text):
        if text_sim < 0.84:
            subtype = "Applicability changed"
            sev = _severity_from_text("TRUE_CHANGE", subtype, old_text, new_text)
            return _build_change(
                old_sec,
                new_sec,
                "TRUE_CHANGE",
                sev,
                subtype,
                "Applicability/scope language changed.",
                "Operator categories or scope boundaries materially differ.",
                score,
            )

    if _contains_regulatory_signal(old_text) or _contains_regulatory_signal(new_text):
        if text_sim < 0.66 and (_is_substantive_rule(old_text) or _is_substantive_rule(new_text)):
            subtype = "Operational requirement changed"
            sev = _severity_from_text("TRUE_CHANGE", subtype, old_text, new_text)
            return _build_change(
                old_sec,
                new_sec,
                "TRUE_CHANGE",
                sev,
                subtype,
                "Operational requirement text changed.",
                "Pilot/operator action could change due to semantic requirement difference.",
                score,
            )

    return _build_change(
        old_sec,
        new_sec,
        "SEMANTIC_MINOR",
        "MINOR",
        "Clarification without rule change",
        "Wording/clarity changes detected.",
        "Difference appears non-operational or uncertain.",
        score,
    )


def _classify_unmatched_old(old_sec, new_sections, relocation_threshold=0.78):
    old_text = _comparison_text(old_sec)

    if _looks_like_noise(old_text):
        return _build_change(
            old_sec,
            None,
            "NOISE",
            "MINOR",
            "Non-regulatory text",
            "Removed noisy/non-regulatory segment.",
            "Text resembles metadata/header/footer/OCR noise.",
        )

    best_id, sem, head, combo = _best_persistence_match(old_sec, new_sections)
    if best_id is not None and (combo >= relocation_threshold or sem >= 0.80 or head >= 0.88):
        return _build_change(
            old_sec,
            new_sections[best_id],
            "STRUCTURAL_CHANGE",
            "MINOR",
            "MOVED_RULE",
            "Rule moved/renumbered with same meaning.",
            "Semantically equivalent rule exists elsewhere in new document.",
            combo,
        )

    if not _is_substantive_rule(old_text):
        return _build_change(
            old_sec,
            None,
            "SEMANTIC_MINOR",
            "MINOR",
            "Possible structural split/merge",
            "Small unmatched fragment likely due to structure changes.",
            "No strong evidence of operational requirement removal.",
            combo if best_id else 0.0,
        )

    subtype = "Rule removed"
    sev = _severity_from_text("TRUE_CHANGE", subtype, old_text, "")
    return _build_change(
        old_sec,
        None,
        "TRUE_CHANGE",
        sev,
        subtype,
        "A previously present rule is missing in new document.",
        "No semantically equivalent rule found across the new document.",
    )


def _classify_unmatched_new(new_sec, old_sections, relocation_threshold=0.78):
    new_text = _comparison_text(new_sec)

    if _looks_like_noise(new_text):
        return _build_change(
            None,
            new_sec,
            "NOISE",
            "MINOR",
            "Non-regulatory text",
            "Added noisy/non-regulatory segment.",
            "Text resembles metadata/header/footer/OCR noise.",
        )

    best_id, sem, head, combo = _best_persistence_match(new_sec, old_sections)
    if best_id is not None and (combo >= relocation_threshold or sem >= 0.80 or head >= 0.88):
        return _build_change(
            old_sections[best_id],
            new_sec,
            "STRUCTURAL_CHANGE",
            "MINOR",
            "MOVED_RULE",
            "Rule moved/renumbered with same meaning.",
            "Semantically equivalent rule exists elsewhere in old document.",
            combo,
        )

    if not _is_substantive_rule(new_text):
        return _build_change(
            None,
            new_sec,
            "SEMANTIC_MINOR",
            "MINOR",
            "Possible structural split/merge",
            "Small unmatched fragment likely due to structure changes.",
            "No strong evidence of operational requirement addition.",
            combo if best_id else 0.0,
        )

    subtype = "New rule added"
    sev = _severity_from_text("TRUE_CHANGE", subtype, "", new_text)
    return _build_change(
        None,
        new_sec,
        "TRUE_CHANGE",
        sev,
        subtype,
        "A new rule appears in the updated document.",
        "No semantically equivalent predecessor found across the old document.",
    )


def _operational_impact_pass(changes):
    out = []
    for ch in changes:
        if ch.get("type") != "TRUE_CHANGE":
            out.append(ch)
            continue

        subtype = ch.get("subtype", "")
        old_text = ch.get("old_text", "")
        new_text = ch.get("new_text", "")

        if subtype in {"Numeric limit changed", "Applicability changed"}:
            out.append(ch)
            continue

        if subtype in {"Rule removed", "New rule added"} and _is_substantive_rule(f"{old_text} {new_text}"):
            out.append(ch)
            continue

        sim = semantic_similarity(old_text, new_text)
        if sim < 0.64 and (_is_substantive_rule(old_text) or _is_substantive_rule(new_text)):
            out.append(ch)
            continue

        ch["type"] = "SEMANTIC_MINOR"
        ch["subtype"] = "Clarification without rule change"
        ch["change_type"] = ch["subtype"]
        ch["severity"] = "MINOR"
        ch["description"] = "Difference appears non-operational after validation pass."
        ch["why_it_is_a_change"] = "Second-pass filter: no clear operator action change detected."
        out.append(ch)

    return out


def _dedupe_by_topic(changes):
    deduped = []
    for ch in changes:
        merged = False
        topic_a = _normalize(ch.get("topic", ""))
        type_a = ch.get("type", "")
        sub_a = ch.get("subtype", "")

        for ex in deduped:
            topic_b = _normalize(ex.get("topic", ""))
            same_type = ex.get("type") == type_a and ex.get("subtype") == sub_a
            topic_sim = lexical_similarity(topic_a, topic_b)
            text_sim = semantic_similarity(
                f"{ch.get('old_text','')} {ch.get('new_text','')}",
                f"{ex.get('old_text','')} {ex.get('new_text','')}",
            )

            if same_type and (topic_sim >= 0.92 or text_sim >= 0.94):
                ex_old = {s for s in [ex.get("old_section", ""), ch.get("old_section", "")] if s}
                ex_new = {s for s in [ex.get("new_section", ""), ch.get("new_section", "")] if s}
                ex["old_section"] = ",".join(sorted(ex_old))
                ex["new_section"] = ",".join(sorted(ex_new))
                ex["section_old"] = ex["old_section"]
                ex["section_new"] = ex["new_section"]
                ex["section"] = ex["new_section"] or ex["old_section"]
                ex["similarity_score"] = max(ex.get("similarity_score", 0.0), ch.get("similarity_score", 0.0))
                merged = True
                break

        if not merged:
            deduped.append(ch)

    return deduped


def _true_change_confidence(ch):
    subtype = ch.get("subtype", "")
    text = f"{ch.get('old_text','')} {ch.get('new_text','')}"
    sim = float(ch.get("similarity_score", 0.0))

    if subtype == "Numeric limit changed":
        return 1.0
    if subtype == "Applicability changed":
        return 0.95

    score = 0.40
    if _is_substantive_rule(text):
        score += 0.25
    if _contains_regulatory_signal(text):
        score += 0.20
    if TIME_OR_UNIT_PATTERN.search(text):
        score += 0.10
    score += max(0.0, 0.1 - sim * 0.05)
    return min(1.0, score)


def _cap_over_detection(changes, max_true_changes=35):
    true_changes = [c for c in changes if c.get("type") == "TRUE_CHANGE"]
    if len(true_changes) <= 50:
        return changes

    ranked = sorted(true_changes, key=_true_change_confidence, reverse=True)
    keep_ids = {c.get("change_id") for c in ranked[:max_true_changes]}

    adjusted = []
    for ch in changes:
        if ch.get("type") != "TRUE_CHANGE":
            adjusted.append(ch)
            continue

        if ch.get("change_id") in keep_ids:
            adjusted.append(ch)
            continue

        ch["type"] = "SEMANTIC_MINOR"
        ch["subtype"] = "Clarification without rule change"
        ch["change_type"] = ch["subtype"]
        ch["severity"] = "MINOR"
        ch["description"] = "Auto-tightened due to high TRUE_CHANGE volume."
        ch["why_it_is_a_change"] = "Low confidence compared with stronger operational changes."
        adjusted.append(ch)

    return adjusted


def _validate_changes(changes, strict_mode=True, include_non_true=False):
    validated = _operational_impact_pass(changes)
    validated = _dedupe_by_topic(validated)
    validated = _cap_over_detection(validated)

    out = []
    for ch in validated:
        ctype = ch.get("type")
        if ctype == "NOISE":
            continue
        if strict_mode and not include_non_true and ctype != "TRUE_CHANGE":
            continue
        out.append(ch)
    return out


def compare_sections(
    old_sections,
    new_sections,
    match_threshold=0.58,
    heading_fallback_threshold=0.82,
    relocation_threshold=0.78,
    strict_mode=True,
    include_non_true=False,
):
    """
    Legal-diff style section-independent comparison.

    Returns strict change objects with fields:
    CHANGE_ID/TYPE/SEVERITY/OLD_SECTION/NEW_SECTION/DESCRIPTION/WHY_IT_IS_A_CHANGE
    plus backward-compatible fields used by app.py.
    """
    changes = []

    old_ids = list(old_sections.keys())
    new_ids = list(new_sections.keys())

    for oid in old_ids:
        old_sections[oid]["section"] = oid
    for nid in new_ids:
        new_sections[nid]["section"] = nid

    scored_pairs = []
    for oid in old_ids:
        for nid in new_ids:
            scored_pairs.append((_pair_score(old_sections[oid], new_sections[nid]), oid, nid))
    scored_pairs.sort(reverse=True, key=lambda x: x[0])

    matched_old = set()
    matched_new = set()
    matches = []

    for score, oid, nid in scored_pairs:
        if score < match_threshold:
            break
        if oid in matched_old or nid in matched_new:
            continue
        matched_old.add(oid)
        matched_new.add(nid)
        matches.append((oid, nid, score))

    heading_pairs = []
    for oid in old_ids:
        if oid in matched_old:
            continue
        for nid in new_ids:
            if nid in matched_new:
                continue
            hs = lexical_similarity(old_sections[oid].get("heading", ""), new_sections[nid].get("heading", ""))
            heading_pairs.append((hs, oid, nid))
    heading_pairs.sort(reverse=True, key=lambda x: x[0])

    for hs, oid, nid in heading_pairs:
        if hs < heading_fallback_threshold:
            break
        if oid in matched_old or nid in matched_new:
            continue
        matched_old.add(oid)
        matched_new.add(nid)
        matches.append((oid, nid, hs * 0.92))

    for oid, nid, score in matches:
        c = _classify_matched_change(old_sections[oid], new_sections[nid], score)
        if c:
            changes.append(c)

    for oid in old_ids:
        if oid not in matched_old:
            changes.append(_classify_unmatched_old(old_sections[oid], new_sections, relocation_threshold=relocation_threshold))

    for nid in new_ids:
        if nid not in matched_new:
            changes.append(_classify_unmatched_new(new_sections[nid], old_sections, relocation_threshold=relocation_threshold))

    changes = _validate_changes(changes, strict_mode=strict_mode, include_non_true=include_non_true)

    severity_rank = {"CRITICAL": 0, "MODERATE": 1, "MINOR": 2}
    changes.sort(key=lambda c: (severity_rank.get(c.get("severity"), 3), c.get("change_id", "")))

    return changes
