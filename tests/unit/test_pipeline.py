from handler import read_csv, transform_records, validate_transformed_data


def test_read_csv():
    assert read_csv("customer_id,customer_name,email\n1,Alice,alice@example.com\n")[0]["customer_id"] == "1"


def test_missing_header():
    try:
        read_csv("customer_id,customer_name\n1,Alice\n")
        assert False
    except ValueError as error:
        assert "email" in str(error)


def test_trim_and_lowercase_email():
    rows = [{"customer_id": " 1 ", "customer_name": " Alice ", "email": " ALICE@EXAMPLE.COM "}]
    good, bad = transform_records(rows)
    assert good[0]["customer_id"] == "1"
    assert good[0]["customer_name"] == "Alice"
    assert good[0]["email"] == "alice@example.com"
    assert bad == []


def test_duplicate_id_rejected():
    rows = [
        {"customer_id": "1", "customer_name": "Alice", "email": "alice@example.com"},
        {"customer_id": "1", "customer_name": "Other", "email": "other@example.com"},
    ]
    good, bad = transform_records(rows)
    assert len(good) == 1
    assert bad[0]["reason"] == "duplicate customer_id"


def test_missing_id_rejected():
    good, bad = transform_records([{"customer_id": "", "customer_name": "A", "email": "a@b.com"}])
    assert good == []
    assert bad[0]["reason"] == "customer_id is missing"


def test_invalid_email_rejected():
    good, bad = transform_records([{"customer_id": "1", "customer_name": "A", "email": "bad"}])
    assert good == []
    assert bad[0]["reason"] == "email is missing or invalid"


def test_post_transform_validation_passes():
    rows = [{"customer_id": "1", "customer_name": "Alice", "email": "alice@example.com"}]
    result = validate_transformed_data(rows)
    assert result["passed"] is True
    assert result["row_count"] == 1
    assert result["unique_customer_ids"] == 1


def test_post_transform_validation_detects_duplicate_ids():
    rows = [
        {"customer_id": "1", "customer_name": "Alice", "email": "alice@example.com"},
        {"customer_id": "1", "customer_name": "Bob", "email": "bob@example.com"},
    ]
    result = validate_transformed_data(rows)
    assert result["passed"] is False
    assert "customer_id contains duplicates" in result["errors"]


def test_post_transform_validation_detects_bad_email():
    result = validate_transformed_data([{"customer_id": "1", "customer_name": "A", "email": "bad"}])
    assert result["passed"] is False
    assert any("email format" in item for item in result["errors"])
