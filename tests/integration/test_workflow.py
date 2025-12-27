"""Integration tests for ChronoClean workflow."""

from datetime import datetime
from pathlib import Path

import pytest

from chronoclean.core.date_inference import DateInferenceEngine
from chronoclean.core.exif_reader import ExifReader
from chronoclean.core.file_operations import BatchOperations, FileOperations
from chronoclean.core.folder_tagger import FolderTagger
from chronoclean.core.models import DateSource, FileType, ScanResult
from chronoclean.core.renamer import ConflictResolver, Renamer
from chronoclean.core.scanner import Scanner
from chronoclean.core.sorter import Sorter, SortingPlan


class TestScanToSortWorkflow:
    """Test complete scan-to-sort workflow."""

    def test_scan_and_sort_single_file(self, temp_dir: Path):
        """Test scanning a single file and computing its destination."""
        # Setup: create source file
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        photo = source_dir / "IMG_001.jpg"
        photo.write_bytes(b"fake image content")

        dest_dir = temp_dir / "sorted"

        # Scan
        scanner = Scanner()
        result = scanner.scan(source_dir)

        assert result.processed_files == 1
        record = result.files[0]
        assert record.source_path == photo
        assert record.detected_date is not None

        # Sort (compute destination)
        sorter = Sorter(destination_root=dest_dir, folder_structure="YYYY/MM")
        destination = sorter.compute_full_destination(
            record.source_path,
            record.detected_date,
        )

        # Verify destination path structure
        assert dest_dir in destination.parents or destination.parent == dest_dir
        assert destination.name == "IMG_001.jpg"

    def test_scan_sort_rename_workflow(self, temp_dir: Path):
        """Test scan → sort → rename workflow."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        photo = source_dir / "IMG_001.jpg"
        photo.write_bytes(b"test")

        dest_dir = temp_dir / "sorted"

        # Scan
        scanner = Scanner()
        result = scanner.scan(source_dir)
        record = result.files[0]

        # Rename
        renamer = Renamer(pattern="{date}_{time}")
        new_name = renamer.generate_filename(
            record.source_path,
            record.detected_date,
        )

        # Sort with new name
        sorter = Sorter(destination_root=dest_dir)
        destination = sorter.compute_full_destination(
            record.source_path,
            record.detected_date,
            new_name,
        )

        # Verify renamed file in destination
        assert destination.stem.startswith("20")  # Year prefix
        assert destination.suffix == ".jpg"

    def test_full_workflow_with_move(self, temp_dir: Path):
        """Test complete workflow including actual file move."""
        # Setup
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        dest_dir = temp_dir / "sorted"

        photo = source_dir / "vacation.jpg"
        photo.write_bytes(b"photo data")

        # Scan
        scanner = Scanner()
        result = scanner.scan(source_dir)
        record = result.files[0]

        # Compute destination
        sorter = Sorter(destination_root=dest_dir, folder_structure="YYYY/MM")
        destination = sorter.compute_full_destination(
            record.source_path,
            record.detected_date,
        )

        # Execute move
        file_ops = FileOperations(dry_run=False, create_dirs=True)
        success, message = file_ops.move_file(record.source_path, destination)

        assert success is True
        assert not photo.exists()
        assert destination.exists()
        assert destination.read_bytes() == b"photo data"


class TestMultiFileWorkflow:
    """Test workflows with multiple files."""

    def test_scan_multiple_files_same_date(self, temp_dir: Path):
        """Test handling multiple files from same date."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()

        # Create multiple files
        for i in range(3):
            (source_dir / f"photo_{i}.jpg").write_bytes(f"content {i}".encode())

        # Scan
        scanner = Scanner()
        result = scanner.scan(source_dir)

        assert result.processed_files == 3

        # All should have similar dates (filesystem dates)
        dates = [r.detected_date.date() for r in result.files]
        assert len(set(dates)) == 1  # All same date

    def test_conflict_resolution_workflow(self, temp_dir: Path):
        """Test renaming with conflict resolution."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()

        # Create files that would have same name after rename
        photo1 = source_dir / "IMG_001.jpg"
        photo2 = source_dir / "IMG_002.jpg"
        photo1.write_bytes(b"photo1")
        photo2.write_bytes(b"photo2")

        # Use same date for both
        date = datetime(2024, 3, 15, 14, 30, 45)

        resolver = ConflictResolver()
        name1 = resolver.resolve(photo1, date)
        name2 = resolver.resolve(photo2, date)

        # Names should be unique
        assert name1 != name2
        assert name1 == "20240315_143045.jpg"
        assert name2 == "20240315_143045_001.jpg"

    def test_batch_move_workflow(self, temp_dir: Path):
        """Test batch moving multiple files."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        dest_dir = temp_dir / "sorted"

        # Create files
        files = []
        for i in range(5):
            path = source_dir / f"photo_{i}.jpg"
            path.write_bytes(f"content {i}".encode())
            files.append(path)

        # Scan
        scanner = Scanner()
        result = scanner.scan(source_dir)

        # Build operations
        sorter = Sorter(destination_root=dest_dir)
        operations = []
        for record in result.files:
            dest = sorter.compute_full_destination(
                record.source_path,
                record.detected_date,
            )
            operations.append((record.source_path, dest))

        # Execute batch
        file_ops = FileOperations(dry_run=False, create_dirs=True)
        batch = BatchOperations(file_ops=file_ops, dry_run=False)
        success, failure = batch.execute_moves(operations)

        assert success == 5
        assert failure == 0
        assert all(not f.exists() for f in files)


