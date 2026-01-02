"""Tests for exporter module (v0.2)."""

import csv
import io
import json
import pytest
from datetime import datetime
from pathlib import Path

from chronoclean.core.exporter import (
    Exporter,
    export_to_json,
    export_to_csv,
)
from chronoclean.core.models import ScanResult, FileRecord, DateSource, FileType


def create_test_record(
    source_path: str = "/photos/test.jpg",
    size_bytes: int = 1024,
    detected_date: datetime | None = None,
    date_source: DateSource = DateSource.UNKNOWN,
    filename_date: datetime | None = None,
    date_mismatch: bool = False,
    date_mismatch_days: int | None = None,
    file_hash: str | None = None,
    is_duplicate: bool = False,
    duplicate_of: Path | None = None,
) -> FileRecord:
    """Create a test FileRecord."""
    return FileRecord(
        source_path=Path(source_path),
        file_type=FileType.IMAGE,
        size_bytes=size_bytes,
        detected_date=detected_date,
        date_source=date_source,
        filename_date=filename_date,
        date_mismatch=date_mismatch,
        date_mismatch_days=date_mismatch_days,
        file_hash=file_hash,
        is_duplicate=is_duplicate,
        duplicate_of=duplicate_of,
    )


def create_test_scan_result(files: list[FileRecord] | None = None) -> ScanResult:
    """Create a test ScanResult."""
    if files is None:
        files = [
            create_test_record(
                source_path="/photos/IMG_001.jpg",
                size_bytes=2048,
                detected_date=datetime(2024, 1, 15, 10, 30, 0),
                date_source=DateSource.EXIF,
            ),
            create_test_record(
                source_path="/photos/IMG_002.jpg",
                size_bytes=4096,
                detected_date=datetime(2024, 2, 20, 14, 45, 0),
                date_source=DateSource.FILENAME,
            ),
        ]
    return ScanResult(
        source_root=Path("/photos"),
        files=files,
    )


class TestExporterInit:
    """Tests for Exporter initialization."""

    def test_default_init(self):
        """Test default initialization."""
        exporter = Exporter()
        assert exporter.include_statistics is True
        assert exporter.pretty_print is True

    def test_custom_init(self):
        """Test custom initialization."""
        exporter = Exporter(include_statistics=False, pretty_print=False)
        assert exporter.include_statistics is False
        assert exporter.pretty_print is False


