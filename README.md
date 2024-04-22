# Mini Social

## Installation
1. Clone the project
2. Install [poetry](https://python-poetry.org/)
3. Run `poetry install --with=dev,docs,test,static-analysis,types`

## Usage
### Run the tests
1. Run `poetry run pytest`
### Run the server
1. Run `poetry run uvicorn app.main:app --reload`
### See Docs
1. Run `poetry run mkdocs serve`
