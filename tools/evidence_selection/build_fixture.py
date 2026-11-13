"""Build the source-labeled supplement; no retrieval, model output or private data."""
import hashlib
import json
from pathlib import Path


def build(root):
    if root.exists() and any(root.iterdir()):
        raise FileExistsError("Refusing to overwrite a frozen fixture; use a new empty directory")
    documents = {
        "global/wal.md": ("en", "https://www.sqlite.org/wal.html", """# SQLite WAL engineering note
## Concurrency
WAL lets readers overlap a writer, but there is still only one writer at a time.
All database processes must share a host; WAL is unsuitable for a network filesystem.
Each read transaction retains its original committed snapshot until it ends.
## Checkpoint pressure
A checkpoint copies committed WAL pages back into the database.
A long-lived reader can prevent a checkpoint from advancing past that reader's snapshot.
The normal automatic checkpoint threshold is 1000 pages, and applications can change it.
Busy outcomes remain possible in WAL mode; concurrent reading does not guarantee that every operation succeeds immediately.
"""),
        "global/isolation.md": ("en", "https://www.postgresql.org/docs/current/transaction-iso.html", """# PostgreSQL transaction review
## Read committed
Read Committed obtains a new snapshot for each statement.
Two reads in one transaction can therefore observe different committed data.
## Repeatable read
Repeatable Read keeps the snapshot established by the first non-control statement.
It prevents phantom reads in PostgreSQL but can still admit serialization anomalies.
Updating transactions must handle serialization failures by restarting the entire transaction.
## Serializable
Serializable admits only committed results consistent with some serial ordering.
Applications still need transaction retry logic when serialization fails.
Predicate locks used to detect dependencies do not block other transactions.
"""),
        "global/revert.md": ("en", "https://git-scm.com/docs/git-revert", """# Undoing a shared Git change
## Published history
Revert records a new commit that reverses the effect of an earlier change.
The ordinary invocation requires a clean working tree.
## Merge parent
Reverting a merge requires choosing a mainline parent with -m; parent numbering starts at one.
The reversal is computed relative to that parent.
Later merges do not automatically restore tree changes from ancestors of the reverted merge.
## Staging
The --no-commit option applies reversals to the working tree and index without making a commit.
It can combine reversals of several commits before recording the result.
"""),
        "global/codegen.md": ("en", "https://cmake.org/cmake/help/latest/command/add_custom_command.html", """# CMake generated artifact dependencies
## Outputs
An OUTPUT custom command defines a build rule for generated files.
Independent targets must not each own the same generated output when they may build concurrently.
Use one custom target to drive shared generation and make consumers depend on it.
## Auxiliary products
Declare secondary generated files with BYPRODUCTS so Ninja knows how to rebuild them when missing.
Relative byproduct paths are interpreted relative to the build tree directory for the source directory.
## Arguments
VERBATIM asks CMake to escape arguments appropriately for the build tool.
Multiple COMMAND entries are not guaranteed to share a stateful shell.
"""),
        "project/release-current.md": ("pl", "fictional:release-R7", """---
status: approved
---
# Procedura wydania R7
## Warunki wstępne
Przed migracją zatrzymaj zadania zapisujące i potwierdź odtworzenie kopii na izolowanym serwerze.
## Okno wdrożenia
Zatwierdzone okno migracji R7 wynosi 25 minut.
## Wycofanie
Jeżeli suma kontrolna nie pasuje, zatrzymaj publikację i przywróć poprzedni obraz wraz ze zgodną wersją schematu.
"""),
        "project/release-old.md": ("pl", "fictional:release-R6", """---
status: superseded
---
# Archiwum wydania R6
## Okno wdrożenia
Historyczne okno migracji R6 wynosiło 12 minut.
Ta notatka została zastąpiona procedurą R7 i nie stanowi aktualnej zgody na wdrożenie.
"""),
        "global/release-check.md": ("de", "fictional:release-validation", """# Validierung eines Releases
## Nach der Migration
Nach dem Schemawechsel müssen Integritätsprüfung und ein Schreib-Lese-Test erfolgreich sein.
Die Prüfung erfolgt vor dem Wiederanlauf der schreibenden Aufgaben.
"""),
    }
    # Long, explicitly fictional multi-section engineering procedure. Unique
    # natural prose, not repeated padding or a source-specific selector feature.
    sections = [
        ("Purpose", "The Atlas fixture is a fictional laboratory data recorder. Its maintenance procedure separates mechanical inspection, recording configuration, synchronization and acceptance. A completed configuration screen is not sufficient evidence that a recording is reliable. The operator keeps an audit trail of each intervention and records which equipment was connected. This manual is evaluation material and describes no real installation."),
        ("Prerequisites", "Before updating Atlas firmware, disconnect the excitation output and verify that the recovery image can be restored. Keep the instrument powered from the approved isolated supply while copying its configuration. A screenshot of the live display is insufficient because it omits calibration and trigger state. Export the complete configuration bundle and record its checksum before opening the maintenance session."),
        ("Inspection", "Inspect the shield termination, connector latch and strain relief independently. A clean enclosure is not proof of a good signal connection. Report cracked insulation and quarantine a cable with intermittent continuity. Do not compensate for a damaged lead by changing the software gain. The maintenance record must identify the replacement part and the inspection result."),
        ("Timebase", "Compare the recorder clock with the laboratory reference before collecting acceptance traces. A plausible date on the display does not establish timing accuracy. Preserve the measured offset and the duration of the comparison. Clock adjustments during recording invalidate the continuity assumption, so stop acquisition before changing synchronization configuration."),
        ("Configuration", "Configure the recorder with the released channel map rather than a map exported from a prototype. Names are descriptive; channel numbers determine the stored measurement order. The operator checks both against the signed wiring schedule. A previously successful recording is not sufficient to approve a changed harness or sensor assignment."),
        ("Trigger", "A trigger marks the start of an event and must be tested with a known pulse. Inspect pre-event and post-event intervals separately. An event visible in the display may still have insufficient prehistory in the saved record. Confirm that the file contains the expected baseline before the pulse and a complete decay afterward."),
        ("Buffering", "The internal queue absorbs brief storage stalls but does not guarantee lossless recording indefinitely. Monitor queue occupancy during a representative workload. A steadily increasing backlog indicates that sustained input exceeds storage throughput. Reduce the offered load and repeat the trial; clearing the counter alone does not resolve the bottleneck."),
        ("Storage", "Use a clean test directory and preserve the original acceptance files until review is complete. Verify the stored checksum after closing the file. Free capacity estimates do not establish write durability. An interrupted file must be classified explicitly rather than silently appended to a previous successful test run."),
        ("Recovery", "A failed update leaves the excitation output disconnected. Restore the verified recovery image before importing the saved configuration bundle. Keep the failure log with the recovery record and perform the acceptance procedure again. Successful startup alone does not approve reconnecting the actuator or releasing the recorder to another operator."),
        ("Acceptance", "Atlas passes acceptance only when the timestamp drift remains below 80 microseconds over the complete test interval. The acceptance record must also contain a continuous 40-second trace without a dropped sample. Inspect the exported file, not only the live display. A short successful capture does not establish compliance with the complete interval requirement."),
        ("Handover", "The reviewer signs the restored configuration checksum and the acceptance result. Preserve unsuccessful trials with their explanation so that the final record cannot be mistaken for the only trial performed. Document the instrument identifier and firmware revision in the handover note. The next operator must be able to reconstruct which configuration was approved."),
    ]
    documents["global/atlas.md"] = ("en", "fictional:atlas-maintenance", "# Atlas maintenance manual\n\n" + "\n\n".join("## " + h + "\n" + t for h, t in sections) + "\n")
    for path, (_, _, text) in documents.items():
        target = root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8", newline="\n")

    queries = []
    def q(text, language, topic, evidence, scope="global", phenomenon="cross_language"):
        atoms = [{"document_id": ("@project/" if p.startswith("project/") else "@knowledge/") + p.split("/", 1)[1], "passage": passage}
                 for p, passage in evidence]
        ids = list(dict.fromkeys(a["document_id"] for a in atoms))
        queries.append({"id": f"s{len(queries)+1:02}", "text": text, "language": language,
                        "topic_id": topic, "phenomenon": phenomenon, "split": "source_labeled_supplement",
                        "allowed_scope": scope, "expected_document_ids": ids, "relevance": {d: 2 for d in ids},
                        "evidence": atoms, "no_answer": None if atoms else "unsupported"})
    q("Czy WAL pozwoli kilku procesom jednocześnie zapisywać bazę na udziale sieciowym?", "pl", "wal", [("global/wal.md", "there is still only one writer at a time."), ("global/wal.md", "WAL is unsuitable for a network filesystem.")])
    q("Our WAL file keeps growing while reporting holds a read transaction open. What could stop checkpoint progress?", "en", "wal", [("global/wal.md", "A long-lived reader can prevent a checkpoint from advancing past that reader's snapshot.")])
    q("Welche beiden Snapshot-Garantien unterscheiden Read Committed von Repeatable Read?", "de", "isolation", [("global/isolation.md", "Read Committed obtains a new snapshot for each statement."), ("global/isolation.md", "Repeatable Read keeps the snapshot established by the first non-control statement.")])
    q("Transakcja aktualizująca dostała błąd serializacji. Czy ponowić tylko ostatni UPDATE?", "pl", "isolation", [("global/isolation.md", "Updating transactions must handle serialization failures by restarting the entire transaction.")])
    q("Would PostgreSQL Serializable remove the need for application retries?", "en", "isolation", [("global/isolation.md", "Applications still need transaction retry logic when serialization fails.")])
    q("Jak cofnąć opublikowaną zmianę bez przepisywania historii i jak przygotować kilka cofnięć razem?", "pl", "revert", [("global/revert.md", "Revert records a new commit that reverses the effect of an earlier change."), ("global/revert.md", "The --no-commit option applies reversals to the working tree and index without making a commit.")])
    q("Why do I need to choose a parent when reverting a merge, and will merging again restore everything?", "en", "revert", [("global/revert.md", "Reverting a merge requires choosing a mainline parent with -m; parent numbering starts at one."), ("global/revert.md", "Later merges do not automatically restore tree changes from ancestors of the reverted merge.")])
    q("Ninja cannot regenerate a missing auxiliary file from our code generator. What declaration is missing?", "en", "codegen", [("global/codegen.md", "Declare secondary generated files with BYPRODUCTS so Ninja knows how to rebuild them when missing.")])
    q("Zwei Targets erzeugen dieselbe Datei parallel. Wie soll die CMake-Abhängigkeit aufgebaut werden?", "de", "codegen", [("global/codegen.md", "Use one custom target to drive shared generation and make consumers depend on it.")])
    q("Can two custom COMMAND entries rely on shell variables set by the first one?", "en", "codegen", [("global/codegen.md", "Multiple COMMAND entries are not guaranteed to share a stateful shell.")])
    q("I have twelve minutes reserved for R7. Is that the approved window, and what must finish before migration?", "en", "release", [("project/release-current.md", "Zatwierdzone okno migracji R7 wynosi 25 minut."), ("project/release-current.md", "Przed migracją zatrzymaj zadania zapisujące i potwierdź odtworzenie kopii na izolowanym serwerze.")], "project", "superseded")
    q("Co zrobić przed migracją R7 i jakie sprawdzenia wykonać przed wznowieniem zapisów?", "pl", "release", [("project/release-current.md", "Przed migracją zatrzymaj zadania zapisujące i potwierdź odtworzenie kopii na izolowanym serwerze."), ("global/release-check.md", "Nach dem Schemawechsel müssen Integritätsprüfung und ein Schreib-Lese-Test erfolgreich sein.")], "hybrid", "multi_document")
    q("For the database review, explain both PostgreSQL snapshot stability and why an SQLite WAL checkpoint can stall.", "en", "database-review", [("global/isolation.md", "Repeatable Read keeps the snapshot established by the first non-control statement."), ("global/wal.md", "A long-lived reader can prevent a checkpoint from advancing past that reader's snapshot.")], phenomenon="multi_document")
    q("Co zabezpieczyć przed aktualizacją firmware Atlas i jakie dwa wyniki muszą znaleźć się w odbiorze?", "pl", "atlas", [("global/atlas.md", "Before updating Atlas firmware, disconnect the excitation output and verify that the recovery image can be restored."), ("global/atlas.md", "the timestamp drift remains below 80 microseconds over the complete test interval."), ("global/atlas.md", "a continuous 40-second trace without a dropped sample.")], phenomenon="long_procedure")
    q("Atlas starts successfully after a failed update. May I reconnect its actuator immediately?", "en", "atlas", [("global/atlas.md", "Restore the verified recovery image before importing the saved configuration bundle."), ("global/atlas.md", "Successful startup alone does not approve reconnecting the actuator or releasing the recorder to another operator.")])
    q("Welche Nachweise braucht die Atlas-Abnahme statt nur einer kurzen Anzeige?", "de", "atlas", [("global/atlas.md", "the timestamp drift remains below 80 microseconds over the complete test interval."), ("global/atlas.md", "a continuous 40-second trace without a dropped sample.")])
    q("Which torque in newton metres is approved for the Atlas enclosure bolts?", "en", "atlas", [], phenomenon="no_answer")
    q("Jaki jest zatwierdzony adres serwera produkcyjnego R7?", "pl", "release", [], "project", "no_answer")
    q("Which maximum database size guarantees no SQLite WAL busy errors?", "en", "wal", [], phenomenon="no_answer")
    q("What is the company's approved CMake generator for its private build farm?", "en", "codegen", [], phenomenon="no_answer")
    dataset = {"id": "laew-evidence-source-supplement-v1", "version": 1, "queries": queries,
               "document_languages": {("@project/" if p.startswith("project/") else "@knowledge/") + p.split("/", 1)[1]: lang for p, (lang, _, _) in documents.items()},
               "sources": {p: url for p, (_, url, _) in documents.items()}}
    (root / "dataset.json").write_text(json.dumps(dataset, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    frozen = {"date": "2026-11-10", "labeling": "Source-grounded authored labels before scoring; no external independent annotator or model judgments.",
              "sha256": {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file() and p.name != "FREEZE.json"}}
    (root / "FREEZE.json").write_text(json.dumps(frozen, indent=2) + "\n", encoding="utf-8", newline="\n")


if __name__ == "__main__":
    build(Path("tests/rag/evidence_supplement_v1"))
