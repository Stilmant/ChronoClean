"""Configuration loading and validation for ChronoClean."""

import logging
from pathlib import Path
from typing import Any, Optional

import yaml

from chronoclean.config.schema import (
    ChronoCleanConfig,
    DateMismatchConfig,
    DryRunConfig,
    DuplicatesConfig,
    ExportConfig,
    FilenameDateConfig,
    FolderTagsConfig,
    GeneralConfig,
    HeuristicConfig,
    LoggingConfig,
    PathsConfig,
    PerformanceConfig,
    RenamingConfig,
    ScanConfig,
    SortingConfig,
    SynologyConfig,
    VerifyConfig,
    VideoMetadataConfig,
)

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configuration error."""

    pass


class ConfigLoader:
    """Loads configuration from YAML files."""

    DEFAULT_CONFIG_PATHS = [
        Path("chronoclean.yaml"),
        Path("chronoclean.yml"),
        Path(".chronoclean/config.yaml"),
        Path(".chronoclean/config.yml"),
    ]

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> ChronoCleanConfig:
        """
        Load configuration.

        Priority:
        1. Explicit config_path argument
        2. Default config paths (first found)
        3. Built-in defaults

        Args:
            config_path: Optional explicit path to config file

        Returns:
            ChronoCleanConfig object

        Raises:
            ConfigError: If config file cannot be read or parsed
        """
        config_dict: dict[str, Any] = {}

        # Try to load config file
        if config_path:
            if not config_path.exists():
                raise ConfigError(f"Config file not found: {config_path}")
            config_dict = cls._load_yaml(config_path)
        else:
            # Search default paths
            for default_path in cls.DEFAULT_CONFIG_PATHS:
                if default_path.exists():
                    logger.info(f"Loading config from {default_path}")
                    config_dict = cls._load_yaml(default_path)
                    break

        # Build config object with defaults
        return cls._build_config(config_dict)

    @classmethod
    def _load_yaml(cls, path: Path) -> dict[str, Any]:
        """Load YAML file and return dict."""
        try:
            with open(path, encoding="utf-8") as f:
                data = yaml.safe_load(f)
                return data if data else {}
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in {path}: {e}")
        except OSError as e:
            raise ConfigError(f"Cannot read {path}: {e}")

    @classmethod
    def _build_config(cls, data: dict[str, Any]) -> ChronoCleanConfig:
        """Build ChronoCleanConfig from dictionary."""
        return ChronoCleanConfig(
            version=data.get("version", "1.0"),
            general=cls._build_general(data.get("general", {})),
            paths=cls._build_paths(data.get("paths", {})),
            scan=cls._build_scan(data.get("scan", {})),
            sorting=cls._build_sorting(data.get("sorting", {})),
            heuristic=cls._build_heuristic(data.get("heuristic", {})),
            folder_tags=cls._build_folder_tags(data.get("folder_tags", {})),
            renaming=cls._build_renaming(data.get("renaming", {})),
            duplicates=cls._build_duplicates(data.get("duplicates", {})),
            # v0.2 additions
            filename_date=cls._build_filename_date(data.get("filename_date", {})),
            date_mismatch=cls._build_date_mismatch(data.get("date_mismatch", {})),
            export=cls._build_export(data.get("export", {})),
            # v0.3 additions
            video_metadata=cls._build_video_metadata(data.get("video_metadata", {})),
            # v0.3.1 additions
            verify=cls._build_verify(data.get("verify", {})),
            # Display and system
            dry_run=cls._build_dry_run(data.get("dry_run", {})),
            logging=cls._build_logging(data.get("logging", {})),
            performance=cls._build_performance(data.get("performance", {})),
            synology=cls._build_synology(data.get("synology", {})),
        )

    @classmethod
    def _build_general(cls, data: dict[str, Any]) -> GeneralConfig:
        """Build GeneralConfig from dictionary."""
        config = GeneralConfig()
        if "timezone" in data:
            config.timezone = data["timezone"]
        if "recursive" in data:
            config.recursive = bool(data["recursive"])
        if "include_videos" in data:
            config.include_videos = bool(data["include_videos"])
        if "ignore_hidden_files" in data:
            config.ignore_hidden_files = bool(data["ignore_hidden_files"])
        if "dry_run_default" in data:
            config.dry_run_default = bool(data["dry_run_default"])
        if "output_folder" in data:
            config.output_folder = data["output_folder"]
        return config

    @classmethod
    def _build_paths(cls, data: dict[str, Any]) -> PathsConfig:
        """Build PathsConfig from dictionary."""
        config = PathsConfig()
        if "source" in data and data["source"]:
            config.source = Path(data["source"])
        if "destination" in data and data["destination"]:
            config.destination = Path(data["destination"])
        if "temp_folder" in data and data["temp_folder"]:
            config.temp_folder = Path(data["temp_folder"])
        return config

    @classmethod
    def _build_scan(cls, data: dict[str, Any]) -> ScanConfig:
        """Build ScanConfig from dictionary."""
        config = ScanConfig()
        if "image_extensions" in data:
            config.image_extensions = list(data["image_extensions"])
        if "video_extensions" in data:
            config.video_extensions = list(data["video_extensions"])
        if "raw_extensions" in data:
            config.raw_extensions = list(data["raw_extensions"])
        if "skip_exif_errors" in data:
            config.skip_exif_errors = bool(data["skip_exif_errors"])
        if "limit" in data:
            config.limit = int(data["limit"]) if data["limit"] else None
        return config

    @classmethod
    def _build_sorting(cls, data: dict[str, Any]) -> SortingConfig:
        """Build SortingConfig from dictionary."""
        config = SortingConfig()
        if "folder_structure" in data:
            config.folder_structure = data["folder_structure"]
            # Determine include_day from structure
            config.include_day = "DD" in config.folder_structure
        if "fallback_date_priority" in data:
            config.fallback_date_priority = list(data["fallback_date_priority"])
        return config

    @classmethod
    def _build_heuristic(cls, data: dict[str, Any]) -> HeuristicConfig:
        """Build HeuristicConfig from dictionary."""
        config = HeuristicConfig()
        if "enabled" in data:
            config.enabled = bool(data["enabled"])
        if "max_days_from_cluster" in data:
            config.max_days_from_cluster = int(data["max_days_from_cluster"])
        # v0.3: min_cluster_size
        if "min_cluster_size" in data:
            config.min_cluster_size = int(data["min_cluster_size"])
        return config

    @classmethod
    def _build_folder_tags(cls, data: dict[str, Any]) -> FolderTagsConfig:
        """Build FolderTagsConfig from dictionary."""
        config = FolderTagsConfig()
        if "enabled" in data:
            config.enabled = bool(data["enabled"])
        if "tag_format" in data:
            config.tag_format = data["tag_format"]
        if "min_length" in data:
            config.min_length = int(data["min_length"])
        if "max_length" in data:
            config.max_length = int(data["max_length"])
        if "ignore_list" in data:
            config.ignore_list = list(data["ignore_list"])
        if "force_list" in data:
            config.force_list = list(data["force_list"])
        if "auto_detect" in data:
            config.auto_detect = bool(data["auto_detect"])
        if "distance_check" in data:
            config.distance_check = bool(data["distance_check"])
        if "distance_threshold" in data:
            config.distance_threshold = float(data["distance_threshold"])
        return config

    @classmethod
    def _build_renaming(cls, data: dict[str, Any]) -> RenamingConfig:
        """Build RenamingConfig from dictionary."""
        config = RenamingConfig()
        if "enabled" in data:
            config.enabled = bool(data["enabled"])
        if "pattern" in data:
            config.pattern = data["pattern"]
        if "date_format" in data:
            config.date_format = data["date_format"]
        if "time_format" in data:
            config.time_format = data["time_format"]
        if "lowercase_extensions" in data:
            config.lowercase_extensions = bool(data["lowercase_extensions"])
        if "keep_original_if_conflict" in data:
            config.keep_original_if_conflict = bool(data["keep_original_if_conflict"])
        return config

    @classmethod
    def _build_duplicates(cls, data: dict[str, Any]) -> DuplicatesConfig:
        """Build DuplicatesConfig from dictionary."""
        config = DuplicatesConfig()
        if "enabled" in data:
            config.enabled = bool(data["enabled"])
        if "policy" in data:
            config.policy = data["policy"]
        if "hashing_algorithm" in data:
            config.hashing_algorithm = data["hashing_algorithm"]
        if "on_collision" in data:
            config.on_collision = data["on_collision"]
        if "consider_resolution" in data:
            config.consider_resolution = bool(data["consider_resolution"])
        if "consider_metadata" in data:
            config.consider_metadata = bool(data["consider_metadata"])
        if "cache_hashes" in data:
            config.cache_hashes = bool(data["cache_hashes"])
        return config

    @classmethod
    def _build_filename_date(cls, data: dict[str, Any]) -> FilenameDateConfig:
        """Build FilenameDateConfig from dictionary (v0.2)."""
        config = FilenameDateConfig()
        if "enabled" in data:
            config.enabled = bool(data["enabled"])
        if "patterns" in data:
            config.patterns = list(data["patterns"])
        if "year_cutoff" in data:
            config.year_cutoff = int(data["year_cutoff"])
        if "priority" in data:
            config.priority = data["priority"]
        return config

    @classmethod
    def _build_date_mismatch(cls, data: dict[str, Any]) -> DateMismatchConfig:
        """Build DateMismatchConfig from dictionary (v0.2)."""
        config = DateMismatchConfig()
        if "enabled" in data:
            config.enabled = bool(data["enabled"])
        if "threshold_days" in data:
            config.threshold_days = int(data["threshold_days"])
        if "warn_on_scan" in data:
            config.warn_on_scan = bool(data["warn_on_scan"])
        if "include_in_export" in data:
            config.include_in_export = bool(data["include_in_export"])
        return config

    @classmethod
    def _build_export(cls, data: dict[str, Any]) -> ExportConfig:
        """Build ExportConfig from dictionary (v0.2)."""
        config = ExportConfig()
        if "default_format" in data:
            config.default_format = data["default_format"]
        if "include_statistics" in data:
            config.include_statistics = bool(data["include_statistics"])
        if "include_folder_tags" in data:
            config.include_folder_tags = bool(data["include_folder_tags"])
        if "pretty_print" in data:
            config.pretty_print = bool(data["pretty_print"])
        if "output_path" in data:
            config.output_path = data["output_path"]
        return config

    @classmethod
    def _build_video_metadata(cls, data: dict[str, Any]) -> VideoMetadataConfig:
        """Build VideoMetadataConfig from dictionary (v0.3)."""
        config = VideoMetadataConfig()
        if "enabled" in data:
            config.enabled = bool(data["enabled"])
        if "provider" in data:
            config.provider = data["provider"]
        if "ffprobe_path" in data:
            config.ffprobe_path = data["ffprobe_path"]
        if "fallback_to_hachoir" in data:
            config.fallback_to_hachoir = bool(data["fallback_to_hachoir"])
        if "skip_errors" in data:
            config.skip_errors = bool(data["skip_errors"])
        return config

    @classmethod
    def _build_verify(cls, data: dict[str, Any]) -> VerifyConfig:
        """Build VerifyConfig from dictionary (v0.3.1)."""
        config = VerifyConfig()
        if "enabled" in data:
            config.enabled = bool(data["enabled"])
        if "algorithm" in data:
            config.algorithm = data["algorithm"]
        if "state_dir" in data:
            config.state_dir = data["state_dir"]
        if "run_record_dir" in data:
            config.run_record_dir = data["run_record_dir"]
        if "verification_dir" in data:
            config.verification_dir = data["verification_dir"]
        if "allow_cleanup_on_quick" in data:
            config.allow_cleanup_on_quick = bool(data["allow_cleanup_on_quick"])
        if "content_search_on_reconstruct" in data:
            config.content_search_on_reconstruct = bool(data["content_search_on_reconstruct"])
        if "write_run_record" in data:
            config.write_run_record = bool(data["write_run_record"])
        return config

    @classmethod
    def _build_dry_run(cls, data: dict[str, Any]) -> DryRunConfig:
        """Build DryRunConfig from dictionary."""
        config = DryRunConfig()
        if "show_moves" in data:
            config.show_moves = bool(data["show_moves"])
        if "show_renames" in data:
            config.show_renames = bool(data["show_renames"])
        if "show_tags" in data:
            config.show_tags = bool(data["show_tags"])
        if "show_duplicates" in data:
            config.show_duplicates = bool(data["show_duplicates"])
        if "summary_only" in data:
            config.summary_only = bool(data["summary_only"])
        return config

    @classmethod
    def _build_logging(cls, data: dict[str, Any]) -> LoggingConfig:
        """Build LoggingConfig from dictionary."""
        config = LoggingConfig()
        if "level" in data:
            config.level = data["level"]
        if "color_output" in data:
            config.color_output = bool(data["color_output"])
        if "log_to_file" in data:
            config.log_to_file = bool(data["log_to_file"])
        if "file_path" in data:
            config.file_path = data["file_path"]
        return config

    @classmethod
    def _build_performance(cls, data: dict[str, Any]) -> PerformanceConfig:
        """Build PerformanceConfig from dictionary."""
        config = PerformanceConfig()
        if "multiprocessing" in data:
            config.multiprocessing = bool(data["multiprocessing"])
        if "max_workers" in data:
            config.max_workers = int(data["max_workers"])
        if "chunk_size" in data:
            config.chunk_size = int(data["chunk_size"])
        if "enable_cache" in data:
            config.enable_cache = bool(data["enable_cache"])
        if "cache_location" in data:
            config.cache_location = data["cache_location"]
        return config

    @classmethod
    def _build_synology(cls, data: dict[str, Any]) -> SynologyConfig:
        """Build SynologyConfig from dictionary."""
        config = SynologyConfig()
        if "safe_fs_mode" in data:
            config.safe_fs_mode = bool(data["safe_fs_mode"])
        if "use_long_paths" in data:
            config.use_long_paths = bool(data["use_long_paths"])
        if "min_free_space_mb" in data:
            config.min_free_space_mb = int(data["min_free_space_mb"])
        return config

    @classmethod
    def validate(cls, config: ChronoCleanConfig) -> list[str]:
        """
        Validate configuration and return list of errors.

        Args:
            config: Configuration to validate

        Returns:
            List of error messages (empty if valid)
        """
        errors: list[str] = []

        # Validate sorting structure
        valid_structures = ["YYYY/MM", "YYYY/MM/DD", "YYYY"]
        if config.sorting.folder_structure not in valid_structures:
            errors.append(
                f"Invalid folder_structure: {config.sorting.folder_structure}. "
                f"Must be one of: {valid_structures}"
            )

        # Validate fallback priority
        valid_sources = ["exif", "video_metadata", "filesystem", "folder_name", "filename", "heuristic"]
        for source in config.sorting.fallback_date_priority:
            if source not in valid_sources:
                errors.append(f"Invalid fallback source: {source}")

        # Validate logging level
        valid_levels = ["debug", "info", "warning", "error", "critical"]
        if config.logging.level.lower() not in valid_levels:
            errors.append(f"Invalid logging level: {config.logging.level}")

        # Validate duplicates policy
        valid_policies = ["safe", "skip", "overwrite"]
        if config.duplicates.policy not in valid_policies:
            errors.append(f"Invalid duplicates policy: {config.duplicates.policy}")

        # Validate thresholds
        if not 0 <= config.folder_tags.distance_threshold <= 1:
            errors.append("distance_threshold must be between 0 and 1")

        if config.folder_tags.min_length < 1:
            errors.append("min_length must be at least 1")

        if config.folder_tags.max_length < config.folder_tags.min_length:
            errors.append("max_length must be >= min_length")

        return errors
