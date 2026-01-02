"""Unit tests for chronoclean.core.models."""

from datetime import datetime
from pathlib import Path

import pytest

from chronoclean.core.models import (
    DateSource,
    FileRecord,
    FileType,
    MoveOperation,
    OperationPlan,
    ScanResult,
)


class TestDateSource:
    """Tests for DateSource enum."""

    def test_enum_values(self):
        assert DateSource.EXIF.value == "exif"
        assert DateSource.FILESYSTEM_CREATED.value == "filesystem_created"
        assert DateSource.FILESYSTEM_MODIFIED.value == "filesystem_modified"
        assert DateSource.FOLDER_NAME.value == "folder_name"
        assert DateSource.UNKNOWN.value == "unknown"


class TestFileType:
    """Tests for FileType enum."""

    def test_enum_values(self):
        assert FileType.IMAGE.value == "image"
        assert FileType.VIDEO.value == "video"
        assert FileType.RAW.value == "raw"
        assert FileType.UNKNOWN.value == "unknown"


class TestFileRecord:
    """Tests for FileRecord dataclass."""

    def test_basic_creation(self, temp_dir: Path):
        file_path = temp_dir / "test.jpg"
        file_path.write_bytes(b"test")

        record = FileRecord(
            source_path=file_path,
            file_type=FileType.IMAGE,
            size_bytes=100,
        )

        assert record.source_path == file_path
        assert record.file_type == FileType.IMAGE
        assert record.size_bytes == 100
        assert record.detected_date is None
        assert record.date_source == DateSource.UNKNOWN

    def test_with_date(self, temp_dir: Path):
        file_path = temp_dir / "test.jpg"
        file_path.write_bytes(b"test")
        date = datetime(2024, 3, 15, 14, 30, 0)

        record = FileRecord(
            source_path=file_path,
            file_type=FileType.IMAGE,
            size_bytes=100,
            detected_date=date,
            date_source=DateSource.EXIF,
            has_exif=True,
        )

        assert record.detected_date == date
        assert record.date_source == DateSource.EXIF
        assert record.has_exif is True

    def test_extension_property(self, temp_dir: Path):
        jpg_path = temp_dir / "test.JPG"
        jpg_path.write_bytes(b"test")

        record = FileRecord(
            source_path=jpg_path,
            file_type=FileType.IMAGE,
            size_bytes=100,
        )

        assert record.extension == ".jpg"  # lowercase

    def test_original_filename_property(self, temp_dir: Path):
        file_path = temp_dir / "my_photo.jpg"
        file_path.write_bytes(b"test")

        record = FileRecord(
            source_path=file_path,
            file_type=FileType.IMAGE,
            size_bytes=100,
        )

        assert record.original_filename == "my_photo.jpg"

    def test_destination_path_property_none(self, temp_dir: Path):
        file_path = temp_dir / "test.jpg"
        file_path.write_bytes(b"test")

        record = FileRecord(
            source_path=file_path,
            file_type=FileType.IMAGE,
            size_bytes=100,
        )

        assert record.destination_path is None

    def test_destination_path_property_set(self, temp_dir: Path):
        file_path = temp_dir / "test.jpg"
        file_path.write_bytes(b"test")

        record = FileRecord(
            source_path=file_path,
            file_type=FileType.IMAGE,
            size_bytes=100,
            destination_folder=Path("/dest/2024/03"),
            destination_filename="20240315_143000.jpg",
        )

        assert record.destination_path == Path("/dest/2024/03/20240315_143000.jpg")

    def test_folder_tag_fields(self, temp_dir: Path):
        file_path = temp_dir / "test.jpg"
        file_path.write_bytes(b"test")

        # Test with array-based tags (v0.3.4+)
        record = FileRecord(
            source_path=file_path,
            file_type=FileType.IMAGE,
            size_bytes=100,
            source_folder_name="Paris 2024",
            folder_tags=["Paris_2024"],
            folder_tag_reasons=["parent_folder"],
        )

        assert record.source_folder_name == "Paris 2024"
        assert record.folder_tags == ["Paris_2024"]
        assert record.folder_tag_reasons == ["parent_folder"]
        # Backward-compatible properties
        assert record.folder_tag == "Paris_2024"
        assert record.folder_tag_reason == "parent_folder"
        assert record.folder_tag_usable is True

    def test_folder_tag_empty(self, temp_dir: Path):
        """Test folder_tag_usable returns False when no tags."""
        file_path = temp_dir / "test.jpg"
        file_path.write_bytes(b"test")

        record = FileRecord(
            source_path=file_path,
            file_type=FileType.IMAGE,
            size_bytes=100,
        )

        assert record.folder_tags == []
        assert record.folder_tag is None
        assert record.folder_tag_usable is False


