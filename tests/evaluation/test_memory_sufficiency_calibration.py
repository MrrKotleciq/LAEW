"""Hand-labeled offline calibration corpus; labels describe whether Global evidence is needed.

These fixtures do not assert that lexical heuristics understand the text. They are
kept independent of the implementation and include adversarial incomplete records.
"""
from time import perf_counter

from laew.knowledge.routing import KnowledgeTurn, SourceRoute

# question, recalled records, additional Global evidence required
CASES = [
    ("Jakiego języka się uczyłem?", ["Użytkownik uczył się hiszpańskiego, ale zakończył naukę."], False),
    ("Which language did I study?", ["The user studied Spanish but stopped learning it."], False),
    ("Jakie miasto chciałbym odwiedzić?", ["Użytkownik chciałby odwiedzić Kioto."], False),
    ("Where did I put the rehearsal key?", ["I put the rehearsal key in a locker."], False),
    ("Podaj mój kod depozytu.", ["Kod depozytu: 17"], False),
    ("What is my account number?", ["Account number: 123"], False),
    ("When is my next hive inspection?", ["My next hive inspection is scheduled."], True),
    ("When is my next hive inspection?", ["My next hive inspection is in November."], True),
    ("Where did I put the rehearsal key and who can collect it?", ["I put the rehearsal key in a locker."], True),
    ("Jakie miasto chciałbym odwiedzić i kiedy?", ["Użytkownik chciałby odwiedzić Kioto."], True),
    ("Jakie miasto chciałbym odwiedzić?", ["Użytkownik chciałby odwiedzić Kioto.", "Użytkownik chciałby odwiedzić Oslo."], True),
    ("Podaj mój kod depozytu.", ["Kod depozytu: 17", "Kod depozytu: 42"], True),
    ("What is my account number?", ["Account number: unknown"], True),
    ("Which language did I study?", ["The user's favorite food is soup."], True),
    ("Czym szkliwiłam niebieską miskę?", [], True),
    ("What else?", ["The user studied Spanish."], True),
    ("A co jeszcze?", ["Użytkownik uczył się hiszpańskiego."], True),
    ("When did I finish my degree?", ["I am currently studying engineering."], True),
    ("Which city did I visit?", ["I planned to visit Paris but cancelled the trip."], True),
    ("What is my favorite book?", ["My favorite book is possibly Dune."], True),
    ("Where is my spare key?", ["My spare key is in the kitchen, but I may have moved it."], True),
    ("Where is my rehearsal studio key?", ["The rehearsal studio key was discussed with Alice."], True),
    ("What is my project deadline?", ["My project deadline is not confirmed."], True),
]


def test_assessment_calibration_metrics():
    turn = KnowledgeTurn(lambda *_: None)
    turn._decision = SourceRoute(True, (), "calibration")
    turn._global_queries = set()
    turn.diagnostics = {"prefetch": []}
    unnecessary = missed = 0
    started = perf_counter()
    for question, contents, needs_global in CASES:
        turn._message = question
        recall = {"status": "completed" if contents else "no_results", "prepared": len(contents), "mode": "semantic"}
        assessment, _, search, _ = turn._evaluate_recall(question, recall, [{"content": s} for s in contents])
        unnecessary += search and not needs_global
        missed += not search and needs_global
        print(f"{question} | {assessment['status']} | search={search} | required={needs_global}")
    elapsed = (perf_counter() - started) * 1000
    print(f"unnecessary_rag={unnecessary}/{sum(not c[2] for c in CASES)} "
          f"missed_evidence={missed}/{sum(c[2] for c in CASES)} assessment_ms={elapsed:.2f}")





def test_calibration_with_labeled_assessor_stub():
    """Measure orchestration with an oracle stub, not model accuracy."""
    turn = KnowledgeTurn(lambda *_: None)
    turn._decision = SourceRoute(True, (), "calibration")
    turn._global_queries = set()
    turn.diagnostics = {"prefetch": []}
    class LabeledAssessor:
        def __init__(self):
            self.calls = 0
            self.needs_global = None
        def assess(self, question, memories):
            self.calls += 1
            return {"status": "completed", "sufficient": not self.needs_global, "calls": 1}
    judge = LabeledAssessor()
    turn._assessor = judge
    unnecessary = missed = 0
    started = perf_counter()
    for question, contents, needs_global in CASES:
        turn._assessment_calls = 0
        turn._message = question
        judge.needs_global = needs_global
        recall = {"status": "completed" if contents else "no_results", "prepared": len(contents), "mode": "semantic"}
        _, _, search, _ = turn._evaluate_recall(question, recall, [{"content": s} for s in contents])
        unnecessary += search and not needs_global
        missed += not search and needs_global
    print(f"oracle_stub unnecessary_rag={unnecessary}/{sum(not c[2] for c in CASES)} "
          f"missed_evidence={missed}/{sum(c[2] for c in CASES)} model_calls={judge.calls} "
          f"assessment_ms={(perf_counter()-started)*1000:.2f}")
    assert (unnecessary, missed) == (0, 0)