class TestFolderTagWorkflow:
    """Test folder tagging integration."""

    def test_scan_extracts_folder_tags(self, temp_dir: Path):
        """Test that scanning extracts folder tags."""
        source_dir = temp_dir / "source"
        event_dir = source_dir / "Paris Vacation"
        event_dir.mkdir(parents=True)

        photo = event_dir / "photo.jpg"
        photo.write_bytes(b"test")

        scanner = Scanner()
        result = scanner.scan(source_dir)

        assert len(result.files) == 1
        record = result.files[0]
        assert record.folder_tag == "Paris_Vacation"

    def test_rename_with_folder_tag(self, temp_dir: Path):
        """Test renaming includes folder tag."""
        source_dir = temp_dir / "Wedding Photos"
        source_dir.mkdir()
        photo = source_dir / "IMG_001.jpg"
        photo.write_bytes(b"test")

        scanner = Scanner()
        result = scanner.scan(source_dir)
        record = result.files[0]

        renamer = Renamer()
        if record.folder_tag and record.folder_tag_usable:
            new_name = renamer.generate_filename(
                photo,
                record.detected_date,
                tag=record.folder_tag,
            )
            assert "Wedding" in new_name

    def test_multiple_folders_different_tags(self, temp_dir: Path):
        """Test scanning multiple folders with different tags."""
        source_dir = temp_dir / "source"

        # Create two event folders
        folder1 = source_dir / "Birthday Party"
        folder2 = source_dir / "Beach Trip"
        folder1.mkdir(parents=True)
        folder2.mkdir(parents=True)

        (folder1 / "photo1.jpg").write_bytes(b"test1")
        (folder2 / "photo2.jpg").write_bytes(b"test2")

        scanner = Scanner()
        result = scanner.scan(source_dir)

        tags = {r.folder_tag for r in result.files if r.folder_tag}
        assert "Birthday_Party" in tags
        assert "Beach_Trip" in tags


