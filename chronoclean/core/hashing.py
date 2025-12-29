"""Hash computation utilities for ChronoClean.

Provides streamed SHA-256 hashing to avoid loading large files into memory.
"""

import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default chunk size for streaming hash computation (64KB)
DEFAULT_CHUNK_SIZE = 65536


def compute_file_hash(
    file_path: Path,
    algorithm: str = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> Optional[str]:
    """Compute hash of a file using streamed reading.
    
    Args:
        file_path: Path to the file to hash.
        algorithm: Hash algorithm to use ('sha256', 'md5').
        chunk_size: Size of chunks to read at a time.
        
    Returns:
        Hexadecimal hash string, or None if file cannot be read.
        
    Raises:
        ValueError: If algorithm is not supported.
    """
    if algorithm not in ("sha256", "md5"):
        raise ValueError(f"Unsupported hash algorithm: {algorithm}. Use 'sha256' or 'md5'.")
    
    try:
        hasher = hashlib.new(algorithm)
        
        with open(file_path, "rb") as f:
            while chunk := f.read(chunk_size):
                hasher.update(chunk)
        
        return hasher.hexdigest()
    
    except FileNotFoundError:
        logger.debug(f"File not found for hashing: {file_path}")
        return None
    except PermissionError:
        logger.warning(f"Permission denied reading file for hash: {file_path}")
        return None
    except OSError as e:
        logger.warning(f"OS error hashing file {file_path}: {e}")
        return None


def compare_file_hashes(
    source_path: Path,
    destination_path: Path,
    algorithm: str = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> tuple[bool, Optional[str], Optional[str]]:
    """Compare hashes of two files.
    
    Args:
        source_path: Path to source file.
        destination_path: Path to destination file.
        algorithm: Hash algorithm to use.
        chunk_size: Size of chunks to read at a time.
        
    Returns:
        Tuple of (match: bool, source_hash: str|None, dest_hash: str|None).
        match is True if both hashes exist and are equal.
    """
    source_hash = compute_file_hash(source_path, algorithm, chunk_size)
    dest_hash = compute_file_hash(destination_path, algorithm, chunk_size)
    
    if source_hash is None or dest_hash is None:
        return (False, source_hash, dest_hash)
    
    return (source_hash == dest_hash, source_hash, dest_hash)


def hash_matches_any(
    source_path: Path,
    candidate_paths: list[Path],
    algorithm: str = "sha256",
    chunk_size: int = DEFAULT_CHUNK_SIZE,
) -> tuple[bool, Optional[Path], Optional[str], Optional[str]]:
    """Check if source hash matches any candidate file.
    
    Used for reconstruction mode where we search for matching content.
    
    Args:
        source_path: Path to source file.
        candidate_paths: List of candidate destination paths to check.
        algorithm: Hash algorithm to use.
        chunk_size: Size of chunks to read at a time.
        
    Returns:
        Tuple of (found: bool, matching_path: Path|None, source_hash: str|None, dest_hash: str|None).
    """
    source_hash = compute_file_hash(source_path, algorithm, chunk_size)
    
    if source_hash is None:
        return (False, None, None, None)
    
    for candidate in candidate_paths:
        candidate_hash = compute_file_hash(candidate, algorithm, chunk_size)
        if candidate_hash == source_hash:
            return (True, candidate, source_hash, candidate_hash)
    
    return (False, None, source_hash, None)
