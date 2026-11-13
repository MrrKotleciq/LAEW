# Undoing a shared Git change
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
