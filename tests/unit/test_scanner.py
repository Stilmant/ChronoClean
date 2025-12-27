"""Unit tests for chronoclean.core.scanner."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from chronoclean.core.models import DateSource, FileType, ScanResult
from chronoclean.core.scanner import Scanner, scan_directory


class TestScannerInit:
    """Tests for Scanner initialization."""

    def test_default_init(self):
        scanner = Scanner()

        assert scanner.exif_reader is not None
        assert scanner.date_engine is not None
        assert scanner.folder_tagger is not None
        assert scanner.recursive is True
        assert scanner.ignore_hidden is True
        assert scanner.include_videos is True
        assert scanner.include_raw is True

    def test_custom_extensions(self):
        custom_images = {".jpg", ".png"}
        scanner = Scanner(image_extensions=custom_images)

        assert scanner.image_extensions == custom_images

    def test_disable_videos(self):
        scanner = Scanner(include_videos=False)

        assert scanner.include_videos is False
        assert ".mp4" not in scanner.supported_extensions

    def test_disable_raw(self):
        scanner = Scanner(include_raw=False)

        assert scanner.include_raw is False
        assert ".cr2" not in scanner.supported_extensions


class TestSupportedExtensions:
    """Tests for supported_extensions property."""

    def test_includes_images(self):
        scanner = Scanner()

        assert ".jpg" in scanner.supported_extensions
        assert ".jpeg" in scanner.supported_extensions
        assert ".png" in scanner.supported_extensions
        assert ".heic" in scanner.supported_extensions

    def test_includes_videos_when_enabled(self):
        scanner = Scanner(include_videos=True)

        assert ".mp4" in scanner.supported_extensions
        assert ".mov" in scanner.supported_extensions

    def test_excludes_videos_when_disabled(self):
        scanner = Scanner(include_videos=False)

        assert ".mp4" not in scanner.supported_extensions
        assert ".mov" not in scanner.supported_extensions

    def test_includes_raw_when_enabled(self):
        scanner = Scanner(include_raw=True)

        assert ".cr2" in scanner.supported_extensions
        assert ".nef" in scanner.supported_extensions

    def test_excludes_raw_when_disabled(self):
        scanner = Scanner(include_raw=False)

        assert ".cr2" not in scanner.supported_extensions
        assert ".nef" not in scanner.supported_extensions


class TestClassifyFileType:
    """Tests for _classify_file_type method."""

    def test_image_files(self):
        scanner = Scanner()

        assert scanner._classify_file_type(Path("photo.jpg")) == FileType.IMAGE
        assert scanner._classify_file_type(Path("photo.jpeg")) == FileType.IMAGE
        assert scanner._classify_file_type(Path("photo.png")) == FileType.IMAGE
        assert scanner._classify_file_type(Path("photo.heic")) == FileType.IMAGE

    def test_video_files(self):
        scanner = Scanner()

        assert scanner._classify_file_type(Path("video.mp4")) == FileType.VIDEO
        assert scanner._classify_file_type(Path("video.mov")) == FileType.VIDEO
        assert scanner._classify_file_type(Path("video.avi")) == FileType.VIDEO

    def test_raw_files(self):
        scanner = Scanner()

        assert scanner._classify_file_type(Path("photo.cr2")) == FileType.RAW
        assert scanner._classify_file_type(Path("photo.nef")) == FileType.RAW
        assert scanner._classify_file_type(Path("photo.arw")) == FileType.RAW

    def test_unknown_files(self):
        scanner = Scanner()

        assert scanner._classify_file_type(Path("document.txt")) == FileType.UNKNOWN
        assert scanner._classify_file_type(Path("file.xyz")) == FileType.UNKNOWN

    def test_case_insensitive(self):
        scanner = Scanner()

        assert scanner._classify_file_type(Path("photo.JPG")) == FileType.IMAGE
        assert scanner._classify_file_type(Path("photo.HEIC")) == FileType.IMAGE
        assert scanner._classify_file_type(Path("video.MOV")) == FileType.VIDEO


class TestIterFiles:
    """Tests for _iter_files method."""

    def test_finds_image_files(self, temp_dir: Path):
        (temp_dir / "photo1.jpg").write_bytes(b"test")
        (temp_dir / "photo2.png").write_bytes(b"test")

        scanner = Scanner()
        files = list(scanner._iter_files(temp_dir))

        assert len(files) == 2
        names = {f.name for f in files}
        assert "photo1.jpg" in names
        assert "photo2.png" in names

    def test_skips_unsupported_extensions(self, temp_dir: Path):
        (temp_dir / "photo.jpg").write_bytes(b"test")
        (temp_dir / "document.txt").write_bytes(b"test")
        (temp_dir / "data.csv").write_bytes(b"test")

        scanner = Scanner()
        files = list(scanner._iter_files(temp_dir))

        assert len(files) == 1
        assert files[0].name == "photo.jpg"

    def test_recursive_scanning(self, temp_dir: Path):
        (temp_dir / "photo.jpg").write_bytes(b"test")
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.jpg").write_bytes(b"test")

        scanner = Scanner(recursive=True)
        files = list(scanner._iter_files(temp_dir))

        assert len(files) == 2

    def test_non_recursive_scanning(self, temp_dir: Path):
        (temp_dir / "photo.jpg").write_bytes(b"test")
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.jpg").write_bytes(b"test")

        scanner = Scanner(recursive=False)
        files = list(scanner._iter_files(temp_dir))

        assert len(files) == 1
        assert files[0].name == "photo.jpg"

    def test_skips_hidden_files(self, temp_dir: Path):
        (temp_dir / "visible.jpg").write_bytes(b"test")
        (temp_dir / ".hidden.jpg").write_bytes(b"test")

        scanner = Scanner(ignore_hidden=True)
        files = list(scanner._iter_files(temp_dir))

        assert len(files) == 1
        assert files[0].name == "visible.jpg"

    def test_includes_hidden_files_when_allowed(self, temp_dir: Path):
        (temp_dir / "visible.jpg").write_bytes(b"test")
        (temp_dir / ".hidden.jpg").write_bytes(b"test")

        scanner = Scanner(ignore_hidden=False)
        files = list(scanner._iter_files(temp_dir))

        assert len(files) == 2

    def test_skips_hidden_directories(self, temp_dir: Path):
        (temp_dir / "photo.jpg").write_bytes(b"test")
        hidden_dir = temp_dir / ".hidden"
        hidden_dir.mkdir()
        (hidden_dir / "nested.jpg").write_bytes(b"test")

        scanner = Scanner(ignore_hidden=True, recursive=True)
        files = list(scanner._iter_files(temp_dir))

        assert len(files) == 1
        assert files[0].name == "photo.jpg"

    def test_skips_directories_themselves(self, temp_dir: Path):
        (temp_dir / "photo.jpg").write_bytes(b"test")
        subdir = temp_dir / "subdir"
        subdir.mkdir()

        scanner = Scanner(recursive=False)
        files = list(scanner._iter_files(temp_dir))

        # Should only get the file, not the directory
        assert len(files) == 1
        assert all(f.is_file() for f in files)


class TestScan:
    """Tests for scan method."""

    def test_scan_empty_directory(self, temp_dir: Path):
        scanner = Scanner()
        result = scanner.scan(temp_dir)

        assert isinstance(result, ScanResult)
        assert result.source_root == temp_dir
        assert result.processed_files == 0

    def test_scan_with_files(self, temp_dir: Path):
        (temp_dir / "photo1.jpg").write_bytes(b"test content")
        (temp_dir / "photo2.jpg").write_bytes(b"test content")

        scanner = Scanner()
        result = scanner.scan(temp_dir)

        assert result.processed_files == 2
        assert len(result.files) == 2

    def test_scan_nonexistent_directory(self, temp_dir: Path):
        scanner = Scanner()

        with pytest.raises(FileNotFoundError):
            scanner.scan(temp_dir / "nonexistent")

    def test_scan_file_instead_of_directory(self, temp_dir: Path):
        file_path = temp_dir / "file.txt"
        file_path.write_text("test")

        scanner = Scanner()

        with pytest.raises(NotADirectoryError):
            scanner.scan(file_path)

    def test_scan_with_limit(self, temp_dir: Path):
        for i in range(10):
            (temp_dir / f"photo{i}.jpg").write_bytes(b"test")

        scanner = Scanner()
        result = scanner.scan(temp_dir, limit=3)

        assert result.processed_files == 3

    def test_scan_result_has_duration(self, temp_dir: Path):
        (temp_dir / "photo.jpg").write_bytes(b"test")

        scanner = Scanner()
        result = scanner.scan(temp_dir)

        assert result.scan_duration_seconds >= 0

    def test_scan_tracks_folder_tags(self, temp_dir: Path):
        event_dir = temp_dir / "Paris 2024"
        event_dir.mkdir()
        (event_dir / "photo.jpg").write_bytes(b"test")

        scanner = Scanner()
        result = scanner.scan(temp_dir)

        assert "Paris_2024" in result.folder_tags_detected


class TestBuildFileRecord:
    """Tests for _build_file_record method."""

    def test_builds_basic_record(self, temp_dir: Path):
        photo = temp_dir / "photo.jpg"
        photo.write_bytes(b"test content here")

        scanner = Scanner()
        record = scanner._build_file_record(photo)

        assert record.source_path == photo
        assert record.file_type == FileType.IMAGE
        assert record.size_bytes == len(b"test content here")
        assert record.source_folder_name == temp_dir.name

    def test_record_has_date(self, temp_dir: Path):
        photo = temp_dir / "photo.jpg"
        photo.write_bytes(b"test")

        scanner = Scanner()
        record = scanner._build_file_record(photo)

        # Should have a date (from filesystem if no EXIF)
        assert record.detected_date is not None
        assert record.date_source in DateSource

    def test_record_folder_tag(self, temp_dir: Path):
        event_dir = temp_dir / "Wedding"
        event_dir.mkdir()
        photo = event_dir / "photo.jpg"
        photo.write_bytes(b"test")

        scanner = Scanner()
        record = scanner._build_file_record(photo)

        assert record.folder_tag == "Wedding"


class TestScanDirectoryFunction:
    """Tests for scan_directory convenience function."""

    def test_basic_scan(self, temp_dir: Path):
        (temp_dir / "photo.jpg").write_bytes(b"test")

        result = scan_directory(temp_dir)

        assert isinstance(result, ScanResult)
        assert result.processed_files == 1

    def test_with_options(self, temp_dir: Path):
        (temp_dir / "photo.jpg").write_bytes(b"test")
        (temp_dir / "video.mp4").write_bytes(b"test")

        result = scan_directory(temp_dir, include_videos=False)

        # Should only include photo, not video
        assert result.processed_files == 1

    def test_non_recursive(self, temp_dir: Path):
        (temp_dir / "photo.jpg").write_bytes(b"test")
        subdir = temp_dir / "subdir"
        subdir.mkdir()
        (subdir / "nested.jpg").write_bytes(b"test")

        result = scan_directory(temp_dir, recursive=False)

        assert result.processed_files == 1


class TestScannerWithMocks:
    """Tests using mocked dependencies."""

    def test_uses_provided_exif_reader(self, temp_dir: Path):
        mock_reader = MagicMock()
        mock_reader.read.return_value = MagicMock(
            date_original=datetime(2024, 3, 15, 14, 30, 45),
            make="Canon",
            model="EOS R5"
        )
        mock_reader.get_date.return_value = datetime(2024, 3, 15, 14, 30, 45)

        photo = temp_dir / "photo.jpg"
        photo.write_bytes(b"test")

        scanner = Scanner(exif_reader=mock_reader)
        scanner.scan(temp_dir)

        # Verify our mock was used (via the date engine)
        # The date engine will call the exif reader

    def test_handles_file_processing_error(self, temp_dir: Path):
        photo = temp_dir / "photo.jpg"
        photo.write_bytes(b"test")

        scanner = Scanner()

        # Mock _build_file_record to raise an exception
        original_build = scanner._build_file_record
        call_count = [0]

        def failing_build(path):
            call_count[0] += 1
            raise ValueError("Test error")

        scanner._build_file_record = failing_build
        result = scanner.scan(temp_dir)

        assert result.error_files == 1
        assert len(result.errors) == 1


class TestExtensionSets:
    """Tests for extension constants."""

    def test_image_extensions(self):
        expected = {
            ".jpg", ".jpeg", ".png", ".tiff", ".tif",
            ".heic", ".heif", ".webp", ".bmp", ".gif"
        }
        assert Scanner.IMAGE_EXTENSIONS == expected

    def test_video_extensions(self):
        expected = {
            ".mp4", ".mov", ".avi", ".mkv", ".m4v",
            ".3gp", ".wmv", ".webm", ".mts", ".m2ts"
        }
        assert Scanner.VIDEO_EXTENSIONS == expected

    def test_raw_extensions(self):
        expected = {
            ".cr2", ".cr3", ".nef", ".arw", ".dng",
            ".orf", ".rw2", ".raf", ".pef", ".srw"
        }
        assert Scanner.RAW_EXTENSIONS == expected
