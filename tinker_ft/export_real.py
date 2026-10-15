"""Turn REAL first-step sentences from the app's SQLite DB into a JSONL you can hand-label and train on.

Usage (locally, on a copy of the DB downloaded from the Render disk):
    python -m tinker_ft.export_real path/to/firststep.db > data/firststep_real.jsonl
Each row has the rules' guess in "rules_label" and an empty "label". Fill "label" by hand (that is the point:
a human label on a real learner sentence), then train/evaluate with tinker_ft/train_firststep.py on the labelled rows.
Learner ids are NOT exported.
"""
import json
import sqlite3
import sys

from app.firststep import classify_rules
from app.problems import PROBLEMS


def main(db_path: str) -> None:
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row
    for r in db.execute("SELECT problem_id, first_step_text, first_step_cat FROM sessions "
                        "WHERE first_step_text IS NOT NULL AND first_step_text != '' ORDER BY id"):
        p = PROBLEMS.get(r["problem_id"])
        if not p:
            continue
        print(json.dumps({"problem_id": p.id, "statement": p.statement, "text": r["first_step_text"],
                          "app_label": r["first_step_cat"], "rules_label": classify_rules(p.statement, r["first_step_text"]),
                          "label": ""}))


if __name__ == "__main__":
    main(sys.argv[1])