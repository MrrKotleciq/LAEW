# Fictional Atlas R2 laboratory gateway
## Laboratory frame acceptance
This original test scenario describes a retired laboratory profile. Atlas R2 laboratory frames contain 24 bytes. Their acknowledgements use a laboratory cycle counter rather than the production R3 session number. A 24-byte frame is valid only for the R2 simulator; it is not a valid measurement frame for the production Atlas R3 receiver. The profile is intentionally retained for migration tests so a search can encounter similar terminology from different versions.
## Troubleshooting an R2 simulation
The simulator can delay an acknowledgement to exercise client retries. Record the simulator build before interpreting those delays. A transport connection may remain open while no simulated measurement is available. Do not change the production receiver merely because the laboratory script accepts a shorter payload. Session validation in the R3 production profile is not optional and cannot be replaced by an R2 laboratory acknowledgement.
## Compatibility record
An R2 test record contains the profile name, cycle counter and simulator build. It does not establish production acceptance limits, calibrated timing accuracy or a safe migration procedure. Those details must come from the active profile and the corresponding timing specification.
