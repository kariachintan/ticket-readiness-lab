.PHONY: install test demo
install:
	pip install -e ".[dev]"
test:
	python -m pytest --cov=ticket_readiness --cov-report=term-missing
demo:
	ticket-readiness review data/tickets/*.md
