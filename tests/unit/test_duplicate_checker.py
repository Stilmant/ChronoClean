"""Tests for duplicate checker module (v0.2)."""

import pytest
from pathlib import Path

from chronoclean.core.duplicate_checker import (
    DuplicateChecker,
    compute_file_hash,
    are_files_identical,
)


class TestDuplicateCheckerInit:
    """Tests for DuplicateChecker initialization."""

    def test_default_init(self):
        """Test default initialization."""
        checker = DuplicateChecker()
        assert checker.algorithm == "sha256"
        assert checker.cache_enabled is True

    def test_md5_algorithm(self):
        """Test MD5 algorithm option."""
        checker = DuplicateChecker(algorithm="md5")
        assert checker.algorithm == "md5"

    def test_sha256_algorithm(self):
        """Test SHA256 algorithm option."""
        checker = DuplicateChecker(algorithm="sha256")
        assert checker.algorithm == "sha256"

    def test_invalid_algorithm_falls_back(self):
        """Test invalid algorithm falls back to sha256."""
        checker = DuplicateChecker(algorithm="invalid")
        assert checker.algorithm == "sha256"

    def test_cache_disabled(self):
        """Test cache can be disabled."""
        checker = DuplicateChecker(cache_enabled=False)
        assert checker.cache_enabled is False

    def test_case_insensitive_algorithm(self):
        """Test algorithm name is case insensitive."""
        checker = DuplicateChecker(algorithm="SHA256")
        assert checker.algorithm == "sha256"


class TestComputeHash:
    """Tests for compute_hash method."""

    def test_hash_simple_file(self, tmp_path):
        """Test hashing a simple file."""
        file = tmp_path / "test.txt"
        file.write_text("Hello, World!")
        
        checker = DuplicateChecker()
        file_hash = checker.compute_hash(file)
        
        assert file_hash is not None
        assert len(file_hash) == 64  # SHA256 hex length

    def test_hash_empty_file(self, tmp_path):
        """Test hashing an empty file."""
        file = tmp_path / "empty.txt"
        file.touch()
        
        checker = DuplicateChecker()
        file_hash = checker.compute_hash(file)
        
        assert file_hash is not None
        # SHA256 of empty file is consistent
        assert file_hash == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"

    def test_hash_binary_file(self, tmp_path):
        """Test hashing a binary file."""
        file = tmp_path / "test.bin"
        file.write_bytes(bytes(range(256)))
        
        checker = DuplicateChecker()
        file_hash = checker.compute_hash(file)
        
        assert file_hash is not None
        assert len(file_hash) == 64

    def test_hash_md5(self, tmp_path):
        """Test MD5 hashing."""
        file = tmp_path / "test.txt"
        file.write_text("Hello, World!")
        
        checker = DuplicateChecker(algorithm="md5")
        file_hash = checker.compute_hash(file)
        
        assert file_hash is not None
        assert len(file_hash) == 32  # MD5 hex length

    def test_hash_nonexistent_file(self, tmp_path):
        """Test hashing nonexistent file returns None."""
        checker = DuplicateChecker()
        file_hash = checker.compute_hash(tmp_path / "nonexistent.txt")
        
        assert file_hash is None

    def test_hash_directory_returns_none(self, tmp_path):
        """Test hashing a directory returns None."""
        checker = DuplicateChecker()
        file_hash = checker.compute_hash(tmp_path)
        
        assert file_hash is None

    def test_hash_caching(self, tmp_path):
        """Test hash caching works."""
        file = tmp_path / "test.txt"
        file.write_text("content")
        
        checker = DuplicateChecker(cache_enabled=True)
        
        # First call
        hash1 = checker.compute_hash(file)
        assert checker.get_cache_size() == 1
        
        # Second call should use cache
        hash2 = checker.compute_hash(file)
        assert hash1 == hash2
        assert checker.get_cache_size() == 1

    def test_hash_no_caching(self, tmp_path):
        """Test hash caching can be disabled."""
        file = tmp_path / "test.txt"
        file.write_text("content")
        
        checker = DuplicateChecker(cache_enabled=False)
        
        checker.compute_hash(file)
        assert checker.get_cache_size() == 0

    def test_same_content_same_hash(self, tmp_path):
        """Test files with same content have same hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("identical content")
        file2.write_text("identical content")
        
        checker = DuplicateChecker()
        hash1 = checker.compute_hash(file1)
        hash2 = checker.compute_hash(file2)
        
        assert hash1 == hash2

    def test_different_content_different_hash(self, tmp_path):
        """Test files with different content have different hash."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content A")
        file2.write_text("content B")
        
        checker = DuplicateChecker()
        hash1 = checker.compute_hash(file1)
        hash2 = checker.compute_hash(file2)
        
        assert hash1 != hash2


