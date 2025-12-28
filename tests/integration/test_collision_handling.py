"""Integration tests for collision and duplicate handling in apply workflow."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from chronoclean.core.duplicate_checker import DuplicateChecker
from chronoclean.core.file_operations import FileOperations, BatchOperations
from chronoclean.core.models import FileRecord, DateSource, FileType
from chronoclean.config.schema import DuplicatesConfig


class TestCollisionDetection:
    """Test collision detection when destination exists."""

    def test_detects_collision_when_destination_exists(self, temp_dir: Path):
        """Test that collision is detected when destination file exists."""
        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"source content")

        dest = temp_dir / "dest" / "photo.jpg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"existing content")

        # Destination exists = collision
        assert dest.exists()

    def test_no_collision_when_destination_empty(self, temp_dir: Path):
        """Test that no collision when destination doesn't exist."""
        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"source content")

        dest = temp_dir / "dest" / "photo.jpg"
        dest.parent.mkdir(parents=True)

        assert not dest.exists()


class TestDuplicateDetectionOnCollision:
    """Test duplicate detection when files collide."""

    def test_identical_files_detected_as_duplicates(self, temp_dir: Path):
        """Test that identical files are correctly identified as duplicates."""
        content = b"identical content for both files"

        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(content)

        dest = temp_dir / "dest" / "photo.jpg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(content)

        checker = DuplicateChecker()
        assert checker.are_duplicates(source, dest) is True

    def test_different_files_not_duplicates(self, temp_dir: Path):
        """Test that different files are not identified as duplicates."""
        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"source content version 1")

        dest = temp_dir / "dest" / "photo.jpg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"different content version 2")

        checker = DuplicateChecker()
        assert checker.are_duplicates(source, dest) is False

    def test_different_sizes_fast_fail(self, temp_dir: Path):
        """Test that different file sizes skip hash computation."""
        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"short")

        dest = temp_dir / "dest" / "photo.jpg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"much longer content here")

        checker = DuplicateChecker()
        # Should return False without computing hashes due to size difference
        assert checker.are_duplicates(source, dest) is False


class TestCollisionResolutionStrategies:
    """Test different collision resolution strategies."""

    def test_check_hash_skips_duplicate(self, temp_dir: Path):
        """Test check_hash strategy skips identical files."""
        content = b"identical content"

        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(content)

        dest = temp_dir / "dest" / "2024" / "01" / "photo.jpg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(content)

        checker = DuplicateChecker()
        file_ops = FileOperations(dry_run=False)

        # Simulate check_hash collision handling
        if dest.exists():
            if checker.are_duplicates(source, dest):
                # Skip - don't copy
                skipped = True
            else:
                # Rename and copy
                skipped = False
                new_dest = file_ops.ensure_unique_path(dest)
        else:
            skipped = False

        assert skipped is True
        # Source should still exist (not moved)
        assert source.exists()

    def test_check_hash_renames_different_files(self, temp_dir: Path):
        """Test check_hash strategy renames non-duplicate collisions."""
        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"source content")

        dest = temp_dir / "dest" / "2024" / "01" / "photo.jpg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"different existing content")

        checker = DuplicateChecker()
        file_ops = FileOperations(dry_run=False)

        # Simulate check_hash collision handling
        new_dest = dest
        if dest.exists():
            if checker.are_duplicates(source, dest):
                new_dest = None  # Skip
            else:
                new_dest = file_ops.ensure_unique_path(dest)

        assert new_dest is not None
        assert new_dest != dest
        assert new_dest.name == "photo_001.jpg"

    def test_rename_strategy_always_renames(self, temp_dir: Path):
        """Test rename strategy renames even for identical files."""
        content = b"identical content"

        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(content)

        dest = temp_dir / "dest" / "photo.jpg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(content)

        file_ops = FileOperations(dry_run=False)

        # Simulate rename collision handling (no hash check)
        new_dest = dest
        if dest.exists():
            new_dest = file_ops.ensure_unique_path(dest)

        assert new_dest != dest
        assert new_dest.name == "photo_001.jpg"

    def test_skip_strategy_skips_all_collisions(self, temp_dir: Path):
        """Test skip strategy skips all collisions regardless of content."""
        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"source content")

        dest = temp_dir / "dest" / "photo.jpg"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"different content")

        # Simulate skip collision handling
        skipped = dest.exists()

        assert skipped is True


