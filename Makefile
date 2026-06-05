.PHONY: test eval doctor demo mcp-smoke verify install-dev clean

install-dev:
	python3 -m pip install -e . --no-build-isolation

test:
	python3 -m unittest discover -s tests

eval:
	python3 -m zerker_memory eval

doctor:
	python3 -m zerker_memory doctor

demo:
	bash examples/demo.sh

mcp-smoke:
	python3 examples/mcp_smoke.py

verify: test eval doctor demo mcp-smoke

clean:
	rm -rf build dist *.egg-info .pytest_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
