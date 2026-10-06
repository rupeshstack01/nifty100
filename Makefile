.PHONY: load ratios test report dashboard api clean

load:
	python -m src.etl.loader

ratios:
	python -m src.etl.validator

test:
	pytest -q

report:
	python -m src.etl.validator

dashboard:
	@echo "Dashboard target reserved for later sprint."

api:
	@echo "API target reserved for later sprint."

clean:
	find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
