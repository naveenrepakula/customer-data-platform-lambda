"""S3-triggered customer CSV validation and transformation Lambda."""
import csv
import io
import json
import logging
import os
import re
import urllib.parse
from datetime import datetime, timezone

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)
REQUIRED_COLUMNS = ["customer_id", "customer_name", "email"]
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
s3 = boto3.client("s3")


def read_csv(file_text):
    reader = csv.DictReader(io.StringIO(file_text))
    if not reader.fieldnames:
        raise ValueError("CSV file is empty or has no header")
    missing = [name for name in REQUIRED_COLUMNS if name not in reader.fieldnames]
    if missing:
        raise ValueError("Missing required columns: " + ", ".join(missing))
    return list(reader)


def transform_records(records):
    transformed, rejected, seen_ids = [], [], set()
    for line_number, row in enumerate(records, start=2):
        clean = {key: (value or "").strip() for key, value in row.items()}
        clean["customer_id"] = clean.get("customer_id", "").strip()
        clean["customer_name"] = clean.get("customer_name", "").strip()
        clean["email"] = clean.get("email", "").strip().lower()

        reason = None
        if not clean["customer_id"]:
            reason = "customer_id is missing"
        elif not clean["customer_name"]:
            reason = "customer_name is missing"
        elif not clean["email"] or not EMAIL_PATTERN.match(clean["email"]):
            reason = "email is missing or invalid"
        elif clean["customer_id"] in seen_ids:
            reason = "duplicate customer_id"

        if reason:
            rejected.append({"line_number": line_number, "record": clean, "reason": reason})
        else:
            seen_ids.add(clean["customer_id"])
            transformed.append(clean)
    return transformed, rejected


def validate_transformed_data(records):
    errors = []
    ids = [row.get("customer_id", "") for row in records]
    for number, row in enumerate(records, start=1):
        for column in REQUIRED_COLUMNS:
            if not row.get(column):
                errors.append(f"row {number}: {column} is empty")
        email = row.get("email", "")
        if email and not EMAIL_PATTERN.match(email):
            errors.append(f"row {number}: email format is invalid")
    if len(ids) != len(set(ids)):
        errors.append("customer_id contains duplicates")
    return {
        "passed": not errors,
        "row_count": len(records),
        "unique_customer_ids": len(set(ids)),
        "errors": errors,
    }


def records_to_csv(records, fieldnames):
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=fieldnames, extrasaction="ignore")
    writer.writeheader()
    writer.writerows(records)
    return output.getvalue()


def process_file(bucket, key):
    response = s3.get_object(Bucket=bucket, Key=key)
    source_text = response["Body"].read().decode("utf-8-sig")
    input_records = read_csv(source_text)
    good_records, rejected_records = transform_records(input_records)

    quality = validate_transformed_data(good_records)
    if not quality["passed"]:
        raise ValueError("Post-transformation validation failed: " + "; ".join(quality["errors"]))

    output_bucket = os.environ["OUTPUT_BUCKET"]
    file_name = key.split("/")[-1].rsplit(".", 1)[0]
    output_key = f"processed/customers/{file_name}.processed.csv"
    rejected_key = f"failed/records/{file_name}.rejected.json"
    report_key = f"failed/reports/{file_name}.report.json"
    columns = list(input_records[0].keys()) if input_records else REQUIRED_COLUMNS

    s3.put_object(
        Bucket=output_bucket, Key=output_key,
        Body=records_to_csv(good_records, columns).encode("utf-8"),
        ContentType="text/csv",
    )
    if rejected_records:
        s3.put_object(
            Bucket=output_bucket, Key=rejected_key,
            Body=json.dumps(rejected_records, indent=2).encode("utf-8"),
            ContentType="application/json",
        )

    report = {
        "source_bucket": bucket,
        "source_key": key,
        "input_count": len(input_records),
        "transformed_count": len(good_records),
        "rejected_count": len(rejected_records),
        "post_transformation_validation": quality,
        "processed_output": output_key,
        "rejected_output": rejected_key if rejected_records else None,
        "processed_at": datetime.now(timezone.utc).isoformat(),
    }
    s3.put_object(
        Bucket=output_bucket, Key=report_key,
        Body=json.dumps(report, indent=2).encode("utf-8"),
        ContentType="application/json",
    )
    logger.info("Pipeline report: %s", json.dumps(report))
    return report


def lambda_handler(event, context):
    results = []
    for record in event.get("Records", []):
        if record.get("eventSource") != "aws:s3":
            continue
        bucket = record["s3"]["bucket"]["name"]
        key = urllib.parse.unquote_plus(record["s3"]["object"]["key"])
        # Only incoming files trigger processing; outputs cannot trigger a loop.
        if key.startswith("incoming/"):
            results.append(process_file(bucket, key))
        else:
            logger.info("Ignoring key outside incoming/: %s", key)
    return {"statusCode": 200, "body": json.dumps(results)}


if __name__ == "__main__":
    sample = [{"customer_id": "1", "customer_name": " Alice ", "email": "ALICE@EXAMPLE.COM"}]
    good, bad = transform_records(sample)
    print(good, bad, validate_transformed_data(good))
