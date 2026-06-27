# Flaky Test Report: WorldEditor.test.tsx

**Date:** 2026-03-28
**Test:** `WorldEditor stepper > navigates forward and back through steps`
**File:** `frontend/src/components/master/__tests__/WorldEditor.test.tsx:65`

## Stress Test Results

| Mode | Runs | Failures | Rate |
|------|------|----------|------|
| Solo (only WorldEditor.test.tsx) | 20 | 3 | 15% |
| Full suite (18 test files, 136 tests) | 10 | 0 | 0% |

Full logs: `/tmp/we-stress-solo.txt`, `/tmp/we-stress-suite.txt`

Failure only manifests in solo runs (faster execution = tighter timing). In the full suite, concurrent test file processing slows execution enough that the race condition doesn't trigger.

## Failure Message

```
AssertionError: expected "vi.fn()" to be called with arguments: [ 'sword_vale', 'region' ]
Number of calls: 0

 ❯ src/components/master/__tests__/WorldEditor.test.tsx:70:34
```

Always line 70. `listEntities` has 0 calls — the useEffect hasn't fired yet.

## Root Cause

Race between `waitForStepper()` resolving and `EntityListEditor`'s `useEffect` firing.

### Execution flow:

1. Test calls `setup()` → renders `WorldEditor`
2. `WorldEditor.useEffect` fires → `getWorldManifest()` resolves → `setLayers(data.layers)`
3. Re-render: stepper buttons appear, `EntityListEditor` components mount for "region" and "location"
4. `waitForStepper()` resolves (buttons found in DOM)
5. **Test immediately checks** `mockApi.listEntities` on lines 70-71 — **synchronous, no `waitFor()`**
6. `EntityListEditor.useEffect` fires → calls `listEntities("sword_vale", "region")` and `listEntities("sword_vale", "location")`

Steps 4 and 6 race. In fast solo runs, step 5 executes before step 6. In the full suite, the extra concurrency delays step 5 enough that step 6 has already fired.

### The code pattern:

```tsx
// Line 68-71 (test)
await waitForStepper()                                              // ← waits for buttons only

expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "region")   // ← NOT in waitFor()
expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "location") // ← NOT in waitFor()
```

Compare with lines 76-78 (same test, correct pattern):
```tsx
await waitFor(() => {
  expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "nation")
})
```

## Fix

Wrap the synchronous assertions in `waitFor()`:

```tsx
await waitForStepper()

await waitFor(() => {
  expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "region")
  expect(mockApi.listEntities).toHaveBeenCalledWith("sword_vale", "location")
})
```

This is a one-line fix. The rest of the test already uses `waitFor()` for similar assertions.

## Why full suite doesn't fail

Vitest runs test files in parallel workers. When 18 files run simultaneously, system load increases, event loop ticks take longer, and by the time `waitForStepper()` resolves and the test thread gets back to the assertion, the useEffect has already queued and flushed. In solo mode, the event loop is nearly idle, so the assertion executes in the same microtask batch before useEffect gets a chance to fire.
