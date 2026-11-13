# PostgreSQL transaction review
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
