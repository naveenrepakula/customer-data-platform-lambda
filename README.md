# Customer Data Platform — Lambda-Based Data Engineering Pipeline

## 1. Project overview

This project is a beginner-friendly, end-to-end customer data pipeline built with **Python, Amazon S3, AWS Lambda, Amazon SQS, Amazon CloudWatch, IAM, and AWS SAM/CloudFormation**.

The pipeline receives customer CSV files in S3, validates and cleans the records with Python inside Lambda, validates the transformed data, and stores valid and rejected records separately.

**This project does not use AWS Glue, PySpark, pandas, Step Functions, or Airflow.** All data processing is performed by one Python Lambda function.

## 2. AWS services used

| AWS service | How it is used in this project |
|---|---|
| Amazon S3 | Stores incoming CSV files and the processed CSV, rejected-record JSON, and processing report. |
| AWS Lambda | Runs the Python validation and transformation pipeline when an incoming file is uploaded. |
| Amazon SQS | Acts as the Lambda asynchronous dead-letter queue (DLQ) for failed invocation events. |
| Amazon CloudWatch Logs | Stores Lambda execution logs for troubleshooting. |
| Amazon CloudWatch Alarms | Monitors Lambda errors and visible messages in the SQS failure queue. |
| AWS IAM | Gives Lambda only the permissions defined in the template for logs, S3 access, and SQS. |
| AWS SAM / AWS CloudFormation | Defines and deploys the AWS resources from `infrastructure/template.yaml`. |

The project defines these resources as infrastructure code. They are **not created in your AWS account until you deploy the stack**.

## 3. End-to-end data flow

1. A user uploads a customer CSV file to the raw S3 bucket under `incoming/`.
2. An S3 `ObjectCreated` event invokes the Lambda function.
3. Lambda reads the CSV file from S3.
4. Input validation checks that the required columns exist: `customer_id`, `customer_name`, and `email`.
5. Python transformations trim whitespace and convert email addresses to lowercase.
6. Data-quality rules reject records with missing customer IDs, missing customer names, invalid email addresses, or duplicate customer IDs. The first valid occurrence of a customer ID is kept.
7. A second validation checks the transformed records for required values, valid email formats, and unique customer IDs.
8. Valid records are saved as a processed CSV in the output S3 bucket.
9. Rejected records are saved as JSON when rejected rows exist.
10. A JSON processing report is saved with input, transformed, and rejected counts, validation results, and output locations.
11. CloudWatch stores execution logs and evaluates the configured alarms. Failed asynchronous Lambda invocation events are sent to the SQS DLQ.

### S3 output locations

| S3 key prefix | Contents |
|---|---|
| `incoming/` in the raw bucket | Files waiting to be processed |
| `processed/customers/` in the output bucket | Cleaned and validated CSV files |
| `failed/records/` in the output bucket | Rejected records and their rejection reasons |
| `failed/reports/` in the output bucket | JSON processing reports |

## 4. Project folder structure

See **[PROJECT_STRUCTURE.md](PROJECT_STRUCTURE.md)** for the detailed folder-by-folder and file-by-file explanation.

```text
customer-data-platform/
├── .github/
│   └── workflows/
│       └── deploy.yml
├── infrastructure/
│   └── template.yaml
├── lambda/
│   └── validation/
│       └── handler.py
├── sample_data/
│   └── customers.csv
├── scripts/
│   └── deploy.sh
├── tests/
│   ├── integration/
│   │   └── test_s3_lambda_pipeline.py
│   ├── unit/
│   │   └── test_pipeline.py
│   └── conftest.py
├── .env.example
├── .gitignore
├── Makefile
├── pyproject.toml
├── README.md
├── PROJECT_STRUCTURE.md
└── requirements.txt
```

## 5. Data validation and transformation rules

### Required input columns

- `customer_id`
- `customer_name`
- `email`

### Transformations

- Remove leading and trailing spaces from field values.
- Convert email addresses to lowercase.
- Keep the first valid record for a customer ID.

### Rejection rules

- Missing `customer_id`
- Missing `customer_name`
- Missing or invalid `email`
- Duplicate `customer_id`

Rejected records include the CSV line number, cleaned record, and rejection reason.

### Post-transformation checks

- Required fields are populated.
- Email values match the project's basic email-format pattern.
- Customer IDs are unique.

If the post-transformation checks fail, the Lambda raises an error rather than writing the processed output as successful.

## 6. Run the project locally

### Prerequisites

- Python 3.11
- pip
- Git (optional, for version control)

Open a terminal in the project root.

### Windows PowerShell

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest -v
```

### Linux / macOS

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pytest -v
```

The test suite currently contains **10 tests**: 9 unit tests and 1 integration-style test. The integration-style test uses a small in-memory `FakeS3` object to simulate S3 reads and writes. It does not call AWS and does not require AWS credentials or create AWS resources.