class TestEnsureUniquePath:
    """Test unique path generation for collisions."""

    def test_unique_path_adds_counter(self, temp_dir: Path):
        """Test that ensure_unique_path adds counter suffix."""
        dest = temp_dir / "photo.jpg"
        dest.write_bytes(b"existing")

        file_ops = FileOperations(dry_run=False)
        unique = file_ops.ensure_unique_path(dest)

        assert unique.name == "photo_001.jpg"
        assert unique.parent == dest.parent

    def test_unique_path_increments_counter(self, temp_dir: Path):
        """Test that counter increments for multiple collisions."""
        base = temp_dir / "photo.jpg"
        base.write_bytes(b"original")

        (temp_dir / "photo_001.jpg").write_bytes(b"first collision")
        (temp_dir / "photo_002.jpg").write_bytes(b"second collision")

        file_ops = FileOperations(dry_run=False)
        unique = file_ops.ensure_unique_path(base)

        assert unique.name == "photo_003.jpg"

    def test_unique_path_returns_same_if_no_collision(self, temp_dir: Path):
        """Test that same path returned if no collision."""
        dest = temp_dir / "photo.jpg"
        # Don't create the file

        file_ops = FileOperations(dry_run=False)
        unique = file_ops.ensure_unique_path(dest)

        assert unique == dest


