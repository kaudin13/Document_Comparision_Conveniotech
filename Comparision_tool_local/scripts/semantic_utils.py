import os
import re
from difflib import SequenceMatcher
from functools import lru_cache

TOKEN_RE = re.compile(r"[a-z0-9]+")
SPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    text = (text or "").lower().strip()
    return SPACE_RE.sub(" ", text)


def tokenize(text: str):
    return TOKEN_RE.findall(normalize_text(text))


def jaccard_similarity(text_a: str, text_b: str) -> float:
    a = set(tokenize(text_a))
    b = set(tokenize(text_b))

    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    return len(a & b) / len(a | b)


def lexical_similarity(text_a: str, text_b: str) -> float:
    a = normalize_text(text_a)
    b = normalize_text(text_b)

    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0

    ratio = SequenceMatcher(None, a, b).ratio()
    jac = jaccard_similarity(a, b)
    return 0.55 * ratio + 0.45 * jac


@lru_cache(maxsize=1)
def _get_embedder():
    """
    Optional sentence-transformer loader.
    Disabled by default to keep runtime deterministic/offline-friendly.
    Enable with: ENABLE_EMBEDDINGS=1
    """
    if os.getenv("ENABLE_EMBEDDINGS", "0") != "1":
        return None

    model_name = os.getenv("SEMANTIC_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

    try:
        from sentence_transformers import SentenceTransformer

        return SentenceTransformer(model_name)
    except Exception:
        return None


def _embedding_similarity(text_a: str, text_b: str):
    model = _get_embedder()
    if model is None:
        return None

    try:
        vectors = model.encode([text_a, text_b], convert_to_numpy=True, normalize_embeddings=True)
        score = float((vectors[0] * vectors[1]).sum())
        return max(0.0, min(1.0, score))
    except Exception:
        return None


def semantic_similarity(text_a: str, text_b: str) -> float:
    """
    Semantic similarity in [0, 1].
    Uses transformer embeddings when enabled and available; otherwise lexical fallback.
    """
    text_a = (text_a or "").strip()
    text_b = (text_b or "").strip()

    if not text_a and not text_b:
        return 1.0
    if not text_a or not text_b:
        return 0.0

    emb_score = _embedding_similarity(text_a, text_b)
    lex_score = lexical_similarity(text_a, text_b)

    if emb_score is None:
        return lex_score

    return 0.75 * emb_score + 0.25 * lex_score