## 7. Deploy to AWS

### Prerequisites

1. An AWS account.
2. AWS CLI installed and configured with credentials for the target account.
3. AWS SAM CLI installed.
4. Permission to create the resources in the SAM template, including S3, Lambda, IAM, SQS, CloudWatch Logs, CloudWatch Alarms, and the SAM deployment resources.

Check your setup:

```bash
aws sts get-caller-identity
aws configure get region
sam --version
```

### Deploy

From the project root:

```bash
bash scripts/deploy.sh
```

The script builds and deploys the SAM template. By default, it uses the `dev` environment and the AWS CLI's configured region. You can override these values:

```bash
ENVIRONMENT=test AWS_REGION=ap-south-1 bash scripts/deploy.sh
```

You can also run the SAM commands manually:

```bash
sam build --template-file infrastructure/template.yaml

sam deploy \
  --template-file .aws-sam/build/template.yaml \
  --stack-name customer-data-platform-dev \
  --capabilities CAPABILITY_IAM \
  --resolve-s3 \
  --parameter-overrides Environment=dev
```

Review the proposed changes and AWS charges before confirming deployment.

### Get deployed resource names

```bash
aws cloudformation describe-stacks \
  --stack-name customer-data-platform-dev \
  --query "Stacks[0].Outputs"
```

The stack outputs include the raw bucket name, output bucket name, Lambda function name, and SQS failure queue URL.

## 8. Run an end-to-end test in AWS

After a successful deployment, copy the raw bucket name from the CloudFormation outputs and upload the sample file:

```bash
aws s3 cp sample_data/customers.csv \
  s3://YOUR_RAW_BUCKET/incoming/customers.csv
```

The S3 event should invoke Lambda automatically.

Check Lambda logs:

```bash
aws logs tail /aws/lambda/cdp-customer-pipeline-dev --follow
```

Check the output bucket:

```bash
aws s3 ls s3://YOUR_OUTPUT_BUCKET/processed/customers/
aws s3 ls s3://YOUR_OUTPUT_BUCKET/failed/records/
aws s3 ls s3://YOUR_OUTPUT_BUCKET/failed/reports/
```

The rejected-record folder may not contain a new object if the input file has no rejected rows.

## 9. Tests included

| Test area | What is checked |
|---|---|
| CSV reading | A valid CSV can be read. |
| Header validation | Missing required columns cause an error. |
| Cleaning | Whitespace is trimmed and email is lowercased. |
| Duplicate handling | Duplicate customer IDs are rejected. |
| Required data | A missing customer ID is rejected. |
| Email validation | An invalid email is rejected. |
| Output validation | Valid transformed data passes validation. |
| Duplicate output check | Duplicate IDs fail post-transformation validation. |
| Email output check | Invalid emails fail post-transformation validation. |
| Pipeline integration-style test | A simulated S3 event runs the Lambda flow and checks the processed CSV, rejected JSON, and report. |

Run all tests:

```bash
pytest -v
```

## 10. CI/CD workflow

The GitHub Actions workflow at `.github/workflows/deploy.yml`:

- Runs tests for pull requests targeting `main`.
- Runs tests for pushes to `main`.
- Deploys after tests pass on a push to `main`.

Before enabling deployment, configure these GitHub repository variables:

- `AWS_ROLE_TO_ASSUME`
- `AWS_REGION`

You must also create/configure an AWS IAM role trusted by GitHub Actions using GitHub OIDC, with the permissions needed to deploy the SAM stack. The workflow does not create that trust role for you.

## 11. Important learning and production notes

- The Lambda reads the complete CSV into memory. This simple implementation is intended for small or medium files, not very large datasets.
- S3 event notifications are delivered at least once, so duplicate event delivery is possible. The output object keys are deterministic, which means a retry for the same input filename can overwrite the same output objects.
- Files with the same base filename in different input paths can map to the same output key. Use unique input filenames or enhance the key-generation strategy before using this design for multiple producers.
- The current SQS DLQ is for failed asynchronous Lambda invocation events. It is not a row-level rejection queue; row-level rejects are written to S3.
- The CloudWatch alarms are configured, but no SNS topic or email notification subscription is included.
- The local integration-style test uses `FakeS3`; it is not a real AWS integration test.
- The project has not been deployed or verified in your AWS account just by downloading it. Run the deployment steps and verify the resources in your account.
- Before production use, review IAM permissions, data privacy/PII handling, encryption, retention, alert notifications, retry behavior, file-size limits, idempotency, and cost.

## 12. Quick command reference

```bash
# Install dependencies
pip install -r requirements.txt

# Run tests
pytest -v

# Build the SAM application
sam build --template-file infrastructure/template.yaml

# Deploy
bash scripts/deploy.sh

# Follow Lambda logs
aws logs tail /aws/lambda/cdp-customer-pipeline-dev --follow
```
