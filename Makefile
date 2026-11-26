install:
	python -m pip install -r requirements.txt

test:
	pytest -v

test-unit:
	pytest -v tests/unit

test-integration:
	pytest -v tests/integration

build:
	sam build --template-file infrastructure/template.yaml

deploy:
	bash scripts/deploy.sh
