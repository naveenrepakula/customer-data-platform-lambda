# Project Structure and Folder Guide

This document explains the folders and files in the Customer Data Platform Lambda project, what each one is for, and how the files work together.

## 1. Complete folder tree

```text
customer-data-platform/
│
├── .github/
│   └── workflows/
│       └── deploy.yml
│
├── infrastructure/
│   └── template.yaml
│
├── lambda/
│   └── validation/
│       └── handler.py
│
├── sample_data/
│   └── customers.csv
│
├── scripts/
│   └── deploy.sh
│
├── tests/
│   ├── integration/
│   │   └── test_s3_lambda_pipeline.py
│   ├── unit/
│   │   └── test_pipeline.py
│   └── conftest.py
│
├── .env.example
├── .gitignore
├── Makefile
├── pyproject.toml
├── README.md
├── PROJECT_STRUCTURE.md
└── requirements.txt
```

## 2. Folder-by-folder explanation

### `lambda/validation/`

This is the application code folder. It contains the Python code that runs inside AWS Lambda.

- `handler.py` — the main pipeline code. It reads a CSV object from S3, checks the input columns, cleans and transforms rows, separates valid and rejected rows, validates the transformed records, and writes output files and a JSON report to S3.
- `lambda_handler(event, context)` — the Lambda entry point called when the S3 event invokes the function.
- `read_csv()` — reads CSV text and checks required column names.
- `transform_records()` — trims field values, lowercases email addresses, and rejects records that fail row-level rules.
- `validate_transformed_data()` — checks required values, email format, and uniqueness of customer IDs after transformation.
- `records_to_csv()` — converts valid Python records back to CSV text.
- `process_file()` — coordinates reading, transformation, validation, and writing results to S3.

### `tests/`

This folder contains automated tests. Run them from the project root using `pytest -v`.

#### `tests/unit/`

- `test_pipeline.py` — tests individual Python functions, including CSV reading, missing headers, cleaning, duplicate detection, missing IDs, invalid email addresses, and post-transformation validation.

#### `tests/integration/`

- `test_s3_lambda_pipeline.py` — invokes the Lambda handler with a sample S3 event and a `FakeS3` object. It checks that the simulated end-to-end flow writes a processed CSV, rejected-record JSON, and report.
- This is an integration-style local simulation. It does not connect to an actual S3 bucket or AWS Lambda service.

#### `tests/conftest.py`

- `conftest.py` — shared pytest configuration and test import setup.

### `infrastructure/`

This folder contains infrastructure-as-code definitions.

- `template.yaml` — an AWS SAM/CloudFormation template that defines:
  - Raw S3 bucket for incoming CSV files.
  - Output S3 bucket for processed files, rejected records, and reports.
  - S3 event notification for new objects under `incoming/`.
  - Python 3.11 Lambda function and its environment variable.
  - IAM execution role and permissions for S3, CloudWatch Logs, and SQS.
  - SQS queue configured as the Lambda asynchronous dead-letter queue.
  - CloudWatch log group with 30-day retention.
  - CloudWatch alarms for Lambda errors and visible SQS messages.
  - CloudFormation outputs containing resource names.

The template describes the resources. They are created only after you deploy the stack to AWS.

### `sample_data/`

- `customers.csv` — example customer data that you can use for local learning and upload to the raw S3 bucket after deployment.

### `scripts/`

- `deploy.sh` — runs `sam build` and `sam deploy`. It defaults to the `dev` environment and can use `ENVIRONMENT` and `AWS_REGION` environment variables.

### `.github/workflows/`

- `deploy.yml` — GitHub Actions workflow. It runs pytest on pull requests and pushes to `main`. A push to `main` deploys the SAM application after tests pass.
- The AWS IAM role and GitHub OIDC trust configuration must be created separately. The workflow expects the GitHub repository variables `AWS_ROLE_TO_ASSUME` and `AWS_REGION`.

## 3. Root-level files

| File | Purpose |
|---|---|
| `README.md` | Main project documentation: architecture, AWS services, setup, tests, deployment, and operational notes. |
| `PROJECT_STRUCTURE.md` | This guide: explains each folder and file and how the project is organized. |
| `requirements.txt` | Python packages needed for the project and tests, including boto3, pytest, and Black. |
| `pyproject.toml` | Pytest and Black project configuration. |
| `Makefile` | Shortcuts for common development commands where Make is available. |
| `.gitignore` | Prevents local environments, caches, secrets, build outputs, and temporary files from being committed. |
| `.env.example` | Example environment-configuration placeholder. The Lambda currently receives its `OUTPUT_BUCKET` setting from the SAM template. |

## 4. How the files connect during a pipeline run

```text
sample_data/customers.csv
          |
          | upload to s3://RAW_BUCKET/incoming/
          v
Amazon S3 raw bucket
          |
          | ObjectCreated event
          v
infrastructure/template.yaml
          |
          | defines and connects the trigger
          v
lambda/validation/handler.py
          |
          +--> read and validate CSV header
          |
          +--> clean and transform customer rows
          |
          +--> validate transformed records
          |
          +--> write processed CSV to output S3 bucket
          |
          +--> write rejected rows JSON (when needed)
          |
          +--> write processing report JSON
          |
          +--> write execution logs to CloudWatch
          |
          +--> failed async invocation event -> SQS DLQ
```

## 5. Where to make common changes

| If you want to... | Start with... |
|---|---|
| Add a new transformation | `lambda/validation/handler.py`, then add unit tests in `tests/unit/test_pipeline.py`. |
| Add a new data-quality rule | `lambda/validation/handler.py`, then add positive and negative tests. |
| Change the required CSV columns | `REQUIRED_COLUMNS` in `handler.py`, update sample data and tests. |
| Change the S3 folders or AWS resources | `infrastructure/template.yaml` and the matching output-key logic in `handler.py`. |
| Change Lambda memory or timeout | `infrastructure/template.yaml`. |
| Change CloudWatch retention or alarms | `infrastructure/template.yaml`. |
| Change deployment defaults | `scripts/deploy.sh`. |
| Change CI/CD behavior | `.github/workflows/deploy.yml`. |
| Add or update sample input | `sample_data/customers.csv`. |

## 6. Recommended development sequence

1. Read `README.md` to understand the overall pipeline.
2. Inspect `sample_data/customers.csv` to understand the input format.
3. Read `lambda/validation/handler.py` to understand the processing logic.
4. Run `pytest -v` and read the tests to see how the logic is verified.
5. Review `infrastructure/template.yaml` to understand the AWS resources and event trigger.
6. Deploy to a development AWS environment only after checking account, region, permissions, and possible costs.
7. Upload the sample CSV and verify the output objects and CloudWatch logs.

## 7. Important distinction

The local tests verify the Python logic and a simulated S3-to-Lambda flow. They do not prove that the AWS infrastructure has been deployed successfully. A real AWS end-to-end test requires deploying the SAM stack into an AWS account and uploading a test file to the created raw S3 bucket.