class TestToJson:
    """Tests for to_json method."""

    def test_basic_json_export(self):
        """Test basic JSON export."""
        scan_result = create_test_scan_result()
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert "export_timestamp" in data
        # Use Path for cross-platform comparison
        assert Path(data["source_directory"]) == Path("/photos")
        assert data["file_count"] == 2
        assert len(data["files"]) == 2

    def test_json_includes_file_details(self):
        """Test JSON includes all file details."""
        record = create_test_record(
            source_path="/photos/test.jpg",
            size_bytes=1024,
            detected_date=datetime(2024, 1, 15, 10, 30, 0),
            date_source=DateSource.EXIF,
            filename_date=datetime(2024, 1, 14, 10, 0, 0),
            date_mismatch=True,
            date_mismatch_days=1,
            file_hash="abc123",
            is_duplicate=False,
        )
        scan_result = create_test_scan_result([record])
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        file_data = data["files"][0]
        
        # Use Path for cross-platform comparison
        assert Path(file_data["path"]) == Path("/photos/test.jpg")
        assert file_data["filename"] == "test.jpg"
        assert file_data["size_bytes"] == 1024
        assert file_data["extension"] == ".jpg"
        assert file_data["date_taken"] == "2024-01-15T10:30:00"
        assert file_data["date_source"] == "exif"
        assert file_data["year"] == "2024"
        assert file_data["month"] == "01"
        assert file_data["filename_date"] == "2024-01-14T10:00:00"
        assert file_data["date_mismatch"] is True
        assert file_data["date_mismatch_days"] == 1
        assert file_data["file_hash"] == "abc123"
        assert file_data["is_duplicate"] is False

    def test_json_includes_statistics(self):
        """Test JSON includes statistics when enabled."""
        scan_result = create_test_scan_result()
        exporter = Exporter(include_statistics=True)
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert "statistics" in data
        stats = data["statistics"]
        assert stats["total_files"] == 2
        assert stats["dated_files"] == 2
        assert stats["undated_files"] == 0

    def test_json_excludes_statistics_when_disabled(self):
        """Test JSON excludes statistics when disabled."""
        scan_result = create_test_scan_result()
        exporter = Exporter(include_statistics=False)
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert "statistics" not in data

    def test_json_pretty_print(self):
        """Test JSON pretty print option."""
        scan_result = create_test_scan_result()
        
        exporter_pretty = Exporter(pretty_print=True)
        pretty_json = exporter_pretty.to_json(scan_result)
        
        exporter_compact = Exporter(pretty_print=False)
        compact_json = exporter_compact.to_json(scan_result)
        
        # Pretty JSON should be longer (more whitespace)
        assert len(pretty_json) > len(compact_json)
        assert "\n" in pretty_json
        assert "\n" not in compact_json

    def test_json_writes_to_file(self, tmp_path):
        """Test JSON writes to file."""
        scan_result = create_test_scan_result()
        output_file = tmp_path / "output.json"
        
        exporter = Exporter()
        json_str = exporter.to_json(scan_result, output_file)
        
        assert output_file.exists()
        assert output_file.read_text() == json_str

    def test_json_creates_parent_directories(self, tmp_path):
        """Test JSON creates parent directories."""
        scan_result = create_test_scan_result()
        output_file = tmp_path / "subdir" / "nested" / "output.json"
        
        exporter = Exporter()
        exporter.to_json(scan_result, output_file)
        
        assert output_file.exists()

    def test_json_handles_none_values(self):
        """Test JSON handles None values properly."""
        record = create_test_record(
            source_path="/photos/undated.jpg",
            size_bytes=512,
            detected_date=None,
        )
        scan_result = create_test_scan_result([record])
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        file_data = data["files"][0]
        
        assert file_data["date_taken"] is None
        assert file_data["year"] is None
        assert file_data["month"] is None