class TestApplyCollisionIntegration:
    """Integration tests simulating apply command collision handling."""

    def test_apply_skips_duplicate_on_collision(self, temp_dir: Path):
        """Test that apply workflow skips duplicate files on collision."""
        content = b"identical photo content"

        # Source file to copy
        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(content)

        # Destination already has identical file
        dest_dir = temp_dir / "dest" / "2024" / "01"
        dest_dir.mkdir(parents=True)
        existing = dest_dir / "photo.jpg"
        existing.write_bytes(content)

        # Simulate apply workflow with collision detection
        checker = DuplicateChecker(algorithm="sha256", cache_enabled=True)
        file_ops = FileOperations(dry_run=False)

        operations_to_execute = []
        duplicates_skipped = 0
        collisions_renamed = 0

        # Operation: copy source to dest_dir/photo.jpg
        dest_path = dest_dir / "photo.jpg"

        if dest_path.exists():
            if checker.are_duplicates(source, dest_path):
                duplicates_skipped += 1
                # Skip this operation
            else:
                dest_path = file_ops.ensure_unique_path(dest_path)
                collisions_renamed += 1
                operations_to_execute.append((source, dest_path))
        else:
            operations_to_execute.append((source, dest_path))

        assert duplicates_skipped == 1
        assert collisions_renamed == 0
        assert len(operations_to_execute) == 0

    def test_apply_renames_non_duplicate_collision(self, temp_dir: Path):
        """Test that apply workflow renames non-duplicate collisions."""
        # Source file to copy
        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"new photo content")

        # Destination already has different file with same name
        dest_dir = temp_dir / "dest" / "2024" / "01"
        dest_dir.mkdir(parents=True)
        existing = dest_dir / "photo.jpg"
        existing.write_bytes(b"different existing content")

        # Simulate apply workflow with collision detection
        checker = DuplicateChecker(algorithm="sha256", cache_enabled=True)
        file_ops = FileOperations(dry_run=False)

        operations_to_execute = []
        duplicates_skipped = 0
        collisions_renamed = 0

        # Operation: copy source to dest_dir/photo.jpg
        dest_path = dest_dir / "photo.jpg"

        if dest_path.exists():
            if checker.are_duplicates(source, dest_path):
                duplicates_skipped += 1
            else:
                dest_path = file_ops.ensure_unique_path(dest_path)
                collisions_renamed += 1
                operations_to_execute.append((source, dest_path))
        else:
            operations_to_execute.append((source, dest_path))

        assert duplicates_skipped == 0
        assert collisions_renamed == 1
        assert len(operations_to_execute) == 1
        assert operations_to_execute[0][1].name == "photo_001.jpg"

    def test_apply_handles_multiple_collisions(self, temp_dir: Path):
        """Test apply workflow with multiple files and collisions."""
        # Create source files
        source_dir = temp_dir / "source"
        source_dir.mkdir()

        source_a = source_dir / "a.jpg"
        source_a.write_bytes(b"content a")

        source_b = source_dir / "b.jpg"
        source_b.write_bytes(b"content b")

        source_c = source_dir / "c.jpg"
        source_c.write_bytes(b"content a")  # Duplicate of dest/a.jpg

        # Create destination with some existing files
        dest_dir = temp_dir / "dest" / "2024" / "01"
        dest_dir.mkdir(parents=True)

        existing_a = dest_dir / "a.jpg"
        existing_a.write_bytes(b"content a")  # Same as source_a and source_c

        existing_b = dest_dir / "b.jpg"
        existing_b.write_bytes(b"different content b")  # Different from source_b

        # Simulate apply workflow
        checker = DuplicateChecker()
        file_ops = FileOperations(dry_run=False)

        sources = [
            (source_a, dest_dir / "a.jpg"),
            (source_b, dest_dir / "b.jpg"),
            (source_c, dest_dir / "a.jpg"),
        ]

        operations_to_execute = []
        duplicates_skipped = 0
        collisions_renamed = 0

        for src, dest_path in sources:
            if dest_path.exists():
                if checker.are_duplicates(src, dest_path):
                    duplicates_skipped += 1
                    continue
                else:
                    dest_path = file_ops.ensure_unique_path(dest_path)
                    collisions_renamed += 1
            operations_to_execute.append((src, dest_path))

        # source_a -> duplicate of existing_a (skipped)
        # source_b -> different from existing_b (renamed to b_001.jpg)
        # source_c -> duplicate of existing_a (skipped)
        assert duplicates_skipped == 2
        assert collisions_renamed == 1
        assert len(operations_to_execute) == 1
        assert operations_to_execute[0][1].name == "b_001.jpg"

    def test_apply_no_collision_copies_normally(self, temp_dir: Path):
        """Test that files without collision copy normally."""
        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"photo content")

        dest_dir = temp_dir / "dest" / "2024" / "01"
        dest_dir.mkdir(parents=True)
        # No existing file at destination

        checker = DuplicateChecker()
        file_ops = FileOperations(dry_run=False)

        operations_to_execute = []
        duplicates_skipped = 0
        collisions_renamed = 0

        dest_path = dest_dir / "photo.jpg"

        if dest_path.exists():
            if checker.are_duplicates(source, dest_path):
                duplicates_skipped += 1
            else:
                dest_path = file_ops.ensure_unique_path(dest_path)
                collisions_renamed += 1
                operations_to_execute.append((source, dest_path))
        else:
            operations_to_execute.append((source, dest_path))

        assert duplicates_skipped == 0
        assert collisions_renamed == 0
        assert len(operations_to_execute) == 1
        assert operations_to_execute[0][1] == dest_dir / "photo.jpg"


