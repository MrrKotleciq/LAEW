"""Compare local NLI formulations and replay a hypothetical RAG gate on fixtures."""

import argparse
import hashlib
import json
import re
from pathlib import Path

from laew.eval.memory_sufficiency_eval import DATASET, evaluate
from laew.knowledge.horizon import HorizonAssessor, SIGNAL_THRESHOLD, coverage_pair


HOLDOUT = DATASET.with_name("horizon_strategy_holdout.json")


def direct_answerability(question, memories):
    pair = coverage_pair(question, memories)
    pair["hypothesis"] = f"The passage gives a specific answer to this question: {question}"
    return pair


def evidence_relevance(question, memories):
    pair = coverage_pair(question, memories)
    pair["hypothesis"] = f"The passage discusses the subject of this question: {question}"
    return pair


def candidate_entailment(question, memories):
    """Fill a location slot from one matching declarative Memory sentence."""
    if len(memories) != 1:
        return None
    question_match = re.fullmatch(
        r"(?:where (is|are) ((?:my|our) [\w ]+)|"
        r"gdzie (jest|są) ((?:mój|moja|moje|nasz|nasza|nasze) [\w ]+))\?",
        question.strip(), re.IGNORECASE,
    )
    if not question_match:
        return None
    en_verb, en_subject, pl_verb, pl_subject = question_match.groups()
    verb, subject = (en_verb, en_subject) if en_verb else (pl_verb, pl_subject)
    prepositions = "in|at|under|inside|on|behind|beside|near" if en_verb else "w|we|pod|na|obok|za"
    premise = memories[0].get("content", "").strip()
    location = re.fullmatch(
        rf"{re.escape(subject)} {verb} ((?:{prepositions}) [^.!?;:\n]+)\.?",
        premise, re.IGNORECASE,
    )
    if not location or re.search(
        r"\b(?:and|or|if|unless|maybe|possibly|probably|until|"
        r"i|oraz|albo|jeśli|jeżeli|chyba|prawdopodobnie|dopóki)\b",
        subject + " " + location[1], re.IGNORECASE,
    ):
        return None
    return {"premise": premise, "hypothesis": f"{subject[0].upper()}{subject[1:]} {verb} {location[1]}."}


FORMULATIONS = {
    "legacy": coverage_pair,
    "a_answerability": direct_answerability,
    "b_candidate": candidate_entailment,
    "c_relevance": evidence_relevance,
}


class RecordedAssessment:
    """Keep fixture-only scores for a replay without additional inference."""

    def __init__(self, builder):
        self.assessor = HorizonAssessor(pair_builder=builder)
        self.scores = {}

    @staticmethod
    def key(question, memories):
        return question, tuple(memory["content"] for memory in memories)

    def assess(self, question, memories):
        result = self.assessor.assess(question, memories)
        if result["status"] == "completed":
            self.scores[self.key(question, memories)] = result["entailment_score"]
        return result

    def replay(self, question, memories):
        score = self.scores.get(self.key(question, memories))
        return {"status": "completed", "sufficient": score is not None and score >= SIGNAL_THRESHOLD}


class Replay:
    def __init__(self, recording):
        self.assess = recording.replay


def evaluate_dataset(path):
    data = path.read_bytes()
    cases = json.loads(data.decode("utf-8-sig"))
    records = {name: RecordedAssessment(builder) for name, builder in FORMULATIONS.items()}
    modes = [(name, record) for name, record in records.items()]
    modes += [(f"{name}_hypothetical_gate", Replay(record)) for name, record in records.items()]
    runs = evaluate(cases, {"active": (None, ""), "dedicated": (None, "")}, additional_assessors=modes)
    advisory = {name: runs[name] for name in ("heuristic", *FORMULATIONS)}
    gates = {}
    for name in FORMULATIONS:
        replay = runs[f"{name}_hypothetical_gate"]
        gates[name] = {
            "metrics": {key: value for key, value in replay["metrics"].items()
                        if key in ("false_sufficient", "unnecessary_rag", "missed_required_rag",
                                   "missed_evidence", "evidence_covered", "rag_calls")},
            "changed_cases": [after["id"] for before, after in zip(runs[name]["cases"], replay["cases"], strict=True)
                              if before["assessment_status"] != after["assessment_status"]],
        }
    # The labelled probe bypasses routing and candidate extraction to isolate NLI.
    probe = HorizonAssessor(pair_builder=lambda claim, memories: {
        "premise": "\n\n".join(memory["content"] for memory in memories),
        "hypothesis": claim,
    })
    probes = []
    for case in cases:
        if "claim" in case:
            result = probe.assess(case["claim"], [{"content": text} for text in case["memory"]])
            probes.append({"id": case["id"], "supported": case["claim_supported"], **result})
    return {"dataset": path.as_posix(), "sha256": hashlib.sha256(data).hexdigest(),
            "advisory_runs": advisory, "hypothetical_gates": gates,
            "provided_claim_probes": probes}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, action="append")
    args = parser.parse_args()
    results = [evaluate_dataset(path) for path in (args.dataset or [DATASET, HOLDOUT])]
    payload = {"hypothetical_gate_threshold": SIGNAL_THRESHOLD, "datasets": results}
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
