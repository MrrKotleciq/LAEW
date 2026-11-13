# Atlas maintenance manual

## Purpose
The Atlas fixture is a fictional laboratory data recorder. Its maintenance procedure separates mechanical inspection, recording configuration, synchronization and acceptance. A completed configuration screen is not sufficient evidence that a recording is reliable. The operator keeps an audit trail of each intervention and records which equipment was connected. This manual is evaluation material and describes no real installation.

## Prerequisites
Before updating Atlas firmware, disconnect the excitation output and verify that the recovery image can be restored. Keep the instrument powered from the approved isolated supply while copying its configuration. A screenshot of the live display is insufficient because it omits calibration and trigger state. Export the complete configuration bundle and record its checksum before opening the maintenance session.

## Inspection
Inspect the shield termination, connector latch and strain relief independently. A clean enclosure is not proof of a good signal connection. Report cracked insulation and quarantine a cable with intermittent continuity. Do not compensate for a damaged lead by changing the software gain. The maintenance record must identify the replacement part and the inspection result.

## Timebase
Compare the recorder clock with the laboratory reference before collecting acceptance traces. A plausible date on the display does not establish timing accuracy. Preserve the measured offset and the duration of the comparison. Clock adjustments during recording invalidate the continuity assumption, so stop acquisition before changing synchronization configuration.

## Configuration
Configure the recorder with the released channel map rather than a map exported from a prototype. Names are descriptive; channel numbers determine the stored measurement order. The operator checks both against the signed wiring schedule. A previously successful recording is not sufficient to approve a changed harness or sensor assignment.

## Trigger
A trigger marks the start of an event and must be tested with a known pulse. Inspect pre-event and post-event intervals separately. An event visible in the display may still have insufficient prehistory in the saved record. Confirm that the file contains the expected baseline before the pulse and a complete decay afterward.

## Buffering
The internal queue absorbs brief storage stalls but does not guarantee lossless recording indefinitely. Monitor queue occupancy during a representative workload. A steadily increasing backlog indicates that sustained input exceeds storage throughput. Reduce the offered load and repeat the trial; clearing the counter alone does not resolve the bottleneck.

## Storage
Use a clean test directory and preserve the original acceptance files until review is complete. Verify the stored checksum after closing the file. Free capacity estimates do not establish write durability. An interrupted file must be classified explicitly rather than silently appended to a previous successful test run.

## Recovery
A failed update leaves the excitation output disconnected. Restore the verified recovery image before importing the saved configuration bundle. Keep the failure log with the recovery record and perform the acceptance procedure again. Successful startup alone does not approve reconnecting the actuator or releasing the recorder to another operator.

## Acceptance
Atlas passes acceptance only when the timestamp drift remains below 80 microseconds over the complete test interval. The acceptance record must also contain a continuous 40-second trace without a dropped sample. Inspect the exported file, not only the live display. A short successful capture does not establish compliance with the complete interval requirement.

## Handover
The reviewer signs the restored configuration checksum and the acceptance result. Preserve unsuccessful trials with their explanation so that the final record cannot be mistaken for the only trial performed. Document the instrument identifier and firmware revision in the handover note. The next operator must be able to reconstruct which configuration was approved.
