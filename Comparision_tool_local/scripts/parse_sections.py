import re
from scripts.meaning_block import build_meaning_block

# Numbered section headers, e.g. 12, 12.1, 3.4.2
SECTION_PATTERN = re.compile(r"^(?P<id>\d+(?:\.\d+)*)(?:[.)])?\s+(?P<title>.+)$")

# Unnumbered all-caps headers, e.g. INTRODUCTION
ALL_CAPS_PATTERN = re.compile(r"^[A-Z][A-Z0-9\s,\-:/()&']{4,}$")

TOC_LINE_PATTERN = re.compile(r"^\d+(?:\.\d+)*\s+.+\.{3,}\s+\d+\s*$")
PAGE_ONLY_PATTERN = re.compile(r"^page\s+\d+\s*$", re.I)


def _normalize_line(line: str) -> str:
    return re.sub(r"\s+", " ", line).strip()


def _is_noise(line: str) -> bool:
    if not line:
        return True

    low = line.lower()

    if PAGE_ONLY_PATTERN.match(line):
        return True
    if TOC_LINE_PATTERN.match(line):
        return True
    if "table of contents" in low:
        return True

    # Repeating document headers/footers from extracted text
    if low.startswith("dgca") and ("car" in low or "issue" in low or "dated" in low):
        return True

    return False


def _looks_like_heading_title(title: str) -> bool:
    if not title:
        return False

    if not re.search(r"[A-Za-z]", title):
        return False

    # Avoid classifying table row fragments as headings.
    if len(title) > 220:
        return False

    return True


def parse_sections(text: str):
    """
    Parse document text into structured sections.

    Output schema for each section:
    {
      "section": "6.1",
      "heading": "The maximum flight time ...",
      "body": "...",
      "meaning": "..."
    }
    """

    sections = {}

    current_section_id = None
    current_heading = None
    current_body = []

    synthetic_counter = 0

    for raw_line in text.splitlines():
        line = _normalize_line(raw_line)

        if _is_noise(line):
            continue

        numbered = SECTION_PATTERN.match(line)
        is_numbered_heading = False
        new_section_id = None
        new_heading = None

        if numbered:
            section_id = numbered.group("id")
            title = numbered.group("title").strip()

            if _looks_like_heading_title(title):
                is_numbered_heading = True
                new_section_id = section_id
                new_heading = title.rstrip(" .")

        is_caps_heading = False
        if not is_numbered_heading and ALL_CAPS_PATTERN.match(line):
            # Example in new doc: "INTRODUCTION" (without leading "1")
            synthetic_counter += 1
            is_caps_heading = True
            new_section_id = f"H{synthetic_counter}"
            new_heading = line.rstrip(" .")

        if is_numbered_heading or is_caps_heading:
            if current_section_id and current_heading:
                body = " ".join(current_body).strip()
                meaning = build_meaning_block(current_heading, body)
                sections[current_section_id] = {
                    "section": current_section_id,
                    "heading": current_heading,
                    "body": body,
                    "meaning": meaning,
                }

            current_section_id = new_section_id
            current_heading = new_heading
            current_body = []
            continue

        if current_section_id:
            current_body.append(line)

    if current_section_id and current_heading:
        body = " ".join(current_body).strip()
        meaning = build_meaning_block(current_heading, body)
        sections[current_section_id] = {
            "section": current_section_id,
            "heading": current_heading,
            "body": body,
            "meaning": meaning,
        }

    return sections
