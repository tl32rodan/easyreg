# easyreg

**Easy regression testing — run, compare, promote.**

easyreg is a lightweight, zero-dependency Python tool for building regression
test suites. It executes test case commands, compares outputs against golden
references, and reports `PASS` / `FAIL` / `NEW` / `ERROR` — giving your team
confidence to refactor without fear.

## Key Features

- **Golden-based comparison**: verified expected output stored on the filesystem
- **Configurable diff rules**: ignore timestamps, PIDs, log files, and more
- **Parallel execution**: run cases concurrently with `--parallel N`
- **Multiple report formats**: Markdown (human) and JSON (CI/CD)
- **MCP server**: expose easyreg as AI agent tools via `mcp_server.py`
- **Zero dependencies**: pure Python 3.8+, no `pip install` needed (except FastMCP for MCP server)

## Quick Start

1. **Define a suite config** (`my_suite.json`):

    ```json
    {
      "suite": "my_test",
      "golden_dir": "golden/{case}",
      "output_dir": "runs/{case}",
      "cases": [
        {
          "name": "hello",
          "command": "echo 'Hello, World!' > greeting.txt"
        }
      ]
    }
    ```

2. **Run the suite**:

    ```bash
    python -m easyreg run --config my_suite.json
    ```

3. **First run — promote outputs to golden**:

    ```bash
    python -m easyreg promote --config my_suite.json
    ```

4. **Subsequent runs compare against golden**:

    ```bash
    python -m easyreg run --config my_suite.json
    # → PASS
    ```

## CLI Commands

```bash
easyreg run     --config suite.json              # Execute cases + compare golden
easyreg run     --config suite.json --case hello # Run a single case
easyreg run     --config suite.json --parallel 4 # Run cases in parallel
easyreg compare --config suite.json              # Compare existing outputs (no re-run)
easyreg promote --config suite.json              # Promote outputs to golden
easyreg golden  --config suite.json --status     # Show golden reference status
```

Report format (default Markdown, or JSON for CI):

```bash
easyreg run --config suite.json --report-format json --report result.json
```

## Development

```bash
make test          # Run all tests
make demo          # Run the simple demo
make demo-rules    # Run the diff rules demo
make clean         # Remove generated artifacts
```

## MCP Server (AI Agent integration)

```bash
pip install fastmcp
python mcp_server.py   # stdio transport
```

See [SKILL.md](SKILL.md) for the full agent usage guide.
