"""Tests for the hashing module."""

import hashlib
from pathlib import Path

import pytest

from chronoclean.core.hashing import (
    compute_file_hash,
    compare_file_hashes,
    hash_matches_any,
    DEFAULT_CHUNK_SIZE,
)


class TestComputeFileHash:
    """Tests for compute_file_hash function."""
    
    def test_sha256_hash_small_file(self, tmp_path):
        """Test SHA-256 hash computation for small file."""
        test_file = tmp_path / "test.txt"
        content = b"Hello, World!"
        test_file.write_bytes(content)
        
        result = compute_file_hash(test_file)
        
        expected = hashlib.sha256(content).hexdigest()
        assert result == expected
    
    def test_sha256_hash_empty_file(self, tmp_path):
        """Test SHA-256 hash for empty file."""
        test_file = tmp_path / "empty.txt"
        test_file.write_bytes(b"")
        
        result = compute_file_hash(test_file)
        
        expected = hashlib.sha256(b"").hexdigest()
        assert result == expected
    
    def test_md5_hash(self, tmp_path):
        """Test MD5 hash computation."""
        test_file = tmp_path / "test.txt"
        content = b"Test content"
        test_file.write_bytes(content)
        
        result = compute_file_hash(test_file, algorithm="md5")
        
        expected = hashlib.md5(content).hexdigest()
        assert result == expected
    
    def test_nonexistent_file_returns_none(self, tmp_path):
        """Test that non-existent file returns None."""
        test_file = tmp_path / "nonexistent.txt"
        
        result = compute_file_hash(test_file)
        
        assert result is None
    
    def test_unsupported_algorithm_raises(self, tmp_path):
        """Test that unsupported algorithm raises ValueError."""
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"test")
        
        with pytest.raises(ValueError, match="Unsupported hash algorithm"):
            compute_file_hash(test_file, algorithm="sha512")
    
    def test_large_file_streams_correctly(self, tmp_path):
        """Test that large files are hashed correctly with streaming."""
        test_file = tmp_path / "large.bin"
        # Create a file larger than the default chunk size
        content = b"x" * (DEFAULT_CHUNK_SIZE * 3 + 100)
        test_file.write_bytes(content)
        
        result = compute_file_hash(test_file)
        
        expected = hashlib.sha256(content).hexdigest()
        assert result == expected
    
    def test_custom_chunk_size(self, tmp_path):
        """Test hash computation with custom chunk size."""
        test_file = tmp_path / "test.txt"
        content = b"Test content for chunking"
        test_file.write_bytes(content)
        
        # Use very small chunk size
        result = compute_file_hash(test_file, chunk_size=5)
        
        expected = hashlib.sha256(content).hexdigest()
        assert result == expected


class TestCompareFileHashes:
    """Tests for compare_file_hashes function."""
    
    def test_identical_files_match(self, tmp_path):
        """Test that identical files have matching hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        content = b"Same content"
        file1.write_bytes(content)
        file2.write_bytes(content)
        
        match, hash1, hash2 = compare_file_hashes(file1, file2)
        
        assert match is True
        assert hash1 == hash2
        assert hash1 is not None
    
    def test_different_files_do_not_match(self, tmp_path):
        """Test that different files have different hashes."""
        file1 = tmp_path / "file1.txt"
        file2 = tmp_path / "file2.txt"
        file1.write_bytes(b"Content A")
        file2.write_bytes(b"Content B")
        
        match, hash1, hash2 = compare_file_hashes(file1, file2)
        
        assert match is False
        assert hash1 != hash2
    
    def test_missing_source_returns_none_hash(self, tmp_path):
        """Test that missing source returns None hash."""
        source = tmp_path / "missing.txt"
        dest = tmp_path / "dest.txt"
        dest.write_bytes(b"content")
        
        match, hash1, hash2 = compare_file_hashes(source, dest)
        
        assert match is False
        assert hash1 is None
        assert hash2 is not None
    
    def test_missing_dest_returns_none_hash(self, tmp_path):
        """Test that missing destination returns None hash."""
        source = tmp_path / "source.txt"
        dest = tmp_path / "missing.txt"
        source.write_bytes(b"content")
        
        match, hash1, hash2 = compare_file_hashes(source, dest)
        
        assert match is False
        assert hash1 is not None
        assert hash2 is None


class TestHashMatchesAny:
    """Tests for hash_matches_any function."""
    
    def test_finds_matching_file(self, tmp_path):
        """Test finding a matching file in candidates."""
        source = tmp_path / "source.txt"
        candidate1 = tmp_path / "candidate1.txt"
        candidate2 = tmp_path / "candidate2.txt"
        
        content = b"Matching content"
        source.write_bytes(content)
        candidate1.write_bytes(b"Different")
        candidate2.write_bytes(content)  # This one matches
        
        found, match_path, src_hash, dest_hash = hash_matches_any(
            source, [candidate1, candidate2]
        )
        
        assert found is True
        assert match_path == candidate2
        assert src_hash == dest_hash
    
    def test_no_match_returns_false(self, tmp_path):
        """Test when no candidate matches."""
        source = tmp_path / "source.txt"
        candidate1 = tmp_path / "candidate1.txt"
        candidate2 = tmp_path / "candidate2.txt"
        
        source.write_bytes(b"Source content")
        candidate1.write_bytes(b"Different 1")
        candidate2.write_bytes(b"Different 2")
        
        found, match_path, src_hash, dest_hash = hash_matches_any(
            source, [candidate1, candidate2]
        )
        
        assert found is False
        assert match_path is None
        assert src_hash is not None
        assert dest_hash is None
    
    def test_empty_candidates_returns_false(self, tmp_path):
        """Test with empty candidates list."""
        source = tmp_path / "source.txt"
        source.write_bytes(b"content")
        
        found, match_path, src_hash, dest_hash = hash_matches_any(source, [])
        
        assert found is False
        assert match_path is None
    
    def test_missing_source_returns_none(self, tmp_path):
        """Test with missing source file."""
        source = tmp_path / "missing.txt"
        candidate = tmp_path / "candidate.txt"
        candidate.write_bytes(b"content")
        
        found, match_path, src_hash, dest_hash = hash_matches_any(
            source, [candidate]
        )
        
        assert found is False
        assert src_hash is None