class TestToCsv:
    """Tests for to_csv method."""

    def test_basic_csv_export(self):
        """Test basic CSV export."""
        scan_result = create_test_scan_result()
        exporter = Exporter()
        
        csv_str = exporter.to_csv(scan_result)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        
        # Header + 2 data rows
        assert len(rows) == 3
        assert rows[0][0] == "path"  # First header

    def test_csv_headers(self):
        """Test CSV has correct headers."""
        scan_result = create_test_scan_result()
        exporter = Exporter()
        
        csv_str = exporter.to_csv(scan_result)
        reader = csv.reader(io.StringIO(csv_str))
        headers = next(reader)
        
        # v0.3.4: Added folder tag fields and proposed destination fields
        expected_headers = [
            "path", "filename", "size_bytes", "extension",
            "date_taken", "date_source", "year", "month",
            "target_path", "filename_date", "date_mismatch",
            "date_mismatch_days", "video_metadata_date", "error_category",
            "source_folder_name", "folder_tags", "folder_tag_reasons",
            "folder_tag", "folder_tag_reason", "folder_tag_usable",
            "proposed_destination_folder", "proposed_filename", "proposed_target_path",
            "file_hash", "is_duplicate", "duplicate_of"
        ]
        assert headers == expected_headers

    def test_csv_includes_file_details(self):
        """Test CSV includes all file details."""
        record = create_test_record(
            source_path="/photos/test.jpg",
            size_bytes=1024,
            detected_date=datetime(2024, 1, 15, 10, 30, 0),
            date_source=DateSource.EXIF,
            file_hash="abc123",
        )
        scan_result = create_test_scan_result([record])
        exporter = Exporter()
        
        csv_str = exporter.to_csv(scan_result)
        reader = csv.DictReader(io.StringIO(csv_str))
        row = next(reader)
        
        # Use Path for cross-platform comparison
        assert Path(row["path"]) == Path("/photos/test.jpg")
        assert row["filename"] == "test.jpg"
        assert row["size_bytes"] == "1024"
        assert row["date_taken"] == "2024-01-15T10:30:00"
        assert row["date_source"] == "exif"
        assert row["year"] == "2024"
        assert row["month"] == "01"
        assert row["file_hash"] == "abc123"

    def test_csv_writes_to_file(self, tmp_path):
        """Test CSV writes to file."""
        scan_result = create_test_scan_result()
        output_file = tmp_path / "output.csv"
        
        exporter = Exporter()
        csv_str = exporter.to_csv(scan_result, output_file)
        
        assert output_file.exists()
        # Just check the file was created and contains data
        file_content = output_file.read_text()
        assert "path" in file_content  # Header present
        assert "IMG_001.jpg" in file_content  # Data present

    def test_csv_creates_parent_directories(self, tmp_path):
        """Test CSV creates parent directories."""
        scan_result = create_test_scan_result()
        output_file = tmp_path / "subdir" / "nested" / "output.csv"
        
        exporter = Exporter()
        exporter.to_csv(scan_result, output_file)
        
        assert output_file.exists()

    def test_csv_handles_empty_values(self):
        """Test CSV handles empty/None values."""
        record = create_test_record(
            source_path="/photos/undated.jpg",
            size_bytes=512,
            detected_date=None,
        )
        scan_result = create_test_scan_result([record])
        exporter = Exporter()
        
        csv_str = exporter.to_csv(scan_result)
        reader = csv.DictReader(io.StringIO(csv_str))
        row = next(reader)
        
        assert row["date_taken"] == ""
        assert row["year"] == ""


class TestToDict:
    """Tests for to_dict method."""

    def test_to_dict_returns_dict(self):
        """Test to_dict returns dictionary."""
        scan_result = create_test_scan_result()
        exporter = Exporter()
        
        result = exporter.to_dict(scan_result)
        
        assert isinstance(result, dict)
        assert "files" in result
        assert "file_count" in result