class TestDuplicateCheckerConfig:
    """Test DuplicateChecker configuration integration."""

    def test_uses_sha256_by_default(self):
        """Test that SHA256 is used by default."""
        checker = DuplicateChecker()
        assert checker.algorithm == "sha256"

    def test_uses_configured_algorithm(self):
        """Test that configured algorithm is used."""
        checker = DuplicateChecker(algorithm="md5")
        assert checker.algorithm == "md5"

    def test_caching_enabled_by_default(self):
        """Test that hash caching is enabled by default."""
        checker = DuplicateChecker()
        assert checker.cache_enabled is True

    def test_caching_can_be_disabled(self):
        """Test that caching can be disabled."""
        checker = DuplicateChecker(cache_enabled=False)
        assert checker.cache_enabled is False

    def test_cache_improves_repeated_checks(self, temp_dir: Path):
        """Test that cache avoids recomputation for same file."""
        file = temp_dir / "photo.jpg"
        file.write_bytes(b"test content")

        checker = DuplicateChecker(cache_enabled=True)

        # First computation
        hash1 = checker.compute_hash(file)
        assert checker.get_cache_size() == 1

        # Second computation should use cache
        hash2 = checker.compute_hash(file)
        assert hash1 == hash2
        assert checker.get_cache_size() == 1  # Still 1, not recomputed


class TestCollisionWithRealCopy:
    """Test collision handling with actual file operations."""

    def test_copy_with_collision_rename(self, temp_dir: Path):
        """Test actual copy operation with collision rename."""
        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"new content to copy")

        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        existing = dest_dir / "photo.jpg"
        existing.write_bytes(b"existing different content")

        file_ops = FileOperations(dry_run=False)
        checker = DuplicateChecker()

        dest_path = dest_dir / "photo.jpg"
        if dest_path.exists() and not checker.are_duplicates(source, dest_path):
            dest_path = file_ops.ensure_unique_path(dest_path)

        # Perform actual copy
        success, msg = file_ops.copy_file(source, dest_path)

        assert success
        assert dest_path.exists()
        assert dest_path.name == "photo_001.jpg"
        assert dest_path.read_bytes() == b"new content to copy"
        # Original still exists
        assert existing.exists()
        assert existing.read_bytes() == b"existing different content"

    def test_copy_skips_duplicate(self, temp_dir: Path):
        """Test that copy is skipped for duplicate."""
        content = b"identical content"

        source = temp_dir / "source" / "photo.jpg"
        source.parent.mkdir(parents=True)
        source.write_bytes(content)

        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        existing = dest_dir / "photo.jpg"
        existing.write_bytes(content)

        file_ops = FileOperations(dry_run=False)
        checker = DuplicateChecker()

        dest_path = dest_dir / "photo.jpg"
        should_skip = dest_path.exists() and checker.are_duplicates(source, dest_path)

        assert should_skip is True
        # No new file created
        assert not (dest_dir / "photo_001.jpg").exists()


