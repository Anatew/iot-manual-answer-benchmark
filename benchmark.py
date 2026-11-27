"""Run and evaluate extractive or external answers to a fictional IoT manual."""

import argparse
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
STOP = set("a an and are at can does how i in is it me of on or should the to what when which who with you".split())
VARIANTS = {
    "alerts": "alert", "calibrate": "calibration", "cleaning": "clean",
    "cleans": "clean", "exports": "export", "frequently": "interval",
    "largest": "maximum", "logging": "log", "messages": "message",
    "measurements": "measurement", "nodes": "node", "paired": "pair",
    "readings": "reading", "retained": "retention", "samples": "sample",
    "screws": "screw", "sensors": "sensor", "time": "time", "timeout": "time",
    "transmission": "transmit", "voltage": "input", "warning": "alert",
}


def read_data():
    manual = json.loads((ROOT / "data/manual.json").read_text(encoding="utf-8"))
    cases = read_jsonl(ROOT / "data/questions.jsonl")
    return manual, cases


def read_jsonl(path):
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path.name}:{number}: malformed JSON") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{path.name}:{number}: expected an object")
        records.append(record)
    return records


def normalize(text):
    clean = unicodedata.normalize("NFKC", text).casefold().replace("−", "-")
    return " ".join(clean.strip().rstrip(".!?").split())


def tokenize(text, enhanced):
    words = re.findall(r"[a-z]+", normalize(text))
    if enhanced:
        return {VARIANTS.get(word, word) for word in words if word not in STOP}
    return set(words)


def baseline(manual, cases, enhanced):
    facts = [(section["id"], fact, tokenize(fact["label"], enhanced))
             for section in manual for fact in section["facts"]]
    predictions = []
    for case in cases:
        question = tokenize(case["question"], enhanced)

        def score(candidate):
            words = candidate[2]
            if enhanced:
                return len(question & words) / len(words)
            return len(question & words)

        ranked = sorted(facts, key=score, reverse=True)
        section, fact, _ = ranked[0]
        enough_evidence = not enhanced or (
            score(ranked[0]) >= 0.66 and score(ranked[0]) > score(ranked[1])
        )
        predictions.append({
            "id": case["id"],
            "answer": fact["value"] if enough_evidence else None,
            "citations": [section] if enough_evidence else [],
        })
    return predictions


def evaluate(cases, predictions, passage_ids):
    expected_ids = {case["id"] for case in cases}
    indexed = {}
    for row in predictions:
        item = row.get("id")
        answer = row.get("answer")
        citations = row.get("citations")
        if not isinstance(item, str) or item not in expected_ids or item in indexed:
            raise ValueError(f"Unknown or repeated prediction ID: {item!r}")
        if "answer" not in row or (answer is not None and (
                not isinstance(answer, str) or not answer.strip())):
            raise ValueError(f"{item}: answer must be nonempty text or null")
        if (not isinstance(citations, list)
                or any(not isinstance(cite, str) or cite not in passage_ids for cite in citations)
                or len(citations) != len(set(citations))):
            raise ValueError(f"{item}: citations must be distinct manual section IDs")
        indexed[item] = row
    if set(indexed) != expected_ids:
        missing = ", ".join(sorted(expected_ids - set(indexed)))
        raise ValueError(f"Missing predictions: {missing}")

    details = []
    for case in cases:
        row = indexed[case["id"]]
        answerable = case["answer"] is not None
        if answerable and row["answer"] is not None:
            accepted = {normalize(choice) for choice in [case["answer"], *case["aliases"]]}
            correct = normalize(row["answer"]) in accepted
        else:
            correct = not answerable and row["answer"] is None
        details.append({
            "id": case["id"],
            "question": case["question"],
            "answerable": answerable,
            "expected_answer": case["answer"],
            "actual_answer": row["answer"],
            "expected_citations": case["citations"],
            "actual_citations": row["citations"],
            "answer_correct": correct,
            "citations_match": set(row["citations"]) == set(case["citations"]),
        })

    answerable = [row for row in details if row["answerable"]]
    unanswerable = [row for row in details if not row["answerable"]]
    counts = {
        "answer_match": (sum(row["answer_correct"] for row in answerable), len(answerable)),
        "citation_match": (sum(row["citations_match"] for row in answerable), len(answerable)),
        "abstention": (sum(row["answer_correct"] for row in unanswerable), len(unanswerable)),
        "strict_pass": (sum(row["answer_correct"] and row["citations_match"] for row in details),
                        len(details)),
    }
    return {"metrics": {key: {"passed": passed, "total": total}
                        for key, (passed, total) in counts.items()}, "details": details}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    demo = modes.add_parser("demo", help="compare two local baselines")
    demo.add_argument("--export", type=Path, help="write baseline predictions to a directory")
    external = modes.add_parser("evaluate", help="score one or more JSONL prediction files")
    external.add_argument("predictions", type=Path, nargs="+")
    parser.add_argument("--report", type=Path, help="write full JSON report (place before command)")
    args = parser.parse_args()
    try:
        manual, cases = read_data()
        sections = {section["id"] for section in manual}
        if args.mode == "demo":
            predictions = {name: baseline(manual, cases, enhanced)
                           for name, enhanced in (("keyword", False), ("with-abstention", True))}
            if args.export:
                args.export.mkdir(parents=True, exist_ok=True)
                for name, rows in predictions.items():
                    content = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
                    (args.export / (name + ".jsonl")).write_text(content, encoding="utf-8")
        else:
            predictions = {str(path): read_jsonl(path) for path in args.predictions}
        results = {name: evaluate(cases, rows, sections) for name, rows in predictions.items()}
        if args.report:
            args.report.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n",
                                   encoding="utf-8")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    for name, result in results.items():
        metrics = ", ".join(f"{key} {value['passed']}/{value['total']}"
                            for key, value in result["metrics"].items())
        print(f"{name}: {metrics}")


if __name__ == "__main__":
    main()
