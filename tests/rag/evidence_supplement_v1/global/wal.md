# SQLite WAL engineering note
## Concurrency
WAL lets readers overlap a writer, but there is still only one writer at a time.
All database processes must share a host; WAL is unsuitable for a network filesystem.
Each read transaction retains its original committed snapshot until it ends.
## Checkpoint pressure
A checkpoint copies committed WAL pages back into the database.
A long-lived reader can prevent a checkpoint from advancing past that reader's snapshot.
The normal automatic checkpoint threshold is 1000 pages, and applications can change it.
Busy outcomes remain possible in WAL mode; concurrent reading does not guarantee that every operation succeeds immediately.