class TestDateInferenceIntegration:
    """Test date inference in workflow context."""

    def test_filesystem_date_fallback(self, temp_dir: Path):
        """Test that filesystem dates are used when no EXIF."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()

        # Create a non-image file (no EXIF possible)
        photo = source_dir / "photo.jpg"
        photo.write_bytes(b"not real jpeg")

        scanner = Scanner()
        result = scanner.scan(source_dir)
        record = result.files[0]

        # Should have a date from filesystem
        assert record.detected_date is not None
        assert record.date_source in (
            DateSource.FILESYSTEM_CREATED,
            DateSource.FILESYSTEM_MODIFIED,
        )

    def test_folder_name_date_extraction(self, temp_dir: Path):
        """Test date extraction from folder names."""
        source_dir = temp_dir / "2024-03-15 Event"
        source_dir.mkdir()
        photo = source_dir / "photo.jpg"
        photo.write_bytes(b"test")

        engine = DateInferenceEngine()
        date, source = engine.infer_date(photo)

        # Should extract date from folder name
        assert date is not None
        if source == DateSource.FOLDER_NAME:
            assert date.year == 2024
            assert date.month == 3
            assert date.day == 15


class TestSortingPlanIntegration:
    """Test SortingPlan with real scan results."""

    def test_build_plan_from_scan(self, temp_dir: Path):
        """Test building a sorting plan from scan results."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        dest_dir = temp_dir / "sorted"

        # Create files
        for i in range(3):
            (source_dir / f"photo_{i}.jpg").write_bytes(b"test")

        # Scan
        scanner = Scanner()
        result = scanner.scan(source_dir)

        # Build plan
        plan = SortingPlan(destination_root=dest_dir)
        for record in result.files:
            plan.add_file(record.source_path, record.detected_date)

        assert len(plan.destinations) == 3
        assert not plan.has_conflicts

    def test_plan_detects_conflicts(self, temp_dir: Path):
        """Test that plan detects destination conflicts."""
        dest_dir = temp_dir / "sorted"
        date = datetime(2024, 3, 15)

        plan = SortingPlan(destination_root=dest_dir)

        # Add files with same destination name
        plan.add_file(Path("/source/a.jpg"), date, "same.jpg")
        plan.add_file(Path("/source/b.jpg"), date, "same.jpg")

        assert plan.has_conflicts
        assert len(plan.conflicts) == 1


