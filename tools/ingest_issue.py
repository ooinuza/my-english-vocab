import json, os, re, csv
from datetime import datetime, timezone

ISSUE_BODY = os.environ.get("ISSUE_BODY", "")
ISSUE_NUMBER = os.environ.get("ISSUE_NUMBER", "")
ISSUE_URL = os.environ.get("ISSUE_URL", "")

DATA_JSON = "data/words.json"
DATA_CSV = "data/words.csv"

def parse_field(label: str) -> str:
    # GitHub Issue form renders as Markdown like:
    # ### Word
    # generate
    pattern = rf"^### {re.escape(label)}\s*\n(.+?)(?=\n### |\Z)"
    m = re.search(pattern, ISSUE_BODY, flags=re.MULTILINE | re.DOTALL)
    if not m:
        return ""
    val = m.group(1).strip()
    # Sometimes empty fields are "_No response_"
    if val == "_No response_":
        return ""
    return val

def split_csv_like(s: str):
    parts = [p.strip() for p in s.split(",") if p.strip()]
    # de-dup preserving order
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
    # flat CSV for portability
    fieldnames = [
        "word","part_of_speech","pronunciation","meaning_ja",
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

def upsert(items, entry):
    key = entry["word"].strip().lower()
    for i, it in enumerate(items):
        if it.get("word","").strip().lower() == key:
            # update existing but keep created_at if already present
            entry["created_at"] = it.get("created_at", entry["created_at"])
            items[i] = entry
            return "updated"
    items.append(entry)
    return "added"

def main():
    word = parse_field("Word")
    if not word:
        raise SystemExit("Word is required but missing.")
    entry = {
        "word": word.strip(),
        "part_of_speech": parse_field("Part of speech").strip(),
        "pronunciation": parse_field("Pronunciation (IPA etc.)").strip(),
        "meaning_ja": parse_field("Meaning (Japanese)").strip(),
        "examples": [l.strip() for l in parse_field("Examples (one per line)").splitlines() if l.strip()],
        "synonyms": split_csv_like(parse_field("Synonyms (comma-separated)")),
        "tags": split_csv_like(parse_field("Tags (comma-separated)")),
        "notes": parse_field("Notes").strip(),
        "mastery": 0,
        "last_reviewed": "",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_issue": ISSUE_URL or f"#{ISSUE_NUMBER}",
    }

    items = load_json()
    status = upsert(items, entry)
    # sort by word
    items.sort(key=lambda x: x.get("word","").lower())
    save_json(items)
    save_csv(items)
    print(status)

if __name__ == "__main__":
    main()
