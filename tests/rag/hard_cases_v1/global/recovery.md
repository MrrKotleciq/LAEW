# Recovery
## Recovery order
The violet snapshot is approved only for the auxiliary controller.
```sh
stop_auxiliary
restore_snapshot violet
verify_auxiliary
```
Never apply this snapshot to the main controller.
## Main controller
The main controller uses the amber snapshot after manual approval.
