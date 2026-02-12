import json, os, re, csv
from datetime import datetime, timezone

ISSUE_BODY = os.environ.get("ISSUE_BODY", "")
ISSUE_NUMBER = os.environ.get("ISSUE_NUMBER", "")
ISSUE_URL = os.environ.get("ISSUE_URL", "")

DATA_JSON = "data/words.json"
DATA_CSV = "data/words.csv"

def parse_field(label: str) -> str:
    # GitHub Issue form renders Markdown like:
    # ### Word
    # conflict
    pattern = rf"^### {re.escape(label)}\s*\n(.+?)(?=\n### |\Z)"
    m = re.search(pattern, ISSUE_BODY, flags=re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    val = m.group(1).strip()
    if val == "_No response_":
        return ""
    return val

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
    word = parse_field("Word").strip()
    if not word:
        raise SystemExit("Word is required but missing.")

    # Read incoming fields (may be empty => means 'no change' for updates)
    incoming_pos = parse_field("Part of speech").strip()
    incoming_other = parse_field("Other spelling (UK/US if different)").strip()
    incoming_pron = parse_field("Pronunciation (IPA etc.)").strip()
    incoming_meaning = parse_field("Meaning (Japanese)").strip()
    incoming_examples_raw = parse_field("Examples (one per line)")
    incoming_syn_raw = parse_field("Synonyms (comma-separated)")
    incoming_tags_raw = parse_field("Tags (comma-separated)")
    incoming_notes = parse_field("Notes").strip()

    incoming_examples = [l.strip() for l in incoming_examples_raw.splitlines() if l.strip()] if incoming_examples_raw.strip() else []
    incoming_synonyms = split_csv_like(incoming_syn_raw) if incoming_syn_raw.strip() else []
    incoming_tags = split_csv_like(incoming_tags_raw) if incoming_tags_raw.strip() else []

    items = load_json()
    idx = find_index(items, word)

    now_iso = datetime.now(timezone.utc).isoformat()
    source = ISSUE_URL or f"#{ISSUE_NUMBER}"

    if idx == -1:
        # New entry: require minimum fields
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
        # Update entry: only overwrite fields that are provided (non-empty)
        it = items[idx]

        # Always keep canonical word formatting as existing? We'll set to the provided word.
        it["word"] = word

        if incoming_pos:
            it["part_of_speech"] = incoming_pos
        if incoming_other:
            it["other_spelling"] = incoming_other
        if incoming_pron:
            it["pronunciation"] = incoming_pron
        if incoming_meaning:
            it["meaning_ja"] = incoming_meaning

        # Lists: only replace if provided
        if incoming_examples_raw.strip():
            it["examples"] = incoming_examples
        if incoming_syn_raw.strip():
            it["synonyms"] = incoming_synonyms
        if incoming_tags_raw.strip():
            it["tags"] = incoming_tags

        if incoming_notes:
            it["notes"] = incoming_notes

        # Keep created_at if exists, else set
        it["created_at"] = it.get("created_at") or now_iso

        # Update source_issue to the latest edit issue (handy for audit)
        it["source_issue"] = source

        items[idx] = it
        status = "updated"

    # sort by word
    items.sort(key=lambda x: x.get("word","").lower())
    save_json(items)
    save_csv(items)
    print(status)

if __name__ == "__main__":
    main()