class TestAreDuplicates:
    """Tests for are_duplicates method."""

    def test_identical_files_are_duplicates(self, tmp_path):
        """Test identical files detected as duplicates."""
        file1 = tmp_path / "file1.jpg"
        file2 = tmp_path / "file2.jpg"
        content = b"identical image data" * 100
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        checker = DuplicateChecker()
        assert checker.are_duplicates(file1, file2) is True

    def test_different_files_not_duplicates(self, tmp_path):
        """Test different files not detected as duplicates."""
        file1 = tmp_path / "file1.jpg"
        file2 = tmp_path / "file2.jpg"
        file1.write_bytes(b"content A")
        file2.write_bytes(b"content B")
        
        checker = DuplicateChecker()
        assert checker.are_duplicates(file1, file2) is False

    def test_same_file_is_duplicate(self, tmp_path):
        """Test same file path is considered duplicate."""
        file = tmp_path / "file.jpg"
        file.write_bytes(b"content")
        
        checker = DuplicateChecker()
        assert checker.are_duplicates(file, file) is True

    def test_nonexistent_not_duplicate(self, tmp_path):
        """Test nonexistent file is not duplicate."""
        file1 = tmp_path / "exists.txt"
        file1.write_text("content")
        file2 = tmp_path / "nonexistent.txt"
        
        checker = DuplicateChecker()
        assert checker.are_duplicates(file1, file2) is False

    def test_different_sizes_fast_fail(self, tmp_path):
        """Test different file sizes skip hash comparison."""
        file1 = tmp_path / "small.txt"
        file2 = tmp_path / "large.txt"
        file1.write_text("small")
        file2.write_text("much larger content here")
        
        checker = DuplicateChecker()
        # Should return False without computing hashes
        assert checker.are_duplicates(file1, file2) is False


class TestFindDuplicatesInList:
    """Tests for find_duplicates_in_list method."""

    def test_no_duplicates(self, tmp_path):
        """Test returns empty when no duplicates."""
        files = []
        for i in range(5):
            f = tmp_path / f"unique_{i}.txt"
            f.write_text(f"unique content {i}")
            files.append(f)
        
        checker = DuplicateChecker()
        duplicates = checker.find_duplicates_in_list(files)
        
        assert len(duplicates) == 0

    def test_finds_duplicates(self, tmp_path):
        """Test finds duplicate files."""
        # Create 2 duplicates and 1 unique
        dup_content = b"duplicate content"
        file1 = tmp_path / "dup1.jpg"
        file2 = tmp_path / "dup2.jpg"
        file3 = tmp_path / "unique.jpg"
        
        file1.write_bytes(dup_content)
        file2.write_bytes(dup_content)
        file3.write_bytes(b"unique content")
        
        checker = DuplicateChecker()
        duplicates = checker.find_duplicates_in_list([file1, file2, file3])
        
        assert len(duplicates) == 1
        dup_hash = list(duplicates.keys())[0]
        assert len(duplicates[dup_hash]) == 2
        assert file1 in duplicates[dup_hash]
        assert file2 in duplicates[dup_hash]

    def test_multiple_duplicate_groups(self, tmp_path):
        """Test finds multiple groups of duplicates."""
        # Group A: 2 files
        a1 = tmp_path / "a1.txt"
        a2 = tmp_path / "a2.txt"
        a1.write_text("content A")
        a2.write_text("content A")
        
        # Group B: 3 files
        b1 = tmp_path / "b1.txt"
        b2 = tmp_path / "b2.txt"
        b3 = tmp_path / "b3.txt"
        b1.write_text("content B")
        b2.write_text("content B")
        b3.write_text("content B")
        
        # Unique file
        unique = tmp_path / "unique.txt"
        unique.write_text("unique")
        
        checker = DuplicateChecker()
        duplicates = checker.find_duplicates_in_list([a1, a2, b1, b2, b3, unique])
        
        assert len(duplicates) == 2
        
        # Check group sizes
        group_sizes = sorted([len(v) for v in duplicates.values()])
        assert group_sizes == [2, 3]

    def test_empty_list(self, tmp_path):
        """Test empty list returns empty dict."""
        checker = DuplicateChecker()
        duplicates = checker.find_duplicates_in_list([])
        
        assert duplicates == {}