class TestStatistics:
    """Tests for statistics computation."""

    def test_total_size_calculation(self):
        """Test total size is calculated correctly."""
        records = [
            create_test_record(size_bytes=1024),
            create_test_record(source_path="/photos/b.jpg", size_bytes=2048),
            create_test_record(source_path="/photos/c.jpg", size_bytes=512),
        ]
        scan_result = create_test_scan_result(records)
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert data["statistics"]["total_size_bytes"] == 3584

    def test_dated_undated_counts(self):
        """Test dated/undated file counts."""
        records = [
            create_test_record(detected_date=datetime(2024, 1, 1)),
            create_test_record(source_path="/photos/b.jpg", detected_date=datetime(2024, 2, 1)),
            create_test_record(source_path="/photos/c.jpg", detected_date=None),
        ]
        scan_result = create_test_scan_result(records)
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert data["statistics"]["dated_files"] == 2
        assert data["statistics"]["undated_files"] == 1

    def test_date_source_counts(self):
        """Test date source counting."""
        records = [
            create_test_record(detected_date=datetime(2024, 1, 1), date_source=DateSource.EXIF),
            create_test_record(source_path="/photos/b.jpg", detected_date=datetime(2024, 2, 1), date_source=DateSource.EXIF),
            create_test_record(source_path="/photos/c.jpg", detected_date=datetime(2024, 3, 1), date_source=DateSource.FILENAME),
        ]
        scan_result = create_test_scan_result(records)
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert data["statistics"]["date_sources"]["exif"] == 2
        assert data["statistics"]["date_sources"]["filename"] == 1

    def test_year_counts(self):
        """Test year counting."""
        records = [
            create_test_record(detected_date=datetime(2023, 6, 1)),
            create_test_record(source_path="/photos/b.jpg", detected_date=datetime(2024, 1, 1)),
            create_test_record(source_path="/photos/c.jpg", detected_date=datetime(2024, 6, 1)),
        ]
        scan_result = create_test_scan_result(records)
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert data["statistics"]["files_by_year"]["2023"] == 1
        assert data["statistics"]["files_by_year"]["2024"] == 2

    def test_extension_counts(self):
        """Test extension counting."""
        records = [
            create_test_record(source_path="/photos/a.jpg"),
            create_test_record(source_path="/photos/b.jpg"),
            create_test_record(source_path="/photos/c.png"),
        ]
        scan_result = create_test_scan_result(records)
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert data["statistics"]["files_by_extension"][".jpg"] == 2
        assert data["statistics"]["files_by_extension"][".png"] == 1

    def test_mismatch_count(self):
        """Test date mismatch counting."""
        records = [
            create_test_record(date_mismatch=True),
            create_test_record(source_path="/photos/b.jpg", date_mismatch=True),
            create_test_record(source_path="/photos/c.jpg", date_mismatch=False),
        ]
        scan_result = create_test_scan_result(records)
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert data["statistics"]["date_mismatch_count"] == 2

    def test_duplicate_count(self):
        """Test duplicate counting."""
        records = [
            create_test_record(is_duplicate=True),
            create_test_record(source_path="/photos/b.jpg", is_duplicate=False),
            create_test_record(source_path="/photos/c.jpg", is_duplicate=False),
        ]
        scan_result = create_test_scan_result(records)
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert data["statistics"]["duplicate_count"] == 1

    def test_human_readable_size(self):
        """Test human readable size formatting."""
        exporter = Exporter()
        
        assert "B" in exporter._human_readable_size(100)
        assert "KB" in exporter._human_readable_size(1024)
        assert "MB" in exporter._human_readable_size(1024 * 1024)
        assert "GB" in exporter._human_readable_size(1024 * 1024 * 1024)


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_export_to_json(self):
        """Test export_to_json function."""
        scan_result = create_test_scan_result()
        
        json_str = export_to_json(scan_result)
        data = json.loads(json_str)
        
        assert "files" in data
        assert "statistics" in data

    def test_export_to_json_with_options(self):
        """Test export_to_json with custom options."""
        scan_result = create_test_scan_result()
        
        json_str = export_to_json(
            scan_result,
            include_statistics=False,
            pretty_print=False,
        )
        data = json.loads(json_str)
        
        assert "statistics" not in data
        assert "\n" not in json_str

    def test_export_to_json_to_file(self, tmp_path):
        """Test export_to_json writes to file."""
        scan_result = create_test_scan_result()
        output_file = tmp_path / "output.json"
        
        export_to_json(scan_result, output_file)
        
        assert output_file.exists()

    def test_export_to_csv(self):
        """Test export_to_csv function."""
        scan_result = create_test_scan_result()
        
        csv_str = export_to_csv(scan_result)
        
        assert "path" in csv_str
        assert "IMG_001.jpg" in csv_str  # Filename present

    def test_export_to_csv_to_file(self, tmp_path):
        """Test export_to_csv writes to file."""
        scan_result = create_test_scan_result()
        output_file = tmp_path / "output.csv"
        
        export_to_csv(scan_result, output_file)
        
        assert output_file.exists()


class TestEmptyResults:
    """Tests for empty scan results."""

    def test_empty_json(self):
        """Test JSON export of empty result."""
        scan_result = create_test_scan_result([])
        exporter = Exporter()
        
        json_str = exporter.to_json(scan_result)
        data = json.loads(json_str)
        
        assert data["file_count"] == 0
        assert data["files"] == []
        assert data["statistics"]["total_files"] == 0

    def test_empty_csv(self):
        """Test CSV export of empty result."""
        scan_result = create_test_scan_result([])
        exporter = Exporter()
        
        csv_str = exporter.to_csv(scan_result)
        reader = csv.reader(io.StringIO(csv_str))
        rows = list(reader)
        
        # Only header row
        assert len(rows) == 1
