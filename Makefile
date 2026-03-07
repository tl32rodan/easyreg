.PHONY: test clean demo demo-rules

PYTHON?=python

test:
	$(PYTHON) -m unittest discover tests

clean:
	find . -name '*.pyc' -delete
	find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null || true
	rm -rf examples/runs examples/golden regression_report.md

demo:
	$(PYTHON) bin/easyreg run --config examples/simple_suite.json --report demo_report.md
	@echo "--- Report ---"
	@cat demo_report.md

demo-rules:
	$(PYTHON) bin/easyreg run --config examples/diff_rules_suite.json --report demo_rules_report.md
	@echo "--- Report ---"
	@cat demo_rules_report.md
