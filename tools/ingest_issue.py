import json, os, re, csv
from datetime import datetime, timezone

ISSUE_BODY = os.environ.get("ISSUE_BODY", "")
ISSUE_NUMBER = os.environ.get("ISSUE_NUMBER", "")
ISSUE_URL = os.environ.get("ISSUE_URL", "")

DATA_JSON = "data/words.json"
DATA_CSV = "data/words.csv"

def parse_field(label: str) -> str:
    """
    Parse a GitHub Issue Form field rendered in Markdown:
      ### Label
      value
    """
    pattern = rf"^### {re.escape(label)}\s*\n(.+?)(?=\n### |\Z)"
    m = re.search(pattern, ISSUE_BODY, flags=re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    val = m.group(1).strip()
    if val == "_No response_":
        return ""
    return val

def parse_any(labels):
    """Return first non-empty field among possible labels."""
    for lb in labels:
        v = parse_field(lb)
        if v.strip():
            return v
    return ""

def split_csv_like(s: str):
    parts = [p.strip() for p in s.split(",") if p.strip()]
    seen = set()
    out = []
    for p in parts:
        key = p.lower()
        if key not in seen:
            seen.add(key)
            out.append(p)
    return out

def load_json():
    if not os.path.exists(DATA_JSON):
        return []
    with open(DATA_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(items):
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)

def save_csv(items):
    fieldnames = [
        "word","part_of_speech",
        "other_spelling",
        "pronunciation","meaning_ja",
        "examples","synonyms","tags","notes",
        "mastery","last_reviewed","created_at","source_issue"
    ]
    with open(DATA_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for it in items:
            w.writerow({
                "word": it.get("word",""),
                "part_of_speech": it.get("part_of_speech",""),
                "other_spelling": it.get("other_spelling",""),
                "pronunciation": it.get("pronunciation",""),
                "meaning_ja": it.get("meaning_ja",""),
                "examples": " | ".join(it.get("examples",[])),
                "synonyms": " | ".join(it.get("synonyms",[])),
                "tags": " | ".join(it.get("tags",[])),
                "notes": it.get("notes",""),
                "mastery": it.get("mastery",0),
                "last_reviewed": it.get("last_reviewed",""),
                "created_at": it.get("created_at",""),
                "source_issue": it.get("source_issue",""),
            })

def find_index(items, word: str):
    key = (word or "").strip().lower()
    for i, it in enumerate(items):
        if (it.get("word","").strip().lower() == key):
            return i
    return -1

def main():
    # Accept both template variants (label text may differ over time)
    word = parse_any([
        "Word",
        "Word (must match existing)",
    ]).strip()
    if not word:
        raise SystemExit("Word is required but missing.")

    incoming_pos = parse_any([
        "Part of speech",
        "Part of Speech",
    ]).strip()

    incoming_other = parse_any([
        "Other spelling (UK/US if different)",
        "Other spelling (if different)",
        "Other spelling",
    ]).strip()

    incoming_pron = parse_any([
        "Pronunciation (IPA etc.)",
        "Pronunciation",
    ]).strip()

    incoming_meaning = parse_any([
        "Meaning (Japanese)",
        "Meaning (JP)",
        "Meaning",
    ]).strip()

    incoming_examples_raw = parse_any([
        "Examples (one per line)",
        "Examples",
    ])

    incoming_syn_raw = parse_any([
        "Synonyms (comma-separated)",
        "Synonyms",
    ])

    incoming_tags_raw = parse_any([
        "Tags (comma-separated)",
        "Tags",
    ])

    incoming_notes = parse_any([
        "Notes",
    ]).strip()

    incoming_examples = [l.strip() for l in incoming_examples_raw.splitlines() if l.strip()] if incoming_examples_raw.strip() else []
    incoming_synonyms = split_csv_like(incoming_syn_raw) if incoming_syn_raw.strip() else []
    incoming_tags = split_csv_like(incoming_tags_raw) if incoming_tags_raw.strip() else []

    items = load_json()
    idx = find_index(items, word)

    now_iso = datetime.now(timezone.utc).isoformat()
    source = ISSUE_URL or f"#{ISSUE_NUMBER}"

    if idx == -1:
        # New entry: require minimum information
        if not incoming_meaning:
            raise SystemExit("Meaning (Japanese) is required for a new word.")
        entry = {
            "word": word,
            "part_of_speech": incoming_pos,
            "other_spelling": incoming_other,
            "pronunciation": incoming_pron,
            "meaning_ja": incoming_meaning,
            "examples": incoming_examples,
            "synonyms": incoming_synonyms,
            "tags": incoming_tags,
            "notes": incoming_notes,
            "mastery": 0,
            "last_reviewed": "",
            "created_at": now_iso,
            "source_issue": source,
        }
        items.append(entry)
        status = "added"
    else:
        # Update entry: only apply non-empty fields; keep existing otherwise
        it = items[idx]

        # Keep canonical word (but normalize formatting)
        it["word"] = word

        if incoming_pos:
            it["part_of_speech"] = incoming_pos
        if incoming_other:
            it["other_spelling"] = incoming_other
        if incoming_pron:
            it["pronunciation"] = incoming_pron
        if incoming_meaning:
            it["meaning_ja"] = incoming_meaning

        # Lists: replace only if user provided something (including explicit empty lines not possible)
        if incoming_examples_raw.strip():
            it["examples"] = incoming_examples
        if incoming_syn_raw.strip():
            it["synonyms"] = incoming_synonyms
        if incoming_tags_raw.strip():
            it["tags"] = incoming_tags

        if incoming_notes:
            it["notes"] = incoming_notes

        it["created_at"] = it.get("created_at") or now_iso
        it["source_issue"] = source

        items[idx] = it
        status = "updated"

    items.sort(key=lambda x: x.get("word","").lower())
    save_json(items)
    save_csv(items)
    print(status)

if __name__ == "__main__":
    main()
