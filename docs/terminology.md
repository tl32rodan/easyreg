# easyreg Terminology

| Term | Definition |
|------|-----------|
| **Suite** | A collection of regression test cases, defined by a single JSON config file |
| **Case** | A single test unit: command + input → output directory |
| **Golden** | Verified expected output stored on the filesystem as a reference |
| **Run** | A single execution that produces actual output |
| **Diff Rule** | A filter/transform rule applied during comparison (e.g., ignore timestamps) |
| **Verdict** | Comparison result: PASS, FAIL, NEW (no golden exists), or ERROR (execution failed) |
| **Promotion** | Upgrading a run's output to become the new golden reference |
| **diff_rules_mode** | How case-level rules merge with global rules: `append` (default) or `override` |
