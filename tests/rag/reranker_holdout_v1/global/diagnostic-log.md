# Fictional diagnostic event format
## Event fields
An Atlas diagnostic event contains a run identifier, a category and a monotonic elapsed-time value. The event description records whether a failure occurred while waiting for input, decoding a frame or checking a profile. The log schema deliberately keeps these categories separate so that a timeout cannot silently become a successful empty measurement. This is an original test fixture and defines no production logging policy.
## Redaction and retention
Full measurement payloads and authentication secrets are excluded from ordinary events. A record may refer to a separate controlled capture by its identifier. Such a reference does not make the capture available to every reader of the event log. Event retention does not alter the calibration acceptance threshold or the requirements for database backup.
## Investigation
The first failed validation stage and the active profile version should be preserved when troubleshooting. A later successful retry is stored as a new event. It must not overwrite the fact that the initial run failed. Search results from this diagnostic schema cannot establish absent electrical or mechanical operating limits.