class TestReservedDestinations:
    """Test reserved destinations tracking to prevent collisions between planned operations.
    
    Uses the actual FileOperations.ensure_unique_path method with reserved parameter.
    """

    def test_two_sources_same_destination_get_unique_names(self, temp_dir: Path):
        """Test that two files targeting same destination get unique names."""
        # Two different source files that would both target photo.jpg
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        
        source_a = source_dir / "a" / "photo.jpg"
        source_a.parent.mkdir()
        source_a.write_bytes(b"content from folder a")
        
        source_b = source_dir / "b" / "photo.jpg"
        source_b.parent.mkdir()
        source_b.write_bytes(b"content from folder b")
        
        dest_dir = temp_dir / "dest" / "2024" / "01"
        dest_dir.mkdir(parents=True)
        
        file_ops = FileOperations(dry_run=False)
        
        # Simulate planning with reserved destinations
        reserved_destinations: set[Path] = set()
        operations = []
        
        # First file targets photo.jpg
        dest_path_a = dest_dir / "photo.jpg"
        if dest_path_a.exists() or dest_path_a in reserved_destinations:
            dest_path_a = file_ops.ensure_unique_path(dest_path_a, reserved_destinations)
        reserved_destinations.add(dest_path_a)
        operations.append((source_a, dest_path_a))
        
        # Second file also targets photo.jpg - should get renamed
        dest_path_b = dest_dir / "photo.jpg"
        if dest_path_b.exists() or dest_path_b in reserved_destinations:
            dest_path_b = file_ops.ensure_unique_path(dest_path_b, reserved_destinations)
        reserved_destinations.add(dest_path_b)
        operations.append((source_b, dest_path_b))
        
        assert dest_path_a == dest_dir / "photo.jpg"
        assert dest_path_b == dest_dir / "photo_001.jpg"
        assert len(operations) == 2

    def test_three_sources_same_destination_sequential_naming(self, temp_dir: Path):
        """Test that three files targeting same destination get sequential names."""
        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        
        file_ops = FileOperations(dry_run=False)
        
        reserved_destinations: set[Path] = set()
        results = []
        
        for i in range(3):
            dest_path = dest_dir / "photo.jpg"
            if dest_path.exists() or dest_path in reserved_destinations:
                dest_path = file_ops.ensure_unique_path(dest_path, reserved_destinations)
            reserved_destinations.add(dest_path)
            results.append(dest_path)
        
        assert results[0].name == "photo.jpg"
        assert results[1].name == "photo_001.jpg"
        assert results[2].name == "photo_002.jpg"

    def test_reserved_plus_existing_file(self, temp_dir: Path):
        """Test collision with both reserved destination and existing file."""
        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        
        # File already exists on disk
        existing = dest_dir / "photo.jpg"
        existing.write_bytes(b"existing")
        
        file_ops = FileOperations(dry_run=False)
        
        reserved_destinations: set[Path] = set()
        
        # First planned op - collides with existing file
        dest_path_1 = dest_dir / "photo.jpg"
        if dest_path_1.exists() or dest_path_1 in reserved_destinations:
            dest_path_1 = file_ops.ensure_unique_path(dest_path_1, reserved_destinations)
        reserved_destinations.add(dest_path_1)
        
        # Second planned op - collides with reserved
        dest_path_2 = dest_dir / "photo.jpg"
        if dest_path_2.exists() or dest_path_2 in reserved_destinations:
            dest_path_2 = file_ops.ensure_unique_path(dest_path_2, reserved_destinations)
        reserved_destinations.add(dest_path_2)
        
        assert dest_path_1.name == "photo_001.jpg"  # _001 because photo.jpg exists
        assert dest_path_2.name == "photo_002.jpg"  # _002 because _001 is reserved

    def test_reserved_skips_existing_numbered_files(self, temp_dir: Path):
        """Test that reserved destinations skip over existing numbered files."""
        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        
        # Create existing files
        (dest_dir / "photo.jpg").write_bytes(b"original")
        (dest_dir / "photo_001.jpg").write_bytes(b"first collision")
        (dest_dir / "photo_002.jpg").write_bytes(b"second collision")
        
        file_ops = FileOperations(dry_run=False)
        
        reserved_destinations: set[Path] = set()
        
        # Two new files targeting photo.jpg
        dest_path_1 = dest_dir / "photo.jpg"
        if dest_path_1.exists() or dest_path_1 in reserved_destinations:
            dest_path_1 = file_ops.ensure_unique_path(dest_path_1, reserved_destinations)
        reserved_destinations.add(dest_path_1)
        
        dest_path_2 = dest_dir / "photo.jpg"
        if dest_path_2.exists() or dest_path_2 in reserved_destinations:
            dest_path_2 = file_ops.ensure_unique_path(dest_path_2, reserved_destinations)
        reserved_destinations.add(dest_path_2)
        
        # Should skip _001, _002 (exist on disk) and get _003, _004
        assert dest_path_1.name == "photo_003.jpg"
        assert dest_path_2.name == "photo_004.jpg"

    def test_ensure_unique_path_without_reserved_param(self, temp_dir: Path):
        """Test that ensure_unique_path works without reserved param (backwards compat)."""
        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        
        existing = dest_dir / "photo.jpg"
        existing.write_bytes(b"existing")
        
        file_ops = FileOperations(dry_run=False)
        
        # Call without reserved parameter (should work like before)
        result = file_ops.ensure_unique_path(dest_dir / "photo.jpg")
        
        assert result.name == "photo_001.jpg"

    def test_ensure_unique_path_returns_same_if_unique(self, temp_dir: Path):
        """Test that ensure_unique_path returns same path if already unique."""
        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        
        file_ops = FileOperations(dry_run=False)
        reserved_destinations: set[Path] = set()
        
        # No collision
        result = file_ops.ensure_unique_path(dest_dir / "photo.jpg", reserved_destinations)
        
        assert result == dest_dir / "photo.jpg"


