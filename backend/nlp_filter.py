import re
import spacy
from transformers import pipeline

# ── Load models once when the file is imported ──────────────────────────
print("Loading spaCy model...")
nlp = spacy.load("en_core_web_lg")

print("Loading HuggingFace classifier...")
classifier = pipeline("zero-shot-classification", model="facebook/bart-large-mnli")

print("All models loaded ✓")


# ── LAYER 1: Pattern Matching ────────────────────────────────────────────
PATTERNS = {
    "openai_key": r"sk-[a-zA-Z0-9-_]{10,}",
    "aws_key":       r"AKIA[0-9A-Z]{16}",
    "db_connection": r"(mongodb|postgresql|mysql):\/\/[^\s]+",
    "jwt_token":     r"eyJ[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+",
    "private_key":   r"-----BEGIN (RSA |EC )?PRIVATE KEY-----",
    "ip_address":    r"\b(?:\d{1,3}\.){3}\d{1,3}\b",

    # ADD THESE:
    "source_code":   r"def |class |import |SELECT |DROP TABLE|<\?php",
    "internal_hint": r"internal|confidential|proprietary|secret|private",
}

def pattern_scan(prompt: str) -> dict:
    hits = {}
    for name, pattern in PATTERNS.items():
        if re.search(pattern, prompt):
            hits[name] = True
    return hits


# ── LAYER 2: Named Entity Recognition ───────────────────────────────────
SENSITIVE_ENTITIES = {"ORG", "PERSON", "GPE", "PRODUCT", "MONEY"}

def ner_scan(prompt: str) -> list:
    doc = nlp(prompt)
    found = []
    for ent in doc.ents:
        if ent.label_ in SENSITIVE_ENTITIES:
            found.append({
                "text": ent.text,
                "type": ent.label_
            })
    return found


# ── LAYER 3: Semantic Classification ────────────────────────────────────
SENSITIVE_LABELS = [
    "proprietary source code",
    "internal business document",
    "confidential employee information",
    "trade secret or intellectual property",
    "internal financial data",
]
SAFE_LABELS = [
    "general knowledge question",
    "public information",
]

def semantic_scan(prompt: str) -> dict:
    all_labels = SENSITIVE_LABELS + SAFE_LABELS
    result = classifier(prompt, all_labels)
    return {
        "label":      result["labels"][0],
        "confidence": result["scores"][0]
    }


# ── COMBINING INTO A LEAK SCORE ──────────────────────────────────────────
BLOCK_THRESHOLD = 30

def compute_leak_score(prompt: str) -> dict:
    score   = 0
    reasons = []

    # Layer 1 — Regex (weight: up to 60)
    patterns_found = pattern_scan(prompt)
    if patterns_found:
        score += 60
        reasons.append(f"Sensitive pattern detected: {list(patterns_found.keys())}")

    # Layer 2 — NER (weight: up to 20)
    entities  = ner_scan(prompt)
    org_count = sum(1 for e in entities if e["type"] == "ORG")
    if org_count:
        added = min(org_count * 10, 20)
        score += added
        reasons.append(f"Organisation names found: {org_count}")

    # Layer 3 — Semantic (weight: up to 30)
    semantic = semantic_scan(prompt)
    if semantic["label"] not in SAFE_LABELS:
        added = int(semantic["confidence"] * 30)
        score += added
        reasons.append(
            f"Semantic risk: '{semantic['label']}' "
            f"({semantic['confidence']:.0%} confidence)"
        )

    return {
        "score":    min(score, 100),
        "reasons":  reasons,
        "entities": entities,
        "semantic": semantic,
    }


def should_block(prompt: str) -> tuple:
    analysis = compute_leak_score(prompt)
    blocked  = analysis["score"] >= BLOCK_THRESHOLD
    return blocked, analysis