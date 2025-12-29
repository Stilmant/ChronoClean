"""Export functionality for scan results (v0.2).

This module provides JSON and CSV export capabilities for scan results.
"""

import csv
import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any

from chronoclean.core.models import ScanResult, FileRecord, DateSource


class Exporter:
    """Exports scan results to various formats."""

    def __init__(
        self,
        include_statistics: bool = True,
        pretty_print: bool = True,
    ):
        """Initialize exporter.

        Args:
            include_statistics: Include summary statistics in export.
            pretty_print: Format JSON output with indentation.
        """
        self.include_statistics = include_statistics
        self.pretty_print = pretty_print

    def to_json(
        self,
        scan_result: ScanResult,
        output_path: Path | None = None,
    ) -> str:
        """Export scan result to JSON.

        Args:
            scan_result: The scan result to export.
            output_path: Optional path to write JSON file.

        Returns:
            JSON string representation.
        """
        data = self._prepare_export_data(scan_result)

        indent = 2 if self.pretty_print else None
        json_str = json.dumps(data, indent=indent, default=self._json_serializer)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json_str, encoding="utf-8")

        return json_str

    def to_csv(
        self,
        scan_result: ScanResult,
        output_path: Path | None = None,
    ) -> str:
        """Export scan result to CSV.

        Args:
            scan_result: The scan result to export.
            output_path: Optional path to write CSV file.

        Returns:
            CSV string representation.
        """
        import io

        output = io.StringIO()
        writer = csv.writer(output)

        # Write header
        headers = self._get_csv_headers()
        writer.writerow(headers)

        # Write file records
        for record in scan_result.files:
            row = self._record_to_csv_row(record)
            writer.writerow(row)

        csv_str = output.getvalue()

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(csv_str, encoding="utf-8", newline="")

        return csv_str

    def to_dict(self, scan_result: ScanResult) -> dict[str, Any]:
        """Convert scan result to dictionary.

        Args:
            scan_result: The scan result to convert.

        Returns:
            Dictionary representation.
        """
        return self._prepare_export_data(scan_result)

    def _prepare_export_data(self, scan_result: ScanResult) -> dict[str, Any]:
        """Prepare scan result data for export.

        Args:
            scan_result: The scan result to prepare.

        Returns:
            Dictionary ready for serialization.
        """
        data: dict[str, Any] = {
            "export_timestamp": datetime.now().isoformat(),
            "source_directory": str(scan_result.source_root),
            "file_count": len(scan_result.files),
            "files": [self._record_to_dict(r) for r in scan_result.files],
        }

        if self.include_statistics:
            data["statistics"] = self._compute_statistics(scan_result)

        return data

    def _record_to_dict(self, record: FileRecord) -> dict[str, Any]:
        """Convert a FileRecord to a dictionary.

        Args:
            record: The file record to convert.

        Returns:
            Dictionary representation of the record.
        """
        # Extract year and month from detected_date if available
        year = None
        month = None
        if record.detected_date:
            year = str(record.detected_date.year)
            month = f"{record.detected_date.month:02d}"
        
        return {
            "path": str(record.source_path),
            "filename": record.source_path.name,
            "size_bytes": record.size_bytes,
            "extension": record.extension,
            "date_taken": record.detected_date.isoformat() if record.detected_date else None,
            "date_source": record.date_source.value if record.date_source else None,
            "year": year,
            "month": month,
            "target_path": str(record.destination_path) if record.destination_path else None,
            "filename_date": record.filename_date.isoformat() if record.filename_date else None,
            "date_mismatch": record.date_mismatch,
            "date_mismatch_days": record.date_mismatch_days,
            # v0.3: Video metadata and error category
            "video_metadata_date": record.video_metadata_date.isoformat() if record.video_metadata_date else None,
            "error_category": record.error_category,
            "file_hash": record.file_hash,
            "is_duplicate": record.is_duplicate,
            "duplicate_of": str(record.duplicate_of) if record.duplicate_of else None,
        }

    def _record_to_csv_row(self, record: FileRecord) -> list[Any]:
        """Convert a FileRecord to a CSV row.

        Args:
            record: The file record to convert.

        Returns:
            List of values for CSV row.
        """
        # Extract year and month from detected_date if available
        year = ""
        month = ""
        if record.detected_date:
            year = str(record.detected_date.year)
            month = f"{record.detected_date.month:02d}"
        
        return [
            str(record.source_path),
            record.source_path.name,
            record.size_bytes,
            record.extension,
            record.detected_date.isoformat() if record.detected_date else "",
            record.date_source.value if record.date_source else "",
            year,
            month,
            str(record.destination_path) if record.destination_path else "",
            record.filename_date.isoformat() if record.filename_date else "",
            record.date_mismatch or False,
            record.date_mismatch_days or "",
            # v0.3: Video metadata and error category
            record.video_metadata_date.isoformat() if record.video_metadata_date else "",
            record.error_category or "",
            record.file_hash or "",
            record.is_duplicate or False,
            str(record.duplicate_of) if record.duplicate_of else "",
        ]

    def _get_csv_headers(self) -> list[str]:
        """Get CSV column headers.

        Returns:
            List of header strings.
        """
        return [
            "path",
            "filename",
            "size_bytes",
            "extension",
            "date_taken",
            "date_source",
            "year",
            "month",
            "target_path",
            "filename_date",
            "date_mismatch",
            "date_mismatch_days",
            # v0.3: Video metadata and error category
            "video_metadata_date",
            "error_category",
            "file_hash",
            "is_duplicate",
            "duplicate_of",
        ]

    def _compute_statistics(self, scan_result: ScanResult) -> dict[str, Any]:
        """Compute statistics for scan result.

        Args:
            scan_result: The scan result to analyze.

        Returns:
            Dictionary of statistics.
        """
        files = scan_result.files
        total_size = sum(r.size_bytes for r in files)
        dated_files = [r for r in files if r.detected_date]
        undated_files = [r for r in files if not r.detected_date]
        
        # Count by date source
        source_counts: dict[str, int] = {}
        for record in dated_files:
            if record.date_source:
                source = record.date_source.value
                source_counts[source] = source_counts.get(source, 0) + 1

        # Count by year
        year_counts: dict[str, int] = {}
        for record in files:
            if record.detected_date:
                year = str(record.detected_date.year)
                year_counts[year] = year_counts.get(year, 0) + 1

        # Count by extension
        ext_counts: dict[str, int] = {}
        for record in files:
            ext = record.extension.lower() if record.extension else "no_extension"
            ext_counts[ext] = ext_counts.get(ext, 0) + 1

        # Date mismatch statistics
        mismatch_files = [r for r in files if r.date_mismatch]
        
        # Duplicate statistics
        duplicate_files = [r for r in files if r.is_duplicate]

        # v0.3: Error category counts (from file records)
        error_categories: dict[str, int] = {}
        for record in files:
            if record.error_category:
                cat = record.error_category
                error_categories[cat] = error_categories.get(cat, 0) + 1

        return {
            "total_files": len(files),
            "total_size_bytes": total_size,
            "total_size_human": self._human_readable_size(total_size),
            "dated_files": len(dated_files),
            "undated_files": len(undated_files),
            "date_sources": source_counts,
            "files_by_year": dict(sorted(year_counts.items())),
            "files_by_extension": dict(sorted(ext_counts.items())),
            "date_mismatch_count": len(mismatch_files),
            "duplicate_count": len(duplicate_files),
            # v0.3: Error categories
            "errors_by_category": error_categories if error_categories else None,
        }

    def _human_readable_size(self, size_bytes: int) -> str:
        """Convert bytes to human readable string.

        Args:
            size_bytes: Size in bytes.

        Returns:
            Human readable size string.
        """
        for unit in ["B", "KB", "MB", "GB", "TB"]:
            if size_bytes < 1024.0:
                return f"{size_bytes:.2f} {unit}"
            size_bytes /= 1024.0
        return f"{size_bytes:.2f} PB"

    def _json_serializer(self, obj: Any) -> Any:
        """Custom JSON serializer for special types.

        Args:
            obj: Object to serialize.

        Returns:
            JSON-serializable representation.
        """
        if isinstance(obj, datetime):
            return obj.isoformat()
        if isinstance(obj, Path):
            return str(obj)
        if isinstance(obj, DateSource):
            return obj.value
        raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def export_to_json(
    scan_result: ScanResult,
    output_path: Path | None = None,
    include_statistics: bool = True,
    pretty_print: bool = True,
) -> str:
    """Convenience function to export scan result to JSON.

    Args:
        scan_result: The scan result to export.
        output_path: Optional path to write JSON file.
        include_statistics: Include summary statistics.
        pretty_print: Format with indentation.

    Returns:
        JSON string representation.
    """
    exporter = Exporter(
        include_statistics=include_statistics,
        pretty_print=pretty_print,
    )
    return exporter.to_json(scan_result, output_path)


def export_to_csv(
    scan_result: ScanResult,
    output_path: Path | None = None,
) -> str:
    """Convenience function to export scan result to CSV.

    Args:
        scan_result: The scan result to export.
        output_path: Optional path to write CSV file.

    Returns:
        CSV string representation.
    """
    exporter = Exporter()
    return exporter.to_csv(scan_result, output_path)