class TestCheckCollision:
    """Tests for check_collision method."""

    def test_no_collision(self, tmp_path):
        """Test no collision when destination doesn't exist."""
        source = tmp_path / "source.jpg"
        dest = tmp_path / "dest.jpg"
        source.write_bytes(b"content")
        
        checker = DuplicateChecker()
        collision, is_dup = checker.check_collision(source, dest)
        
        assert collision is False
        assert is_dup is False

    def test_collision_with_duplicate(self, tmp_path):
        """Test collision with duplicate content."""
        source = tmp_path / "source.jpg"
        dest = tmp_path / "dest.jpg"
        content = b"identical content"
        source.write_bytes(content)
        dest.write_bytes(content)
        
        checker = DuplicateChecker()
        collision, is_dup = checker.check_collision(source, dest)
        
        assert collision is True
        assert is_dup is True

    def test_collision_without_duplicate(self, tmp_path):
        """Test collision with different content."""
        source = tmp_path / "source.jpg"
        dest = tmp_path / "dest.jpg"
        source.write_bytes(b"source content")
        dest.write_bytes(b"different content")
        
        checker = DuplicateChecker()
        collision, is_dup = checker.check_collision(source, dest)
        
        assert collision is True
        assert is_dup is False


class TestCacheMethods:
    """Tests for cache management methods."""

    def test_clear_cache(self, tmp_path):
        """Test clear_cache removes all entries."""
        file = tmp_path / "test.txt"
        file.write_text("content")
        
        checker = DuplicateChecker()
        checker.compute_hash(file)
        assert checker.get_cache_size() == 1
        
        checker.clear_cache()
        assert checker.get_cache_size() == 0

    def test_get_cache_size(self, tmp_path):
        """Test get_cache_size returns correct count."""
        checker = DuplicateChecker()
        assert checker.get_cache_size() == 0
        
        for i in range(3):
            file = tmp_path / f"file_{i}.txt"
            file.write_text(f"content {i}")
            checker.compute_hash(file)
        
        assert checker.get_cache_size() == 3


class TestConvenienceFunctions:
    """Tests for module-level convenience functions."""

    def test_compute_file_hash(self, tmp_path):
        """Test compute_file_hash function."""
        file = tmp_path / "test.txt"
        file.write_text("Hello!")
        
        file_hash = compute_file_hash(file)
        
        assert file_hash is not None
        assert len(file_hash) == 64

    def test_compute_file_hash_md5(self, tmp_path):
        """Test compute_file_hash with MD5."""
        file = tmp_path / "test.txt"
        file.write_text("Hello!")
        
        file_hash = compute_file_hash(file, algorithm="md5")
        
        assert file_hash is not None
        assert len(file_hash) == 32

    def test_are_files_identical_true(self, tmp_path):
        """Test are_files_identical returns True for identical."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("same")
        file2.write_text("same")
        
        assert are_files_identical(file1, file2) is True

    def test_are_files_identical_false(self, tmp_path):
        """Test are_files_identical returns False for different."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_text("content A")
        file2.write_text("content B")
        
        assert are_files_identical(file1, file2) is False


class TestLargeFiles:
    """Tests for large file handling."""

    def test_large_file_hashing(self, tmp_path):
        """Test hashing a file larger than chunk size."""
        file = tmp_path / "large.bin"
        # Write 5MB of data (larger than 4MB chunk)
        chunk = bytes(range(256)) * 4096  # 1MB chunks
        with open(file, "wb") as f:
            for _ in range(5):
                f.write(chunk)
        
        checker = DuplicateChecker()
        file_hash = checker.compute_hash(file)
        
        assert file_hash is not None
        assert len(file_hash) == 64

    def test_large_duplicates(self, tmp_path):
        """Test duplicate detection for large files."""
        content = bytes(range(256)) * 4096 * 2  # 2MB
        
        file1 = tmp_path / "large1.bin"
        file2 = tmp_path / "large2.bin"
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        checker = DuplicateChecker()
        assert checker.are_duplicates(file1, file2) is True
