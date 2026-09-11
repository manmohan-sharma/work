# Concept 3: Reliability Risk Assessment

## Exercise Overview

This exercise focuses on identifying reliability risks in AI-generated batch processing and API integration code. You'll practice evaluating system availability, performance characteristics, and failure resilience in production environments.

## Scenario

Your team is building a financial data processing system that handles daily batch operations and integrates with multiple external APIs. An AI tool generated the batch processing pipeline and API integration logic based on your requirements for processing large datasets and maintaining data consistency. The code works well in development and testing, but you need to assess its reliability before deploying to production where it will handle critical financial data.

## Your Task

1. **Review the starter code** (`data_pipeline.py`) for reliability concerns
2. **Apply the reliability risk assessment framework** from the lesson
3. **Identify potential failure points** in batch processing and API integration
4. **Assess resource management** and memory/connection handling
5. **Evaluate error handling** and recovery mechanisms
6. **Analyze performance characteristics** under load
7. **Classify the overall reliability risk level** (Low, Medium, High, Critical)
8. **Make a recommendation**: Accept, Modify, Reject, or Escalate
9. **Run the tests** to understand system behavior under various conditions
10. **Compare with the solution** to validate your assessment

## Reliability Focus Areas

Pay special attention to:
- **Resource management** (memory, database connections, file handles)
- **Error handling** for external API dependencies
- **Recovery mechanisms** for partial failures
- **Performance under load** and large dataset processing
- **Data consistency** and transaction handling
- **Monitoring and observability** for production operations

## Expected Issues

The starter code contains several reliability anti-patterns commonly found in AI-generated systems:
- Resource leaks in database connections
- Missing error handling for external dependencies
- Memory-intensive operations without limits
- No retry logic for transient failures
- Lack of progress tracking and resumability
- Poor performance characteristics at scale

## Reliability Assessment Questions

Consider these questions during your review:
1. What happens when external APIs are temporarily unavailable?

   **Every record fails, and the run still reports success.** Both calls in
   `ExternalAPIClient` (`data_pipeline.py:23-30`, `:32-43`) issue a single bare
   `requests.get` — no retry, no backoff, no circuit breaker, and no `Session`,
   so each call pays a fresh TCP + TLS handshake. `get_exchange_rate` never
   checks `status_code` and calls `response.json()` directly (`:30`): a 500 HTML
   page raises `JSONDecodeError`, and a 200 error payload raises
   `KeyError: 'rate'` at `:87`. `validate_account` raises a bare `Exception`
   (`:43`), indistinguishable by type from a programming bug. Measured against
   the unreachable `api.financial-service.com`: 0 successful / 5 failed in
   **33.02 s** — 6.6 s burned per record, with the 30 s timeout (`:21`) as the
   per-call worst case. `run_daily_pipeline` nevertheless returns
   `"pipeline_status": "completed"` (`:193`) because that string is hardcoded.
   Against the 99.5% availability target, a dependency blip is not a degraded
   run — it is a 100% data-loss run that looks green.

2. How does the system handle partial failures in batch processing?

   **It counts them and drops them.** `process_batch` (`:110-125`) catches every
   `Exception`, increments a counter, appends `str(e)`, and `continue`s. Failed
   records are never persisted: `_save_transaction` is only reached on the
   success path and only ever writes `'completed'` (`:92`), so there is no
   dead-letter queue, no retry queue, and no row to reconcile against. The sole
   record of a failure is the in-memory `errors` list, printed at `:233` and
   then discarded — which breaks the audit-trail requirement for financial
   processing outright. Within a single record the three steps (`:80`, `:86`,
   `:92`) are not atomic: validation and FX conversion can succeed and the
   insert then fail, with no rollback, compensation, or saga
   (`test_no_transaction_rollback_on_partial_failures` demonstrates exactly this
   and passes). Tellingly, the schema defines `status TEXT DEFAULT 'pending'`
   (`:65`) but no code ever writes `'pending'` — the state machine that would
   make partial failure recoverable exists in the table and is unused. The
   error path is also fragile: `results["errors"].append(result["reason"])`
   (`:118`) assumes every non-completed result carries a `reason` key.

3. Are there resource leaks that could cause system instability?

   **Yes — connections, sockets, and unbounded memory.** `setup_database`
   (`:56-71`), `_save_transaction` (`:133-143`) and `get_transaction_summary`
   (`:147-158`) each open a connection and call `.close()` only on the success
   path — no `with`, no `try/finally`. CPython refcounting usually reclaims the
   handle, so the leak is bounded rather than unbounded, but any retained
   traceback (or a non-refcounting runtime) keeps it open, and an unclosed
   connection that has executed an INSERT holds SQLite's RESERVED write lock.
   Measured: with one writer stalled after INSERT but before `commit()`, the
   next `_save_transaction` blocks for the full 5 s default busy timeout and
   then raises `OperationalError: database is locked` — and the stalled writer's
   row is silently lost. The connect-per-write cost is the larger leak of
   throughput: **2,000 inserts through `_save_transaction` took 10.61 s
   (188 txn/s); the same 2,000 rows on one pooled connection with a single
   commit took 0.01 s (157,707 txn/s) — 837x.** On the network side, no
   `requests.Session` (`:27`, `:37`) means two fresh handshakes per record and
   sockets accumulating in TIME_WAIT, putting ephemeral-port exhaustion in reach
   on a large batch. Memory: `_fetch_data_from_source` (`:200`) materializes the
   whole dataset as a list and `process_batch` holds it alongside an unbounded
   `errors` list — measured **+61 MB for 200,000 records before any work**, plus
   **+57 MB for 200,000 error strings** (274 bytes each), i.e. roughly **590 MB
   resident for a 1M-row batch against a down API**, all held until the batch
   ends.