class TestScanResult:
    """Tests for ScanResult dataclass."""

    def test_basic_creation(self, temp_dir: Path):
        result = ScanResult(source_root=temp_dir)

        assert result.source_root == temp_dir
        assert result.total_files == 0
        assert result.processed_files == 0
        assert result.skipped_files == 0
        assert result.error_files == 0
        assert result.files == []

    def test_add_file(self, temp_dir: Path):
        file_path = temp_dir / "test.jpg"
        file_path.write_bytes(b"test")

        result = ScanResult(source_root=temp_dir)
        record = FileRecord(
            source_path=file_path,
            file_type=FileType.IMAGE,
            size_bytes=100,
        )

        result.add_file(record)

        assert len(result.files) == 1
        assert result.processed_files == 1

    def test_add_error(self, temp_dir: Path):
        result = ScanResult(source_root=temp_dir)
        error_path = temp_dir / "bad.jpg"

        result.add_error(error_path, "Cannot read file")

        assert len(result.errors) == 1
        assert result.error_files == 1
        assert result.errors[0] == (error_path, "Cannot read file")

    def test_add_skipped(self, temp_dir: Path):
        result = ScanResult(source_root=temp_dir)

        result.add_skipped()
        result.add_skipped()

        assert result.skipped_files == 2

    def test_success_rate_empty(self, temp_dir: Path):
        result = ScanResult(source_root=temp_dir)
        assert result.success_rate == 0.0

    def test_success_rate_calculated(self, temp_dir: Path):
        result = ScanResult(source_root=temp_dir)
        result.total_files = 10
        result.processed_files = 8

        assert result.success_rate == 80.0

    def test_folder_tags_detected(self, temp_dir: Path):
        result = ScanResult(source_root=temp_dir)
        result.folder_tags_detected = ["Paris", "London", "Tokyo"]

        assert len(result.folder_tags_detected) == 3
        assert "Paris" in result.folder_tags_detected


class TestMoveOperation:
    """Tests for MoveOperation dataclass."""

    def test_basic_creation(self):
        source = Path("/source/photo.jpg")
        dest = Path("/dest/2024/03")

        op = MoveOperation(source=source, destination=dest)

        assert op.source == source
        assert op.destination == dest
        assert op.new_filename is None

    def test_with_new_filename(self):
        source = Path("/source/IMG_001.jpg")
        dest = Path("/dest/2024/03")

        op = MoveOperation(
            source=source,
            destination=dest,
            new_filename="20240315_143000.jpg",
        )

        assert op.new_filename == "20240315_143000.jpg"

    def test_destination_path_without_rename(self):
        source = Path("/source/photo.jpg")
        dest = Path("/dest/2024/03")

        op = MoveOperation(source=source, destination=dest)

        assert op.destination_path == Path("/dest/2024/03/photo.jpg")

    def test_destination_path_with_rename(self):
        source = Path("/source/IMG_001.jpg")
        dest = Path("/dest/2024/03")

        op = MoveOperation(
            source=source,
            destination=dest,
            new_filename="20240315_143000.jpg",
        )

        assert op.destination_path == Path("/dest/2024/03/20240315_143000.jpg")


class TestOperationPlan:
    """Tests for OperationPlan dataclass."""

    def test_basic_creation(self):
        plan = OperationPlan()

        assert plan.moves == []
        assert plan.skipped == []
        assert plan.conflicts == []
        assert plan.total_operations == 0
        assert plan.total_skipped == 0

    def test_add_move(self):
        plan = OperationPlan()
        source = Path("/source/photo.jpg")
        dest = Path("/dest/2024/03")

        plan.add_move(source, dest)

        assert len(plan.moves) == 1
        assert plan.total_operations == 1
        assert plan.moves[0].source == source

    def test_add_move_with_rename(self):
        plan = OperationPlan()
        source = Path("/source/IMG_001.jpg")
        dest = Path("/dest/2024/03")

        plan.add_move(source, dest, new_filename="renamed.jpg", reason="date-based")

        assert plan.moves[0].new_filename == "renamed.jpg"
        assert plan.moves[0].reason == "date-based"

    def test_add_skip(self):
        plan = OperationPlan()
        path = Path("/source/unknown.jpg")

        plan.add_skip(path, "No date found")

        assert len(plan.skipped) == 1
        assert plan.total_skipped == 1
        assert plan.skipped[0] == (path, "No date found")

    def test_add_conflict(self):
        plan = OperationPlan()
        src = Path("/source/photo1.jpg")
        dst = Path("/dest/2024/03/photo.jpg")

        plan.add_conflict(src, dst, "File already exists")

        assert len(plan.conflicts) == 1
        assert plan.conflicts[0] == (src, dst, "File already exists")

    def test_multiple_operations(self):
        plan = OperationPlan()

        plan.add_move(Path("/s/a.jpg"), Path("/d/2024"))
        plan.add_move(Path("/s/b.jpg"), Path("/d/2024"))
        plan.add_skip(Path("/s/c.jpg"), "No date")
        plan.add_conflict(Path("/s/d.jpg"), Path("/d/2024/d.jpg"), "Exists")

        assert plan.total_operations == 2
        assert plan.total_skipped == 1
        assert len(plan.conflicts) == 1
