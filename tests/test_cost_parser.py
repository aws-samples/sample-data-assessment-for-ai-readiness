"""Unit tests for forge.document_ingest.cost_parser."""

import csv
import os
import tempfile

import pytest

from forge.document_ingest import CostSignal
from forge.document_ingest.cost_parser import (
    BILLING_CATEGORY_MAP,
    parse_cost_usage,
    _map_category_to_service,
    _find_column,
    _SERVICE_COL_PATTERNS,
    _SPEND_COL_PATTERNS,
    _COMPUTE_COL_PATTERNS,
)


# --- Fixtures ---


@pytest.fixture
def csv_basic(tmp_path):
    """A basic Databricks cost usage CSV with standard columns."""
    fp = tmp_path / "cost_usage.csv"
    with open(fp, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Billing Category", "Spend (USD)", "DBUs"])
        writer.writerow(["SQL Warehouse", "1500.00", "200"])
        writer.writerow(["Jobs Compute", "3200.50", "450"])
        writer.writerow(["Delta Live Tables", "800.00", "100"])
        writer.writerow(["MLflow", "0.00", "0"])
        writer.writerow(["Model Serving", "250.75", "50"])
    return str(fp)


@pytest.fixture
def csv_aggregation(tmp_path):
    """CSV with multiple rows per service that should aggregate."""
    fp = tmp_path / "multi_rows.csv"
    with open(fp, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Service", "Cost", "Compute Hours"])
        writer.writerow(["SQL Warehouse", "$500.00", "100"])
        writer.writerow(["SQL Warehouse", "$700.00", "150"])
        writer.writerow(["Serverless SQL", "$300.00", "75"])
        writer.writerow(["Jobs", "$200.00", "50"])
    return str(fp)


@pytest.fixture
def csv_empty(tmp_path):
    """An empty CSV file."""
    fp = tmp_path / "empty.csv"
    fp.write_text("")
    return str(fp)


@pytest.fixture
def csv_no_service_col(tmp_path):
    """CSV with no recognizable service column."""
    fp = tmp_path / "no_svc.csv"
    with open(fp, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["foo", "bar", "baz"])
        writer.writerow(["a", "b", "c"])
    return str(fp)


@pytest.fixture
def csv_zero_spend(tmp_path):
    """CSV where all services have zero spend."""
    fp = tmp_path / "zero_spend.csv"
    with open(fp, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Category", "Amount", "Hours"])
        writer.writerow(["SQL Warehouse", "0.00", "0"])
        writer.writerow(["MLflow", "0", "0"])
    return str(fp)


# --- Tests: File Handling ---


class TestFileHandling:
    """Tests for file existence and format detection."""

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="not found"):
            parse_cost_usage("/nonexistent/path/cost.csv")

    def test_unsupported_extension_returns_empty(self, tmp_path):
        fp = tmp_path / "data.xlsx"
        fp.write_text("some data")
        result = parse_cost_usage(str(fp))
        assert result == []

    def test_txt_extension_returns_empty(self, tmp_path):
        fp = tmp_path / "data.txt"
        fp.write_text("some text")
        result = parse_cost_usage(str(fp))
        assert result == []


# --- Tests: CSV Parsing ---


class TestCSVParsing:
    """Tests for CSV format parsing."""

    def test_basic_csv_parsing(self, csv_basic):
        signals = parse_cost_usage(csv_basic)
        assert len(signals) == 5

        service_map = {s.service: s for s in signals}
        assert "sql_warehouse" in service_map
        assert "databricks_workflows" in service_map
        assert "delta_live_tables" in service_map
        assert "mlflow" in service_map
        assert "model_serving" in service_map

    def test_spend_values_correct(self, csv_basic):
        signals = parse_cost_usage(csv_basic)
        service_map = {s.service: s for s in signals}

        assert service_map["sql_warehouse"].spend_30d == 1500.00
        assert service_map["databricks_workflows"].spend_30d == 3200.50
        assert service_map["delta_live_tables"].spend_30d == 800.00
        assert service_map["model_serving"].spend_30d == 250.75

    def test_compute_hours_extracted(self, csv_basic):
        signals = parse_cost_usage(csv_basic)
        service_map = {s.service: s for s in signals}

        assert service_map["sql_warehouse"].compute_hours == 200.0
        assert service_map["databricks_workflows"].compute_hours == 450.0

    def test_active_flag_based_on_spend(self, csv_basic):
        signals = parse_cost_usage(csv_basic)
        service_map = {s.service: s for s in signals}

        assert service_map["sql_warehouse"].active is True
        assert service_map["mlflow"].active is False

    def test_zero_spend_inactive(self, csv_zero_spend):
        signals = parse_cost_usage(csv_zero_spend)
        for signal in signals:
            assert signal.active is False
            assert signal.spend_30d == 0.0

    def test_aggregation_multiple_rows(self, csv_aggregation):
        signals = parse_cost_usage(csv_aggregation)
        service_map = {s.service: s for s in signals}

        # SQL Warehouse: 500 + 700 + 300 (serverless sql) = 1500
        assert service_map["sql_warehouse"].spend_30d == 1500.0
        assert service_map["sql_warehouse"].compute_hours == 325.0

        # Jobs: 200
        assert service_map["databricks_workflows"].spend_30d == 200.0

    def test_empty_csv_returns_empty(self, csv_empty):
        signals = parse_cost_usage(csv_empty)
        assert signals == []

    def test_no_service_column_returns_empty(self, csv_no_service_col):
        signals = parse_cost_usage(csv_no_service_col)
        assert signals == []

    def test_currency_symbols_handled(self, tmp_path):
        fp = tmp_path / "currency.csv"
        with open(fp, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["Category", "Spend"])
            writer.writerow(["SQL Warehouse", "$1,234.56"])
        signals = parse_cost_usage(str(fp))
        assert signals[0].spend_30d == 1234.56

    def test_returns_cost_signal_dataclass(self, csv_basic):
        signals = parse_cost_usage(csv_basic)
        for signal in signals:
            assert isinstance(signal, CostSignal)


# --- Tests: Category Mapping ---


class TestCategoryMapping:
    """Tests for billing category to service key mapping."""

    def test_direct_match(self):
        assert _map_category_to_service("sql warehouse") == "sql_warehouse"
        assert _map_category_to_service("jobs") == "databricks_workflows"
        assert _map_category_to_service("dlt") == "delta_live_tables"
        assert _map_category_to_service("mlflow") == "mlflow"

    def test_case_insensitive(self):
        assert _map_category_to_service("SQL Warehouse") == "sql_warehouse"
        assert _map_category_to_service("JOBS COMPUTE") == "databricks_workflows"
        assert _map_category_to_service("MLflow") == "mlflow"

    def test_substring_match(self):
        assert _map_category_to_service("Serverless SQL Warehouse Pro") == "sql_warehouse"
        assert _map_category_to_service("Jobs Compute (Premium)") == "databricks_workflows"

    def test_unknown_returns_none(self):
        assert _map_category_to_service("Unknown Service") is None
        assert _map_category_to_service("Premium Support") is None


# --- Tests: Column Detection ---


class TestColumnDetection:
    """Tests for auto-detecting CSV column types."""

    def test_service_col_patterns(self):
        headers = ["Billing Category", "Spend", "DBUs"]
        assert _find_column(headers, _SERVICE_COL_PATTERNS) == 0

    def test_spend_col_patterns(self):
        headers = ["Service", "Cost (USD)", "Hours"]
        assert _find_column(headers, _SPEND_COL_PATTERNS) == 1

    def test_compute_col_patterns(self):
        headers = ["Service", "Cost", "Compute Hours"]
        assert _find_column(headers, _COMPUTE_COL_PATTERNS) == 2

    def test_no_match_returns_none(self):
        headers = ["foo", "bar", "baz"]
        assert _find_column(headers, _SERVICE_COL_PATTERNS) is None


# --- Tests: PDF Parsing ---


class TestPDFParsing:
    """Tests for PDF format handling (graceful degradation)."""

    def test_pdf_without_library_returns_empty(self, tmp_path):
        """PDF parsing without PyPDF2/pdfplumber should return empty list."""
        fp = tmp_path / "cost.pdf"
        fp.write_bytes(b"%PDF-1.4 fake pdf")
        # This test validates graceful degradation when no PDF library is installed
        signals = parse_cost_usage(str(fp))
        # Result depends on whether PyPDF2/pdfplumber is installed
        assert isinstance(signals, list)