class TestDryRunWorkflow:
    """Test dry-run mode throughout workflow."""

    def test_dry_run_no_changes(self, temp_dir: Path):
        """Test that dry-run mode makes no changes."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        dest_dir = temp_dir / "sorted"

        photo = source_dir / "photo.jpg"
        photo.write_bytes(b"original content")

        # Scan
        scanner = Scanner()
        result = scanner.scan(source_dir)
        record = result.files[0]

        # Compute destination
        sorter = Sorter(destination_root=dest_dir)
        destination = sorter.compute_full_destination(
            record.source_path,
            record.detected_date,
        )

        # Dry run move
        file_ops = FileOperations(dry_run=True)
        success, message = file_ops.move_file(record.source_path, destination)

        assert success is True
        assert "Dry run" in message
        # Verify no changes
        assert photo.exists()
        assert photo.read_bytes() == b"original content"
        assert not dest_dir.exists()


class TestErrorHandling:
    """Test error handling in workflows."""

    def test_scan_with_unreadable_files(self, temp_dir: Path):
        """Test scan handles errors gracefully."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()

        # Create valid file
        (source_dir / "good.jpg").write_bytes(b"test")

        scanner = Scanner()
        result = scanner.scan(source_dir)

        # Should process what it can
        assert result.processed_files >= 1

    def test_batch_partial_failure_rollback(self, temp_dir: Path):
        """Test rollback after partial batch failure."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        dest_dir = temp_dir / "sorted"

        # Create one file
        photo = source_dir / "photo.jpg"
        photo.write_bytes(b"content")

        # First operation will succeed, second will fail (nonexistent)
        operations = [
            (photo, dest_dir / "2024" / "03" / "photo.jpg"),
            (source_dir / "nonexistent.jpg", dest_dir / "fake.jpg"),
        ]

        file_ops = FileOperations(dry_run=False, create_dirs=True)
        batch = BatchOperations(file_ops=file_ops, dry_run=False)
        success, failure = batch.execute_moves(operations)

        assert success == 1
        assert failure == 1

        # Rollback
        rolled = batch.rollback()
        assert rolled == 1

        # Original file should be back
        assert photo.exists()


class TestFileTypeHandling:
    """Test handling of different file types."""

    def test_mixed_file_types(self, temp_dir: Path):
        """Test scanning mixed image and video files."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()

        (source_dir / "photo.jpg").write_bytes(b"image")
        (source_dir / "video.mp4").write_bytes(b"video")
        (source_dir / "raw.cr2").write_bytes(b"raw")

        scanner = Scanner(include_videos=True, include_raw=True)
        result = scanner.scan(source_dir)

        types = {r.file_type for r in result.files}
        assert FileType.IMAGE in types
        assert FileType.VIDEO in types
        assert FileType.RAW in types

    def test_exclude_videos(self, temp_dir: Path):
        """Test excluding video files from scan."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()

        (source_dir / "photo.jpg").write_bytes(b"image")
        (source_dir / "video.mp4").write_bytes(b"video")

        scanner = Scanner(include_videos=False)
        result = scanner.scan(source_dir)

        types = {r.file_type for r in result.files}
        assert FileType.IMAGE in types
        assert FileType.VIDEO not in types


class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    def test_organize_photo_library(self, temp_dir: Path):
        """Simulate organizing a small photo library."""
        # Setup: messy source structure
        source = temp_dir / "messy_photos"
        (source / "DCIM" / "100APPLE").mkdir(parents=True)
        (source / "Downloads").mkdir()
        (source / "Paris 2024").mkdir()

        (source / "DCIM" / "100APPLE" / "IMG_001.jpg").write_bytes(b"photo1")
        (source / "Downloads" / "screenshot.jpg").write_bytes(b"photo2")
        (source / "Paris 2024" / "eiffel.jpg").write_bytes(b"photo3")

        dest = temp_dir / "organized"

        # Scan
        scanner = Scanner()
        result = scanner.scan(source)

        assert result.processed_files == 3

        # Build sorting plan
        sorter = Sorter(destination_root=dest, folder_structure="YYYY/MM")
        renamer = Renamer()
        resolver = ConflictResolver(renamer=renamer)

        operations = []
        for record in result.files:
            new_name = resolver.resolve(
                record.source_path,
                record.detected_date,
                tag=record.folder_tag if record.folder_tag_usable else None,
            )
            destination = sorter.compute_full_destination(
                record.source_path,
                record.detected_date,
                new_name,
            )
            operations.append((record.source_path, destination))

        # Execute
        file_ops = FileOperations(dry_run=False, create_dirs=True)
        batch = BatchOperations(file_ops=file_ops, dry_run=False)
        success, failure = batch.execute_moves(operations)

        assert success == 3
        assert failure == 0

        # Verify destination structure
        assert dest.exists()
        organized_files = list(dest.rglob("*.jpg"))
        assert len(organized_files) == 3

    def test_incremental_organization(self, temp_dir: Path):
        """Test adding new photos to already organized library."""
        source = temp_dir / "new_photos"
        source.mkdir()
        dest = temp_dir / "library"

        # Pre-existing file in library
        existing_dir = dest / "2024" / "03"
        existing_dir.mkdir(parents=True)
        (existing_dir / "existing.jpg").write_bytes(b"existing")

        # New file to add
        (source / "new.jpg").write_bytes(b"new photo")

        # Scan only new photos
        scanner = Scanner()
        result = scanner.scan(source)

        # Sort into existing structure
        sorter = Sorter(destination_root=dest)
        file_ops = FileOperations(dry_run=False, create_dirs=True)

        for record in result.files:
            destination = sorter.compute_full_destination(
                record.source_path,
                record.detected_date,
            )
            # Ensure unique if conflict
            destination = file_ops.ensure_unique_path(destination)
            file_ops.move_file(record.source_path, destination)

        # Library should have both files
        all_photos = list(dest.rglob("*.jpg"))
        assert len(all_photos) == 2
