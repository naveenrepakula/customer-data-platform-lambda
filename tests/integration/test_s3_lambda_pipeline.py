import io
import json

import handler
from handler import lambda_handler


class FakeS3:
    def __init__(self):
        self.objects = {}

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[(Bucket, Key)])}

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[(Bucket, Key)] = Body if isinstance(Body, bytes) else Body.encode()


def test_s3_event_runs_full_lambda_pipeline(monkeypatch):
    fake_s3 = FakeS3()
    monkeypatch.setattr(handler, "s3", fake_s3)
    monkeypatch.setenv("OUTPUT_BUCKET", "cdp-output-test")

    fake_s3.objects[("cdp-raw-test", "incoming/customers.csv")] = (
        b"customer_id,customer_name,email,city\n"
        b"1, Alice ,ALICE@EXAMPLE.COM,Bengaluru\n"
        b"1,Duplicate,dup@example.com,Bengaluru\n"
        b",No ID,noid@example.com,Chennai\n"
        b"2,Bob,bob@example.com,Hyderabad\n"
    )

    event = {"Records": [{"eventSource": "aws:s3", "s3": {
        "bucket": {"name": "cdp-raw-test"},
        "object": {"key": "incoming%2Fcustomers.csv"},
    }}]}
    response = lambda_handler(event, None)
    report = json.loads(response["body"])[0]

    assert report["input_count"] == 4
    assert report["transformed_count"] == 2
    assert report["rejected_count"] == 2
    assert report["post_transformation_validation"]["passed"] is True

    csv_output = fake_s3.objects[
        ("cdp-output-test", "processed/customers/customers.processed.csv")
    ].decode()
    assert "alice@example.com" in csv_output
    assert "Duplicate" not in csv_output

    rejected = json.loads(fake_s3.objects[
        ("cdp-output-test", "failed/records/customers.rejected.json")
    ])
    assert len(rejected) == 2

    saved_report = json.loads(fake_s3.objects[
        ("cdp-output-test", "failed/reports/customers.report.json")
    ])
    assert saved_report["post_transformation_validation"]["passed"] is True
