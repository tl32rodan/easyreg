# RegressionX Architecture

## Overview

RegressionX is a regression testing platform that gives teams confidence to
refactor and evolve code. It executes test cases, compares outputs against
golden references, and produces reports — all with zero external dependencies.

## Module Structure

```
regressionx/
├── model.py             # Data models: Suite, Case, DiffRule, Verdict, etc.
├── config.py            # JSON config loading, validation, placeholder expansion
├── golden.py            # Golden reference management (CRUD, promotion, backup)
├── cli.py               # CLI entry point and command dispatch
│
├── comparator/          # Comparison engine
│   ├── __init__.py      # compare_directories() + ComparisonResult
│   └── diff_rules.py    # Rule engine: ignore_line/regex/file/folder
│
├── runner/              # Execution engines (extensible)
│   ├── __init__.py
│   └── subprocess_runner.py  # Local subprocess execution
│
└── reporter/            # Report generators (extensible)
    ├── __init__.py
    └── markdown.py      # Markdown report output
```

## Core Workflow

```
Suite JSON → Runner → Comparator (+ DiffRules) → Reporter
                          ↕
                    Golden Manager
```

1. **Load**: Parse JSON config into Suite/Case objects
2. **Execute**: Runner executes each case command in an isolated sandbox
3. **Compare**: Comparator diffs output against golden, applying diff rules
4. **Verdict**: PASS / FAIL / NEW (no golden) / ERROR (execution failed)
5. **Report**: Generate Markdown report with summary and failure details
6. **Promote**: Optionally update golden references with new outputs

## Extension Points

- **Runner**: Implement new runners (e.g., LSF) in `runner/` package
- **Reporter**: Add formats (e.g., JSON) in `reporter/` package
- **DiffRules**: Add new rule types in `comparator/diff_rules.py`

## Design Constraints

- Zero external dependencies (Python stdlib only)
- Python 3.8+
- JSON config format
- Filesystem-based golden reference storage
