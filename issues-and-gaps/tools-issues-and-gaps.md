# Tools Component — Issues & Gaps

Reviewed against `src/tools/` implementation and `specs/tools/` spec files.

---

## Review 4 — Post-Fix (2026-06-04)

Issues 16–18 fixed. Spec-aligned audit loop completed (2 iterations). One additional concurrency gap found and fixed during audit.

| # | Status |
|---|--------|
| 1–19 | ✅ Fixed or Accepted |

All 15 tests in `tests/tools/test_tools_fixes.py` pass. No open issues remain except #11 (Accepted).

---

### 19. Sync `pending_*` and `prune_expired_*` mutated state without lock
**File:** `executor.py:304–335`  
**Severity:** 🟡 Medium  
**Found:** Review 4 audit iteration 1  

`pending_approvals()`, `pending_failures()`, `prune_expired_approvals()`, and `prune_expired_failures()` called `_prune_expired_*()` and read module-level dicts without acquiring `_STATE_LOCK`, while async paths held the lock. Concurrent sync/async access could race.

**Fix:** Replaced `asyncio.Lock` with `threading.RLock` and consolidated all locked mutations into sync `_*_locked()` helpers invoked via `asyncio.to_thread()` from async code and `with _STATE_LOCK:` from sync code.

---

## Review 3 — Post-Fix (2026-06-06)

All 15 prior issues confirmed fixed or accepted. Three new issues identified.

| # | Status |
|---|--------|
| 1–15 | ✅ Fixed or Accepted |
| 16 | ✅ Fixed |
| 17 | ✅ Fixed |
| 18 | ✅ Fixed |

---

### 16. `_PAUSED_CHAINS` accessed without `_STATE_LOCK` in `resolve_approval` and `resolve_failure`
**File:** `executor.py:163–194` (resolve_approval), `executor.py:216–222` (resolve_failure)  
**Severity:** 🟡 Medium  

All writes to `_PAUSED_CHAINS` (in `_continue_chain` and `execute_chain`) are guarded by `_STATE_LOCK`. However, all reads and pops in `resolve_approval` (6 accesses across 3 branches) and `resolve_failure` (4 accesses across 2 branches) are not guarded. If two approval or failure resolutions run concurrently for different steps in the same chain, they can race on the dict.

---

### 17. `empty_chain` ToolResult not logged
**File:** `executor.py:253–259`  
**Severity:** 🔵 Minor  

```python
if not chain.results:
    return ToolResult(success=False, ..., error="empty_chain")
```

This error path in `_continue_chain` returns without calling `_finalize_result`, so nothing is written to the tool log. Issue 15's fix addressed the `not outcome.success` branch one level up; this adjacent path was missed.

---

### 18. `should_retry` early-exit branch is unreachable
**File:** `failure.py:45–46`  
**Severity:** 🔵 Minor  

```python
if not should_retry(first_result, attempts=0):
    return make_failure_event(call, first_result)
```

`should_retry` returns `True` when `not result.success AND attempts < MAX_RETRIES`. At this call site, `attempts=0` and `MAX_RETRIES=1`, so `0 < 1` is always `True` when the result failed — meaning `not should_retry(...)` is always `False`. This guard branch can never be taken and is dead code for any `MAX_RETRIES >= 1`.

---

## Review 2 — Post-Fix (2026-06-06)

All 12 original issues confirmed fixed. Three new issues identified.

| # | Status |
|---|--------|
| 1–12 | ✅ Fixed |
| 13 | ✅ Fixed |
| 14 | ✅ Fixed |
| 15 | ✅ Fixed |

---

### 13. `_APPROVAL_CHAIN_MAP.pop` is outside `_STATE_LOCK`
**File:** `executor.py:151`  
**Severity:** 🔴 Critical  

`_pop_approval()` acquires `_STATE_LOCK` to remove the event from `_PENDING_APPROVALS`, but immediately after, `_APPROVAL_CHAIN_MAP.pop(event_id, None)` runs bare — without the lock. All writes to `_APPROVAL_CHAIN_MAP` are guarded in `_store_approval` and `_continue_chain`, but this read-and-remove is not. Under concurrent approval resolution this is a data race.

---

### 14. `_PENDING_FAILURES` has no TTL or pruning
**File:** `executor.py:278`  
**Severity:** 🟡 Medium  

`_PENDING_APPROVALS` gained TTL pruning as part of the issue #7 fix, but `_PENDING_FAILURES` has no equivalent. Unresolved `FailureEvent`s accumulate indefinitely with no expiry mechanism.

---

### 15. Failed `ToolResult` inside `_continue_chain` is returned unlogged
**File:** `executor.py:239–240`  
**Severity:** 🔵 Minor  

```python
if not outcome.success:
    return outcome
```

A `ToolResult(success=False)` returned at this branch (e.g. from a communication send-denial within a chain) bypasses `_finalize_result`, so nothing is written to the tool log for that failure. All other failure paths call `_finalize_result` before returning.

---

## Review 1 — Initial (2026-06-06)

---

## 🔴 Critical

### 1. Retry logic is dead code
**Files:** `executor.py`, `failure.py`  
**Spec nodes:** P, Q, R, S  

`should_retry()` and `escalation_message()` are defined in `failure.py` but never called from `executor.py`. The spec mandates one automatic retry before escalating to the user. No tool failure ever retries — every failure is returned directly without going through nodes P → Q → R → S.

---

### 2. `resolve_approval` crashes on unknown `event_id`
**File:** `executor.py:72`  

