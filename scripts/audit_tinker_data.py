import json
from collections import Counter
from pathlib import Path

def audit():
    root = Path(__file__).resolve().parent.parent
    train_path = root / "data" / "firststep_train.jsonl"
    test_path = root / "data" / "firststep_test.jsonl"
    
    try:
        with open(train_path, "r", encoding="utf-8") as f:
            train_data = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        print(f"Training file not found at {train_path}")
        return

    try:
        with open(test_path, "r", encoding="utf-8") as f:
            test_data = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        test_data = []

    print("=== FirstStep Dataset Audit ===")
    print(f"Training size: {len(train_data)}")
    print(f"Test size: {len(test_data)}")
    
    # Note: Adjust key name if your dataset uses 'text' or 'sentence'
    train_labels = Counter([x.get("label") for x in train_data])
    print(f"Train Class Distribution: {dict(train_labels)}")
    
    train_sentences = [x.get("text", x.get("sentence", "")) for x in train_data]
    duplicates = [s for s, c in Counter(train_sentences).items() if c > 1]
    print(f"Duplicate training rows detected: {len(duplicates)}")
    
    test_sentences = set(x.get("text", x.get("sentence", "")) for x in test_data)
    overlap = set(train_sentences).intersection(test_sentences)
    print(f"Exact Train/Test Text Overlap: {len(overlap)}")

if __name__ == "__main__":
    audit()