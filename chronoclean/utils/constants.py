"""Constants for ChronoClean."""

# Version
VERSION = "0.3.1"

# Default file extensions
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

ALL_MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | RAW_EXTENSIONS

# Folder patterns to ignore
DEFAULT_IGNORE_FOLDERS = [
    "tosort", "unsorted", "misc", "backup", "temp", "tmp",
    "download", "downloads", "dcim", "camera", "pictures",
    "photos", "images", "100apple", "100andro", "camera roll",
    "new folder", "untitled", "unknown", "other", "various",
    "screenshot", "screenshots", "inbox", "import", "imported",
    "exports", "export", "shared", "public", "private",
]

# Default output folder name
DEFAULT_OUTPUT_FOLDER = ".chronoclean"

# Default folder structures
FOLDER_STRUCTURES = {
    "year": "YYYY",
    "year_month": "YYYY/MM",
    "year_month_day": "YYYY/MM/DD",
}

# Date format patterns
EXIF_DATE_FORMATS = [
    "%Y:%m:%d %H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y:%m:%d %H:%M",
    "%Y-%m-%d %H:%M",
]

# Filename patterns
DEFAULT_RENAME_PATTERN = "{date}_{time}"
DEFAULT_DATE_FORMAT = "%Y%m%d"
DEFAULT_TIME_FORMAT = "%H%M%S"