`_PENDING_APPROVALS.pop(event_id)` raises `KeyError` if the ID is unknown or already resolved. No guard exists — any stale, duplicate, or replayed approval response crashes the executor instead of returning a safe error.

---

### 3. `subprocess.TimeoutExpired` is unhandled in `run_sandboxed`
**File:** `sandbox.py:50–63`  
**Spec node:** M  

When a tool exceeds `timeout_seconds`, `subprocess.run` raises `TimeoutExpired`. This is not caught, so it propagates as an unhandled exception instead of returning a `ToolResult(success=False, ...)`.

---

### 4. `json.JSONDecodeError` unhandled in `_parse_worker_output` (stdout path)
**File:** `sandbox.py:33`  
**Spec node:** M  

If the sandbox worker exits non-zero but wrote malformed or partial JSON to stdout, `json.loads(stdout)` raises `JSONDecodeError`. The stderr path has a try/except for this, but the stdout path does not.

---

### 5. `organize` operation registered but not implemented
**Files:** `registry.py:35`, `builtin/file_management.py`  
**Spec node:** B  

`file_management.operation_action_types` includes `"organize": DESTRUCTIVE`, but `handle()` falls through to `raise NotImplementedError("Unsupported file operation: organize")` — a guaranteed runtime failure for any call using that operation.

---

## 🟡 Medium

### 6. Tool chaining is entirely unintegrated
**Files:** `chaining.py`, `executor.py`  
**Spec nodes:** D, T  

`ToolChain` and `should_continue_chain()` exist but are never imported or called from the executor. The spec's chain-continuation nodes `D` and `T` have no runtime path — multi-tool chains cannot be orchestrated.

---

### 7. `_PENDING_APPROVALS` has no TTL or cleanup
**File:** `executor.py:20`  

Approvals that are never resolved (e.g. user closes the UI) accumulate in the module-level dict indefinitely. Over a long session this is a memory leak and unbounded process state with no expiry mechanism.

---

### 8. `pending_approvals()` not exported from the public API
**File:** `__init__.py`  

`pending_approvals()` is defined in `executor.py` and needed by the brain pipeline and orchestrator to render approval cards, but it is never re-exported from `__init__.py`, making it invisible to consumers of the public API.

---

### 9. `enforce_draft_local_only` exception propagates uncaught from `execute_tool`
**Files:** `executor.py`, `approval.py:47`  
**Spec node:** J  

If a `communication` call has `action="send"`, `draft_communication()` raises `ValueError` before the `ApprovalEvent` is created or stored. This exception propagates through `execute_tool` as an unhandled error instead of returning a denied `ToolResult`.

---

## 🔵 Design / Minor

### 10. Communication `resolve_approval` logs the unsanitized `tool_call`
**File:** `executor.py:77–85`  
**Spec node:** PR3  

The approved communication path stores `tool_call=event.tool_call` in the result — the original, pre-sanitization call. Recipient address and draft body (potential PII) get written to the local tool log. All other paths log the sanitized copy.

---

### 11. Double subprocess for `code_execution`
**Files:** `sandbox.py`, `builtin/code_execution.py`  
**Spec node:** M  

The sandboxed path spawns `sandbox_worker.py` as a subprocess, which then calls `code_execution.handle()`, which spawns a third process (`subprocess.run([sys.executable, "-c", code])`). The outer sandbox layer adds overhead without providing meaningful additional isolation beyond what `code_execution.handle()` already does.

---

### 12. `_PENDING_APPROVALS` is not concurrency-safe
**File:** `executor.py:20`  

The module-level `dict` is accessed from async handlers without any locking. Concurrent approval resolutions (e.g. two events resolved in the same event loop tick) could corrupt state.

---

## Summary

| # | Severity | File(s) | Spec Nodes | Status |
|---|----------|---------|------------|--------|
| 1 | 🔴 Critical | `executor.py`, `failure.py` | P, Q, R, S | ✅ Fixed |
| 2 | 🔴 Critical | `executor.py:72` | — | ✅ Fixed |
| 3 | 🔴 Critical | `sandbox.py:50` | M | ✅ Fixed |
| 4 | 🔴 Critical | `sandbox.py:33` | M | ✅ Fixed |
| 5 | 🔴 Critical | `registry.py`, `file_management.py` | B | ✅ Fixed |
| 6 | 🟡 Medium | `chaining.py`, `executor.py` | D, T | ✅ Fixed |
| 7 | 🟡 Medium | `executor.py:20` | — | ✅ Fixed |
| 8 | 🟡 Medium | `__init__.py` | U | ✅ Fixed |
| 9 | 🟡 Medium | `executor.py`, `approval.py` | J | ✅ Fixed |
| 10 | 🔵 Minor | `executor.py:77` | PR3 | ✅ Fixed |
| 11 | 🔵 Minor | `sandbox.py`, `code_execution.py` | M | Accepted |
| 12 | 🔵 Minor | `executor.py:20` | — | ✅ Fixed |
| 13 | 🔴 Critical | `executor.py:151` | — | ✅ Fixed |
| 14 | 🟡 Medium | `executor.py:278` | — | ✅ Fixed |
| 15 | 🔵 Minor | `executor.py:239` | LOG | ✅ Fixed |
| 16 | 🟡 Medium | `executor.py:163–222` | — | ✅ Fixed |
| 17 | 🔵 Minor | `executor.py:253` | LOG | ✅ Fixed |
| 18 | 🔵 Minor | `failure.py:45` | P, Q | ✅ Fixed |
| 19 | 🟡 Medium | `executor.py:304–335` | — | ✅ Fixed |
