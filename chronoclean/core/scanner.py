"""Directory scanner for ChronoClean."""

import logging
import time
from pathlib import Path
from typing import Iterator, Optional

from chronoclean.core.date_inference import DateInferenceEngine
from chronoclean.core.exif_reader import ExifReader
from chronoclean.core.folder_tagger import FolderTagger
from chronoclean.core.models import DateSource, FileRecord, FileType, ScanResult

logger = logging.getLogger(__name__)


class Scanner:
    """Scans directories and builds file records."""

    IMAGE_EXTENSIONS = {
        ".jpg", ".jpeg", ".png", ".tiff", ".tif",
        ".heic", ".heif", ".webp", ".bmp", ".gif"
    }
    VIDEO_EXTENSIONS = {
        ".mp4", ".mov", ".avi", ".mkv", ".m4v",
        ".3gp", ".wmv", ".webm", ".mts", ".m2ts"
    }
    RAW_EXTENSIONS = {
        ".cr2", ".cr3", ".nef", ".arw", ".dng",
        ".orf", ".rw2", ".raf", ".pef", ".srw"
    }

    def __init__(
        self,
        exif_reader: Optional[ExifReader] = None,
        date_engine: Optional[DateInferenceEngine] = None,
        folder_tagger: Optional[FolderTagger] = None,
        image_extensions: Optional[set[str]] = None,
        video_extensions: Optional[set[str]] = None,
        raw_extensions: Optional[set[str]] = None,
        include_videos: bool = True,
        include_raw: bool = True,
        recursive: bool = True,
        ignore_hidden: bool = True,
        date_mismatch_enabled: bool = True,
        date_mismatch_threshold_days: int = 1,
    ):
        """
        Initialize the scanner.

        Args:
            exif_reader: ExifReader instance
            date_engine: DateInferenceEngine instance
            folder_tagger: FolderTagger instance
            image_extensions: Custom image extensions to recognize
            video_extensions: Custom video extensions to recognize
            raw_extensions: Custom RAW extensions to recognize
            include_videos: Whether to include video files
            include_raw: Whether to include RAW files
            recursive: Whether to scan subdirectories
            ignore_hidden: Whether to skip hidden files/folders
            date_mismatch_enabled: Whether to detect date mismatches between filename and EXIF
            date_mismatch_threshold_days: Minimum difference in days to flag as mismatch
        """
        self.exif_reader = exif_reader or ExifReader()
        self.date_engine = date_engine or DateInferenceEngine(exif_reader=self.exif_reader)
        self.folder_tagger = folder_tagger or FolderTagger()

        self.image_extensions = image_extensions or self.IMAGE_EXTENSIONS
        self.video_extensions = video_extensions or self.VIDEO_EXTENSIONS
        self.raw_extensions = raw_extensions or self.RAW_EXTENSIONS

        self.include_videos = include_videos
        self.include_raw = include_raw
        self.recursive = recursive
        self.ignore_hidden = ignore_hidden
        self.date_mismatch_enabled = date_mismatch_enabled
        self.date_mismatch_threshold_days = date_mismatch_threshold_days

    @property
    def supported_extensions(self) -> set[str]:
        """Get all supported file extensions."""
        extensions = set(self.image_extensions)
        if self.include_videos:
            extensions |= self.video_extensions
        if self.include_raw:
            extensions |= self.raw_extensions
        return extensions

    def scan(
        self,
        source_path: Path,
        limit: Optional[int] = None,
    ) -> ScanResult:
        """
        Scan a directory and return results.

        Args:
            source_path: Directory to scan
            limit: Optional limit on number of files (for debugging)

        Returns:
            ScanResult with all file records
        """
        source_path = Path(source_path).resolve()

        if not source_path.exists():
            raise FileNotFoundError(f"Source path not found: {source_path}")

        if not source_path.is_dir():
            raise NotADirectoryError(f"Source path is not a directory: {source_path}")

        logger.info(f"Scanning {source_path}")
        start_time = time.time()

        result = ScanResult(source_root=source_path)
        folder_tags_seen: set[str] = set()
        file_count = 0

        for file_path in self._iter_files(source_path):
            result.total_files += 1

            # Check limit
            if limit and file_count >= limit:
                logger.info(f"Reached scan limit of {limit} files")
                break

            try:
                record = self._build_file_record(file_path)
                result.add_file(record)
                file_count += 1

                # Track folder tags
                if record.folder_tag:
                    folder_tags_seen.add(record.folder_tag)

                # v0.3: Track error categories from records
                if record.error_category:
                    result.increment_error_category(record.error_category)
                
                # v0.3: Track files with no date found
                if record.date_source == DateSource.UNKNOWN:
                    result.increment_error_category("no_date_found")
                
                # v0.2: Track date mismatches
                if record.date_mismatch:
                    result.increment_error_category("date_mismatch")

            except PermissionError as e:
                logger.error(f"Permission denied for {file_path}: {e}")
                result.add_error(file_path, str(e), category="file_access_error")
            except OSError as e:
                logger.error(f"OS error processing {file_path}: {e}")
                result.add_error(file_path, str(e), category="file_access_error")
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
                result.add_error(file_path, str(e))

        # Finalize result
        result.folder_tags_detected = sorted(folder_tags_seen)
        result.scan_duration_seconds = time.time() - start_time

        logger.info(
            f"Scan complete: {result.processed_files} files processed, "
            f"{result.error_files} errors, {result.skipped_files} skipped "
            f"in {result.scan_duration_seconds:.2f}s"
        )

        return result

    def _iter_files(self, source_path: Path) -> Iterator[Path]:
        """
        Iterate over files in directory (with filters applied).

        Args:
            source_path: Directory to scan

        Yields:
            Path objects for matching files
        """
        pattern = "**/*" if self.recursive else "*"

        for path in source_path.glob(pattern):
            # Skip directories
            if path.is_dir():
                continue

            # Skip hidden files/folders
            if self.ignore_hidden:
                if any(part.startswith(".") for part in path.parts):
                    continue

            # Check extension
            ext = path.suffix.lower()
            if ext not in self.supported_extensions:
                continue

            yield path

    def _classify_file_type(self, path: Path) -> FileType:
        """
        Determine if file is image, video, raw, or unknown.

        Args:
            path: Path to file

        Returns:
            FileType enum value
        """
        ext = path.suffix.lower()

        if ext in self.image_extensions:
            return FileType.IMAGE
        elif ext in self.video_extensions:
            return FileType.VIDEO
        elif ext in self.raw_extensions:
            return FileType.RAW
        else:
            return FileType.UNKNOWN

    def _build_file_record(self, file_path: Path) -> FileRecord:
        """
        Build a FileRecord for a single file.

        Args:
            file_path: Path to the file

        Returns:
            FileRecord with all available information
        """
        # Basic info
        file_type = self._classify_file_type(file_path)
        size_bytes = file_path.stat().st_size

        # Create record
        record = FileRecord(
            source_path=file_path,
            file_type=file_type,
            size_bytes=size_bytes,
            source_folder_name=file_path.parent.name,
        )

        # Get date (pass file_type to route to correct metadata reader)
        detected_date, date_source = self.date_engine.infer_date(file_path, file_type)
        record.detected_date = detected_date
        record.date_source = date_source
        record.has_exif = date_source == DateSource.EXIF
        
        # v0.3: Set error category for files without dates
        if date_source == DateSource.UNKNOWN:
            if file_type == FileType.VIDEO:
                record.error_category = "no_video_metadata"
            elif file_type in (FileType.IMAGE, FileType.RAW):
                record.error_category = "no_exif_date"
            else:
                record.error_category = "no_date_found"

        # v0.3: Extract video metadata date for video files
        if file_type == FileType.VIDEO:
            video_date = self.date_engine.get_video_metadata_date(file_path)
            if video_date:
                record.video_metadata_date = video_date

        # v0.2: Extract filename date (always extract for comparison)
        filename_date = self.date_engine.get_filename_date(file_path)
        if filename_date:
            record.filename_date = filename_date
            
            # Check for date mismatch if enabled and we have both dates
            if self.date_mismatch_enabled and detected_date and filename_date:
                # Calculate the difference in days
                delta = abs((detected_date - filename_date).days)
                if delta >= self.date_mismatch_threshold_days:
                    record.date_mismatch = True
                    record.date_mismatch_days = delta

        # Get folder tag
        tag = self.folder_tagger.extract_tag(file_path)
        if tag:
            record.folder_tag = tag
            record.folder_tag_usable = not self.folder_tagger.is_tag_in_filename(
                file_path.name, tag
            )

        return record


def scan_directory(
    source_path: Path,
    recursive: bool = True,
    include_videos: bool = True,
    limit: Optional[int] = None,
) -> ScanResult:
    """
    Convenience function to scan a directory.

    Args:
        source_path: Directory to scan
        recursive: Whether to scan subdirectories
        include_videos: Whether to include video files
        limit: Optional file limit

    Returns:
        ScanResult with all file records
    """
    scanner = Scanner(
        recursive=recursive,
        include_videos=include_videos,
    )
    return scanner.scan(source_path, limit=limit)