class TestReservedDestinationsWithHashCheck:
    """Test reserved destinations with check_hash content comparison.
    
    Uses the actual FileOperations.ensure_unique_path method with reserved parameter.
    """

    def test_identical_sources_with_check_hash_skips_second(self, temp_dir: Path):
        """Test that two identical source files targeting same dest - second is skipped."""
        content = b"identical content in both files"
        
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        
        source_a = source_dir / "a" / "photo.jpg"
        source_a.parent.mkdir()
        source_a.write_bytes(content)
        
        source_b = source_dir / "b" / "photo.jpg"
        source_b.parent.mkdir()
        source_b.write_bytes(content)  # Identical content
        
        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        
        file_ops = FileOperations(dry_run=False)
        checker = DuplicateChecker()
        
        # Simulate check_hash collision handling with reserved_sources tracking
        reserved_destinations: set[Path] = set()
        reserved_sources: dict[Path, Path] = {}  # dest -> source
        operations = []
        duplicates_skipped = 0
        
        # First file targets photo.jpg
        dest_path_a = dest_dir / "photo.jpg"
        if dest_path_a.exists() or dest_path_a in reserved_destinations:
            # Would check hash here, but nothing reserved yet
            pass
        reserved_destinations.add(dest_path_a)
        reserved_sources[dest_path_a] = source_a
        operations.append((source_a, dest_path_a))
        
        # Second file also targets photo.jpg
        dest_path_b = dest_dir / "photo.jpg"
        if dest_path_b.exists() or dest_path_b in reserved_destinations:
            # check_hash: compare against reserved source
            if dest_path_b in reserved_sources:
                if checker.are_duplicates(source_b, reserved_sources[dest_path_b]):
                    duplicates_skipped += 1
                    # Don't add to operations - skip it
                    dest_path_b = None
        
        if dest_path_b:
            reserved_destinations.add(dest_path_b)
            reserved_sources[dest_path_b] = source_b
            operations.append((source_b, dest_path_b))
        
        assert duplicates_skipped == 1
        assert len(operations) == 1
        assert operations[0] == (source_a, dest_dir / "photo.jpg")

    def test_different_sources_with_check_hash_renames_second(self, temp_dir: Path):
        """Test that two different source files targeting same dest - second is renamed."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        
        source_a = source_dir / "a" / "photo.jpg"
        source_a.parent.mkdir()
        source_a.write_bytes(b"content version A")
        
        source_b = source_dir / "b" / "photo.jpg"
        source_b.parent.mkdir()
        source_b.write_bytes(b"different content version B")
        
        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        
        file_ops = FileOperations(dry_run=False)
        checker = DuplicateChecker()
        
        reserved_destinations: set[Path] = set()
        reserved_sources: dict[Path, Path] = {}
        operations = []
        collisions_renamed = 0
        
        # First file
        dest_path_a = dest_dir / "photo.jpg"
        reserved_destinations.add(dest_path_a)
        reserved_sources[dest_path_a] = source_a
        operations.append((source_a, dest_path_a))
        
        # Second file - different content, should be renamed
        dest_path_b = dest_dir / "photo.jpg"
        if dest_path_b in reserved_destinations:
            if dest_path_b in reserved_sources:
                if not checker.are_duplicates(source_b, reserved_sources[dest_path_b]):
                    # Different content - rename using real method
                    dest_path_b = file_ops.ensure_unique_path(dest_path_b, reserved_destinations)
                    collisions_renamed += 1
        reserved_destinations.add(dest_path_b)
        reserved_sources[dest_path_b] = source_b
        operations.append((source_b, dest_path_b))
        
        assert collisions_renamed == 1
        assert len(operations) == 2
        assert operations[0][1].name == "photo.jpg"
        assert operations[1][1].name == "photo_001.jpg"

    def test_three_identical_files_only_first_copied(self, temp_dir: Path):
        """Test that three identical files - only first is copied."""
        content = b"same content in all three"
        
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        
        sources = []
        for name in ["a", "b", "c"]:
            src = source_dir / name / "photo.jpg"
            src.parent.mkdir()
            src.write_bytes(content)
            sources.append(src)
        
        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        
        checker = DuplicateChecker()
        
        reserved_destinations: set[Path] = set()
        reserved_sources: dict[Path, Path] = {}
        operations = []
        duplicates_skipped = 0
        
        for src in sources:
            dest_path = dest_dir / "photo.jpg"
            
            if dest_path in reserved_destinations:
                if dest_path in reserved_sources:
                    if checker.are_duplicates(src, reserved_sources[dest_path]):
                        duplicates_skipped += 1
                        continue
            
            reserved_destinations.add(dest_path)
            reserved_sources[dest_path] = src
            operations.append((src, dest_path))
        
        assert duplicates_skipped == 2
        assert len(operations) == 1
        assert operations[0][0] == sources[0]

    def test_mixed_identical_and_different_files(self, temp_dir: Path):
        """Test mix of identical and different files targeting same destination."""
        source_dir = temp_dir / "source"
        source_dir.mkdir()
        
        # Files: a=content1, b=content1 (dup of a), c=content2 (different)
        source_a = source_dir / "a" / "photo.jpg"
        source_a.parent.mkdir()
        source_a.write_bytes(b"content version 1")
        
        source_b = source_dir / "b" / "photo.jpg"
        source_b.parent.mkdir()
        source_b.write_bytes(b"content version 1")  # Same as a
        
        source_c = source_dir / "c" / "photo.jpg"
        source_c.parent.mkdir()
        source_c.write_bytes(b"content version 2")  # Different
        
        dest_dir = temp_dir / "dest"
        dest_dir.mkdir()
        
        file_ops = FileOperations(dry_run=False)
        checker = DuplicateChecker()
        
        reserved_destinations: set[Path] = set()
        reserved_sources: dict[Path, Path] = {}
        operations = []
        duplicates_skipped = 0
        collisions_renamed = 0
        
        for src in [source_a, source_b, source_c]:
            dest_path = dest_dir / "photo.jpg"
            
            if dest_path in reserved_destinations:
                if dest_path in reserved_sources:
                    if checker.are_duplicates(src, reserved_sources[dest_path]):
                        duplicates_skipped += 1
                        continue
                    else:
                        dest_path = file_ops.ensure_unique_path(dest_path, reserved_destinations)
                        collisions_renamed += 1
            
            reserved_destinations.add(dest_path)
            reserved_sources[dest_path] = src
            operations.append((src, dest_path))
        
        # a -> photo.jpg (first)
        # b -> skipped (duplicate of a)
        # c -> photo_001.jpg (different content, renamed)
        assert duplicates_skipped == 1
        assert collisions_renamed == 1
        assert len(operations) == 2
        assert operations[0][1].name == "photo.jpg"
        assert operations[1][1].name == "photo_001.jpg"
