# Examples

This directory contains sample regression suites to help you get started with
easyreg. Two suites are provided:

| File | Purpose |
|---|---|
| `simple_suite.json` | Minimal one-case suite — good first demo |
| `diff_rules_suite.json` | Shows diff rules: ignore timestamps, PIDs, log files |

---

## Quick-start script

Run this from the **project root** to see both suites end-to-end:

```bash
#!/usr/bin/env bash
set -e

# Step 1 – run the simple suite (outputs are NEW on first run)
python -m easyreg run --config examples/simple_suite.json --report /tmp/simple_report.md
echo "=== simple_suite: first run ==="
cat /tmp/simple_report.md

# Step 2 – promote outputs to golden
python -m easyreg promote --config examples/simple_suite.json
echo "=== Promoted simple_suite to golden ==="

# Step 3 – run again; all cases should now PASS
python -m easyreg run --config examples/simple_suite.json --report /tmp/simple_report.md
echo "=== simple_suite: second run (expect PASS) ==="
cat /tmp/simple_report.md

# Step 4 – run the diff_rules suite (NEW on first run)
python -m easyreg run --config examples/diff_rules_suite.json --report /tmp/rules_report.md
echo "=== diff_rules_suite: first run ==="
cat /tmp/rules_report.md

# Step 5 – promote diff_rules outputs to golden
python -m easyreg promote --config examples/diff_rules_suite.json
echo "=== Promoted diff_rules_suite to golden ==="

# Step 6 – run again; all cases should PASS despite dynamic content
python -m easyreg run --config examples/diff_rules_suite.json --report /tmp/rules_report.md
echo "=== diff_rules_suite: second run (expect PASS) ==="
cat /tmp/rules_report.md
```

You can also run each suite via the Makefile shortcuts:

```bash
make demo          # simple_suite  — run → promote → run
make demo-rules    # diff_rules_suite
```

---

## Step-by-step regression workflow

### Step 1 — Run the suite (first time)

```bash
python -m easyreg run --config examples/simple_suite.json --report report.md
```

Because no golden reference exists yet, every case is reported as **NEW**.

**Expected output (`report.md`):**

```
# Regression Report

| Case  | Verdict |
|-------|---------|
| hello | NEW     |

Summary: 0 PASS, 0 FAIL, 1 NEW, 0 ERROR
```

> `NEW` means the case ran successfully but has no golden to compare against.
> No action is needed — proceed to Step 2.

---

### Step 2 — Promote outputs to golden

```bash
python -m easyreg promote --config examples/simple_suite.json
```

**Expected console output:**

```
Promoted: hello
```

This copies `examples/runs/hello/` → `examples/golden/hello/`.
The golden directory now contains the accepted reference output.

---

### Step 3 — Run the suite again

```bash
python -m easyreg run --config examples/simple_suite.json --report report.md
```

**Expected output (`report.md`):**

```
# Regression Report

| Case  | Verdict |
|-------|---------|
| hello | PASS    |

Summary: 1 PASS, 0 FAIL, 0 NEW, 0 ERROR
```

All cases **PASS** — the current output matches the golden reference.

---

### Step 4 — Introduce a regression (optional experiment)

Edit `simple_suite.json` and change the command to produce different output,
then re-run:

```bash
python -m easyreg run --config examples/simple_suite.json --report report.md
```

**Expected output:**

```
# Regression Report

| Case  | Verdict |
|-------|---------|
| hello | FAIL    |

Summary: 0 PASS, 1 FAIL, 0 NEW, 0 ERROR

### hello — FAIL
...diff details...
```

A **FAIL** means the output no longer matches golden. Fix the regression or
promote again if the change is intentional.

---

### Step 5 — Diff-rules suite

The `diff_rules_suite.json` suite demonstrates how to ignore dynamic content
(timestamps, PIDs, log files) so regressions aren't caused by noise:

```bash
python -m easyreg run     --config examples/diff_rules_suite.json --report report.md
python -m easyreg promote --config examples/diff_rules_suite.json
python -m easyreg run     --config examples/diff_rules_suite.json --report report.md
```

**Expected final output (`report.md`):**

```
# Regression Report

| Case            | Verdict |
|-----------------|---------|
| with_timestamp  | PASS    |
| custom_rules    | PASS    |

Summary: 2 PASS, 0 FAIL, 0 NEW, 0 ERROR
```

Lines matching `^# Generated at` and tokens matching `PID=\d+` are stripped
before comparison, so they never cause false failures.

---

## Output directory layout

After running both suites you will see:

```
examples/
  golden/
    hello/              ← promoted golden for simple_suite
      greeting.txt
    with_timestamp/     ← promoted golden for diff_rules_suite
      report.txt
    custom_rules/
      output.txt
  runs/
    hello/              ← latest run output
      greeting.txt
    with_timestamp/
      report.txt
    custom_rules/
      output.txt
```

> `examples/runs/` and `examples/golden/` are git-ignored; they are always
> regenerated locally and should not be committed.

---

## Verdict reference

| Verdict | Meaning |
|---------|---------|
| `PASS`  | Output matches golden exactly (after diff rules applied) |
| `FAIL`  | Output differs from golden — check the diff in the report |
| `NEW`   | No golden reference exists yet — promote to accept |
| `ERROR` | The case command exited with a non-zero return code |
