"""Unit tests for chronoclean.core.file_operations."""

from pathlib import Path
from unittest.mock import patch

import pytest

from chronoclean.core.file_operations import (
    BatchOperations,
    FileOperationError,
    FileOperations,
)


class TestFileOperationsInit:
    """Tests for FileOperations initialization."""

    def test_default_init(self):
        ops = FileOperations()

        assert ops.dry_run is True
        assert ops.create_dirs is True
        assert ops.preserve_metadata is True

    def test_custom_init(self):
        ops = FileOperations(
            dry_run=False,
            create_dirs=False,
            preserve_metadata=False,
        )

        assert ops.dry_run is False
        assert ops.create_dirs is False
        assert ops.preserve_metadata is False


class TestMoveFile:
    """Tests for move_file method."""

    def test_dry_run_does_not_move(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test content")
        dest = temp_dir / "dest" / "moved.jpg"

        ops = FileOperations(dry_run=True)
        success, message = ops.move_file(source, dest)

        assert success is True
        assert "Dry run" in message
        assert source.exists()  # Original still exists
        assert not dest.exists()  # Destination not created

    def test_actual_move(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test content")
        dest = temp_dir / "dest" / "moved.jpg"

        ops = FileOperations(dry_run=False, create_dirs=True)
        success, message = ops.move_file(source, dest)

        assert success is True
        assert "successfully" in message
        assert not source.exists()  # Original removed
        assert dest.exists()  # File at destination
        assert dest.read_bytes() == b"test content"

    def test_move_creates_directories(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test")
        dest = temp_dir / "a" / "b" / "c" / "file.jpg"

        ops = FileOperations(dry_run=False, create_dirs=True)
        success, _ = ops.move_file(source, dest)

        assert success is True
        assert dest.exists()
        assert dest.parent.is_dir()

    def test_move_fails_without_create_dirs(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test")
        dest = temp_dir / "nonexistent" / "file.jpg"

        ops = FileOperations(dry_run=False, create_dirs=False)
        success, message = ops.move_file(source, dest)

        assert success is False
        assert "failed" in message.lower()

    def test_move_nonexistent_source(self, temp_dir: Path):
        source = temp_dir / "nonexistent.jpg"
        dest = temp_dir / "dest.jpg"

        ops = FileOperations(dry_run=False)
        success, message = ops.move_file(source, dest)

        assert success is False
        assert "not found" in message

    def test_move_directory_as_source(self, temp_dir: Path):
        source = temp_dir / "directory"
        source.mkdir()
        dest = temp_dir / "dest.jpg"

        ops = FileOperations(dry_run=False)
        success, message = ops.move_file(source, dest)

        assert success is False
        assert "not a file" in message

    def test_move_to_existing_destination(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"source content")
        dest = temp_dir / "dest.jpg"
        dest.write_bytes(b"existing content")

        ops = FileOperations(dry_run=False)
        success, message = ops.move_file(source, dest)

        assert success is False
        assert "already exists" in message
        # Original should be unchanged
        assert source.read_bytes() == b"source content"
        assert dest.read_bytes() == b"existing content"


class TestCopyFile:
    """Tests for copy_file method."""

    def test_dry_run_does_not_copy(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test content")
        dest = temp_dir / "copied.jpg"

        ops = FileOperations(dry_run=True)
        success, message = ops.copy_file(source, dest)

        assert success is True
        assert "Dry run" in message
        assert source.exists()
        assert not dest.exists()

    def test_actual_copy(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test content")
        dest = temp_dir / "copied.jpg"

        ops = FileOperations(dry_run=False)
        success, message = ops.copy_file(source, dest)

        assert success is True
        assert "successfully" in message
        assert source.exists()  # Original still exists
        assert dest.exists()  # Copy exists
        assert dest.read_bytes() == b"test content"

    def test_copy_creates_directories(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test")
        dest = temp_dir / "a" / "b" / "file.jpg"

        ops = FileOperations(dry_run=False, create_dirs=True)
        success, _ = ops.copy_file(source, dest)

        assert success is True
        assert dest.exists()

    def test_copy_nonexistent_source(self, temp_dir: Path):
        source = temp_dir / "nonexistent.jpg"
        dest = temp_dir / "dest.jpg"

        ops = FileOperations(dry_run=False)
        success, message = ops.copy_file(source, dest)

        assert success is False
        assert "not found" in message

    def test_copy_to_existing_destination(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"source")
        dest = temp_dir / "dest.jpg"
        dest.write_bytes(b"existing")

        ops = FileOperations(dry_run=False)
        success, message = ops.copy_file(source, dest)

        assert success is False
        assert "already exists" in message


class TestEnsureUniquePath:
    """Tests for ensure_unique_path method."""

    def test_unique_path_unchanged(self, temp_dir: Path):
        path = temp_dir / "unique.jpg"

        ops = FileOperations()
        result = ops.ensure_unique_path(path)

        assert result == path

    def test_adds_counter_when_exists(self, temp_dir: Path):
        path = temp_dir / "photo.jpg"
        path.write_bytes(b"test")

        ops = FileOperations()
        result = ops.ensure_unique_path(path)

        assert result == temp_dir / "photo_001.jpg"

    def test_increments_counter(self, temp_dir: Path):
        base = temp_dir / "photo.jpg"
        base.write_bytes(b"test")
        (temp_dir / "photo_001.jpg").write_bytes(b"test")
        (temp_dir / "photo_002.jpg").write_bytes(b"test")

        ops = FileOperations()
        result = ops.ensure_unique_path(base)

        assert result == temp_dir / "photo_003.jpg"

    def test_preserves_extension(self, temp_dir: Path):
        path = temp_dir / "video.mp4"
        path.write_bytes(b"test")

        ops = FileOperations()
        result = ops.ensure_unique_path(path)

        assert result.suffix == ".mp4"

    def test_safety_limit(self, temp_dir: Path):
        base = temp_dir / "photo.jpg"
        base.write_bytes(b"test")

        # Create many existing files
        for i in range(1, 10001):
            (temp_dir / f"photo_{i:03d}.jpg").write_bytes(b"test")

        ops = FileOperations()

        with pytest.raises(FileOperationError) as exc_info:
            ops.ensure_unique_path(base)

        assert "unique filename" in str(exc_info.value)


class TestCheckDiskSpace:
    """Tests for check_disk_space method."""

    def test_sufficient_space(self, temp_dir: Path):
        ops = FileOperations()
        has_space, available = ops.check_disk_space(temp_dir, 1024)

        assert has_space is True
        assert available > 0

    def test_insufficient_space(self, temp_dir: Path):
        ops = FileOperations()
        # Request an absurdly large amount
        huge_size = 10**18  # 1 exabyte
        has_space, available = ops.check_disk_space(temp_dir, huge_size)

        assert has_space is False
        assert available > 0

    def test_nonexistent_path_uses_parent(self, temp_dir: Path):
        nonexistent = temp_dir / "a" / "b" / "c" / "file.jpg"

        ops = FileOperations()
        has_space, available = ops.check_disk_space(nonexistent, 1024)

        # Should work using parent that exists
        assert has_space is True


class TestEnsureDirectory:
    """Tests for ensure_directory method."""

    def test_dry_run_returns_true(self, temp_dir: Path):
        path = temp_dir / "new" / "dir"

        ops = FileOperations(dry_run=True)
        result = ops.ensure_directory(path)

        assert result is True
        assert not path.exists()

    def test_creates_directory(self, temp_dir: Path):
        path = temp_dir / "new" / "nested" / "dir"

        ops = FileOperations(dry_run=False)
        result = ops.ensure_directory(path)

        assert result is True
        assert path.is_dir()

    def test_existing_directory_ok(self, temp_dir: Path):
        path = temp_dir / "existing"
        path.mkdir()

        ops = FileOperations(dry_run=False)
        result = ops.ensure_directory(path)

        assert result is True
        assert path.is_dir()


class TestBatchOperationsInit:
    """Tests for BatchOperations initialization."""

    def test_default_init(self):
        batch = BatchOperations()

        assert batch.dry_run is True
        assert batch.file_ops is not None
        assert batch.completed == []
        assert batch.failed == []

    def test_custom_file_ops(self):
        custom_ops = FileOperations(dry_run=False)
        batch = BatchOperations(file_ops=custom_ops)

        assert batch.file_ops is custom_ops


class TestExecuteMoves:
    """Tests for execute_moves method."""

    def test_dry_run_batch(self, temp_dir: Path):
        source1 = temp_dir / "file1.jpg"
        source2 = temp_dir / "file2.jpg"
        source1.write_bytes(b"content1")
        source2.write_bytes(b"content2")

        dest1 = temp_dir / "dest" / "file1.jpg"
        dest2 = temp_dir / "dest" / "file2.jpg"

        batch = BatchOperations(dry_run=True)
        operations = [(source1, dest1), (source2, dest2)]
        success, failure = batch.execute_moves(operations)

        assert success == 2
        assert failure == 0
        assert len(batch.completed) == 2
        # Files should still exist (dry run)
        assert source1.exists()
        assert source2.exists()

    def test_actual_batch_move(self, temp_dir: Path):
        source1 = temp_dir / "file1.jpg"
        source2 = temp_dir / "file2.jpg"
        source1.write_bytes(b"content1")
        source2.write_bytes(b"content2")

        dest_dir = temp_dir / "dest"
        dest1 = dest_dir / "file1.jpg"
        dest2 = dest_dir / "file2.jpg"

        file_ops = FileOperations(dry_run=False, create_dirs=True)
        batch = BatchOperations(file_ops=file_ops, dry_run=False)
        operations = [(source1, dest1), (source2, dest2)]
        success, failure = batch.execute_moves(operations)

        assert success == 2
        assert failure == 0
        assert not source1.exists()
        assert not source2.exists()
        assert dest1.exists()
        assert dest2.exists()

    def test_partial_failure(self, temp_dir: Path):
        source1 = temp_dir / "exists.jpg"
        source2 = temp_dir / "nonexistent.jpg"
        source1.write_bytes(b"content")

        dest1 = temp_dir / "dest" / "file1.jpg"
        dest2 = temp_dir / "dest" / "file2.jpg"

        file_ops = FileOperations(dry_run=False, create_dirs=True)
        batch = BatchOperations(file_ops=file_ops, dry_run=False)
        operations = [(source1, dest1), (source2, dest2)]
        success, failure = batch.execute_moves(operations)

        assert success == 1
        assert failure == 1
        assert len(batch.completed) == 1
        assert len(batch.failed) == 1

    def test_failed_contains_error_message(self, temp_dir: Path):
        source = temp_dir / "nonexistent.jpg"
        dest = temp_dir / "dest.jpg"

        file_ops = FileOperations(dry_run=False)
        batch = BatchOperations(file_ops=file_ops, dry_run=False)
        batch.execute_moves([(source, dest)])

        assert len(batch.failed) == 1
        failed_src, failed_dest, message = batch.failed[0]
        assert failed_src == source
        assert failed_dest == dest
        assert "not found" in message


class TestRollback:
    """Tests for rollback method."""

    def test_rollback_dry_run(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test")
        dest = temp_dir / "dest" / "file.jpg"

        batch = BatchOperations(dry_run=True)
        batch.execute_moves([(source, dest)])

        rolled_back = batch.rollback()

        assert rolled_back == 1

    def test_rollback_actual_moves(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"original content")
        dest = temp_dir / "dest" / "moved.jpg"

        file_ops = FileOperations(dry_run=False, create_dirs=True)
        batch = BatchOperations(file_ops=file_ops, dry_run=False)
        batch.execute_moves([(source, dest)])

        # File should be moved
        assert not source.exists()
        assert dest.exists()

        rolled_back = batch.rollback()

        assert rolled_back == 1
        assert source.exists()
        assert source.read_bytes() == b"original content"

    def test_rollback_clears_completed(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test")
        dest = temp_dir / "dest" / "file.jpg"

        file_ops = FileOperations(dry_run=False, create_dirs=True)
        batch = BatchOperations(file_ops=file_ops, dry_run=False)
        batch.execute_moves([(source, dest)])

        assert len(batch.completed) == 1

        batch.rollback()

        assert len(batch.completed) == 0


class TestBatchProperties:
    """Tests for BatchOperations properties."""

    def test_completed_returns_copy(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test")
        dest = temp_dir / "dest.jpg"

        batch = BatchOperations(dry_run=True)
        batch.execute_moves([(source, dest)])

        completed = batch.completed
        completed.append((Path("/fake1"), Path("/fake2")))

        # Original should not be modified
        assert len(batch.completed) == 1

    def test_failed_returns_copy(self, temp_dir: Path):
        source = temp_dir / "nonexistent.jpg"
        dest = temp_dir / "dest.jpg"

        file_ops = FileOperations(dry_run=False)
        batch = BatchOperations(file_ops=file_ops, dry_run=False)
        batch.execute_moves([(source, dest)])

        failed = batch.failed
        failed.append((Path("/a"), Path("/b"), "fake"))

        assert len(batch.failed) == 1


class TestReset:
    """Tests for reset method."""

    def test_reset_clears_tracking(self, temp_dir: Path):
        source1 = temp_dir / "source.jpg"
        source2 = temp_dir / "nonexistent.jpg"
        source1.write_bytes(b"test")
        dest1 = temp_dir / "dest1.jpg"
        dest2 = temp_dir / "dest2.jpg"

        file_ops = FileOperations(dry_run=False)
        batch = BatchOperations(file_ops=file_ops, dry_run=False)
        batch.execute_moves([(source1, dest1), (source2, dest2)])

        assert len(batch.completed) == 1
        assert len(batch.failed) == 1

        batch.reset()

        assert batch.completed == []
        assert batch.failed == []


class TestPreserveMetadata:
    """Tests for metadata preservation."""

    def test_copy_preserves_metadata_by_default(self, temp_dir: Path):
        source = temp_dir / "source.jpg"
        source.write_bytes(b"test content")

        import time
        # Set a specific modification time
        old_time = time.time() - 3600  # 1 hour ago
        import os
        os.utime(source, (old_time, old_time))

        dest = temp_dir / "dest.jpg"

        ops = FileOperations(dry_run=False, preserve_metadata=True)
        ops.copy_file(source, dest)

        # Modification times should be close
        source_mtime = source.stat().st_mtime
        dest_mtime = dest.stat().st_mtime
        assert abs(source_mtime - dest_mtime) < 1.0


class TestFileOperationError:
    """Tests for FileOperationError exception."""

    def test_can_raise(self):
        with pytest.raises(FileOperationError) as exc_info:
            raise FileOperationError("Test error")

        assert "Test error" in str(exc_info.value)

    def test_is_exception(self):
        error = FileOperationError("message")
        assert isinstance(error, Exception)