4. Can the system recover gracefully from interruptions?

   **No — and re-running after one corrupts the ledger.** There is no
   checkpoint, no cursor, no batch id, and no processed-marker;
   `run_daily_pipeline` (`:174-198`) restarts from record 0 every time, and
   `last_run` (`:172`, `:190`) is in-process state lost on restart. The
   `transactions` table has no natural key and no UNIQUE constraint (`:59-68`),
   and the source records carry no transaction id at all (`:204-210`).
   Measured: processing the same $100 record three times produces **3 rows
   totalling $300**. So an interruption at 80% forces a choice between losing
   the remaining 20% and double-booking the 80% already written — with no way to
   tell which records those were. This fails the stated requirement to "resume
   processing after interruptions without data loss" in both directions.

5. How will the system perform under production data volumes?

   **The 4-hour window is the binding constraint, and nothing enforces it.**
   `process_batch` is a single-threaded `for` loop (`:110`); each non-USD record
   makes two *sequential* blocking HTTP round trips (`:80`, `:86`) plus a
   connect-insert-commit-close. Budget: 14,400 s. At an optimistic 50 ms per API
   call → ~0.105 s/record → ~137,000 records/night. At a realistic 200 ms p95 →
   ~0.405 s/record → ~35,500. With the dependency degraded to the 30 s timeout,
   **480 records consume the entire window**; at the 6.6 s/record actually
   measured against an unreachable host, ~2,180. Even at zero API latency the
   write path alone caps at the measured 188 txn/s (~5.3 ms/record). Nothing
   bounds runtime — no deadline, no max duration, no load shedding, no
   parallelism — so an overrun is silent; `duration_seconds` (`:188`) is
   computed and reported but never compared against a threshold. On the 10x
   growth requirement, the loop has no horizontal path and SQLite (`:56`) is a
   single-writer embedded file: 4 concurrent writers took 6.43 s for 1,200 rows
   in measurement, and the lock test above shows contention surfacing as
   `database is locked`. The storage engine is the wrong substrate for the
   scalability target regardless of what the loop does.

6. Are there adequate monitoring and alerting mechanisms?

   **There are none.** The `logging` module is never imported (`:9-13`); the only
   output in the entire module is `print()` inside `__main__` (`:225-243`). No
   log levels, no structured events, no batch/correlation id, no metrics, no
   health check, no alert path, and no non-zero exit code — to a scheduler or a
   pager, a run that processed nothing is indistinguishable from a clean one.
   The signal that would be needed is computed and thrown away: `errors` is
   returned then dropped, `duration_seconds` is never thresholded, and
   `pipeline_status` is the constant `"completed"` (`:193`). There is no audit
   trail: failures never reach the database, and successful rows record no
   source id, no FX rate used, no batch, and no operator — disqualifying on its
   own for financial data. The test suite is diagnostic-only in the same way as
   Concept 2: every reliability check is a `print()`, so **all 9 tests pass
   against the broken pipeline** and CI stays green.
   `test_pipeline_orchestration` (`test_data_pipeline.py:188-197`) makes real
   network calls to `api.financial-service.com` and asserts only that three keys
   exist — it passed here with 0/5 records processed, spending 12.57 s of the
   suite's 26.83 s runtime waiting on connect timeouts. The tests also write to
   the real
   `starter/transactions.db` with no fixture or cleanup (verified: row count
   went 9 → 11 from a single test), so the suite pollutes the same file the
   pipeline uses.

7. What happens when memory or storage resources are exhausted?

   **Undefined behaviour that degrades into silent data loss.** Nothing is
   bounded: no chunk size, no streaming iterator, no cap on the `errors` list,
   no retention or partitioning on the table, and no backpressure. On memory
   exhaustion the OOM killer takes the process mid-batch, which lands squarely
   in Q4 — no checkpoint, so the rerun starts from zero and duplicates
   everything already committed. On disk exhaustion, `cursor.execute` raises
   `sqlite3.OperationalError: database or disk is full` inside
   `_save_transaction`; that propagates into `process_batch`'s blanket handler
   (`:120`), which counts it as one more failed record and keeps going — the
   pipeline grinds through the entire remaining batch losing every record, then
   reports `"pipeline_status": "completed"`. Storage exhaustion is thereby
   converted into 100% data loss with a success status. There is no preflight
   capacity check and no PRAGMA tuning: `journal_mode` is left at the default
   `delete` (verified), so the rollback journal doubles the write footprint at
   precisely the moment the disk is already full.

## Success Criteria

Your assessment should:
- Identify at least 4 major reliability risks
- Explain the potential impact on system availability
- Suggest specific improvements for resilience and performance
- Consider production monitoring and operational requirements
- Provide an appropriate reliability risk classification
- Make a defensible recommendation for production deployment

## Testing Instructions

```bash
cd starter/
pip install -r requirements.txt
pytest test_data_pipeline.py -v
```

The tests include scenarios for normal operation, error conditions, and load testing that will help you understand the system's reliability characteristics.

## Production Context

This exercise simulates real-world scenarios where:
- Batch processing systems must handle large data volumes reliably
- External API dependencies can fail or become unavailable
- Resource constraints in production environments require careful management
- System failures can have significant business and compliance impact
- Monitoring and alerting are essential for operational visibility

## Reliability Considerations

Consider these production requirements:
- **Availability:** System should maintain 99.5% uptime
- **Performance:** Process daily batches within 4-hour maintenance window
- **Scalability:** Handle 10x data growth over next 2 years
- **Recovery:** Resume processing after interruptions without data loss
- **Monitoring:** Provide visibility into processing status and errors
- **Compliance:** Maintain audit trails for financial data processing

Remember: Functional correctness in development doesn't guarantee production reliability. Your assessment must consider real-world operational challenges and failure scenarios.