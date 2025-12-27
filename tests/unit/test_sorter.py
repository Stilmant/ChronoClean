"""Unit tests for chronoclean.core.sorter."""

from datetime import datetime
from pathlib import Path

import pytest

from chronoclean.core.sorter import Sorter, SortingPlan


class TestSorterInit:
    """Tests for Sorter initialization."""

    def test_default_init(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir)

        assert sorter.destination_root == temp_dir
        assert sorter.folder_structure == "YYYY/MM"

    def test_custom_folder_structure(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY/MM/DD")

        assert sorter.folder_structure == "YYYY/MM/DD"

    def test_year_only_structure(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY")

        assert sorter.folder_structure == "YYYY"

    def test_invalid_structure_uses_default(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="invalid")

        assert sorter.folder_structure == "YYYY/MM"

    def test_path_converted_to_pathlib(self, temp_dir: Path):
        sorter = Sorter(destination_root=str(temp_dir))

        assert isinstance(sorter.destination_root, Path)


class TestComputeDestinationFolder:
    """Tests for compute_destination_folder method."""

    def test_year_month_structure(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY/MM")
        date = datetime(2024, 3, 15)

        result = sorter.compute_destination_folder(date)

        assert result == temp_dir / "2024" / "03"

    def test_year_month_day_structure(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY/MM/DD")
        date = datetime(2024, 3, 15)

        result = sorter.compute_destination_folder(date)

        assert result == temp_dir / "2024" / "03" / "15"

    def test_year_only_structure(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY")
        date = datetime(2024, 3, 15)

        result = sorter.compute_destination_folder(date)

        assert result == temp_dir / "2024"

    def test_single_digit_month_padded(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY/MM")
        date = datetime(2024, 1, 5)

        result = sorter.compute_destination_folder(date)

        assert result == temp_dir / "2024" / "01"

    def test_single_digit_day_padded(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY/MM/DD")
        date = datetime(2024, 1, 5)

        result = sorter.compute_destination_folder(date)

        assert result == temp_dir / "2024" / "01" / "05"


class TestComputeFullDestination:
    """Tests for compute_full_destination method."""

    def test_with_original_filename(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir)
        source = Path("/source/photo.jpg")
        date = datetime(2024, 3, 15)

        result = sorter.compute_full_destination(source, date)

        assert result == temp_dir / "2024" / "03" / "photo.jpg"

    def test_with_new_filename(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir)
        source = Path("/source/photo.jpg")
        date = datetime(2024, 3, 15)

        result = sorter.compute_full_destination(source, date, "20240315_143045.jpg")

        assert result == temp_dir / "2024" / "03" / "20240315_143045.jpg"

    def test_new_filename_without_extension(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir)
        source = Path("/source/photo.JPG")
        date = datetime(2024, 3, 15)

        result = sorter.compute_full_destination(source, date, "20240315_143045")

        # Should add extension from source (lowercase)
        assert result == temp_dir / "2024" / "03" / "20240315_143045.jpg"

    def test_preserves_extension_when_provided(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir)
        source = Path("/source/video.MOV")
        date = datetime(2024, 3, 15)

        result = sorter.compute_full_destination(source, date, "20240315_143045.mov")

        assert result == temp_dir / "2024" / "03" / "20240315_143045.mov"


class TestGetRelativeDestination:
    """Tests for get_relative_destination method."""

    def test_basic_relative_path(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY/MM")
        date = datetime(2024, 3, 15)

        result = sorter.get_relative_destination(date, "photo.jpg")

        assert result == "2024/03/photo.jpg"

    def test_year_month_day_relative(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY/MM/DD")
        date = datetime(2024, 3, 15)

        result = sorter.get_relative_destination(date, "photo.jpg")

        assert result == "2024/03/15/photo.jpg"


class TestSortingPlanInit:
    """Tests for SortingPlan initialization."""

    def test_default_init(self, temp_dir: Path):
        plan = SortingPlan(destination_root=temp_dir)

        assert plan.sorter is not None
        assert plan.destinations == {}
        assert plan.conflicts == []

    def test_custom_structure(self, temp_dir: Path):
        plan = SortingPlan(destination_root=temp_dir, folder_structure="YYYY")

        assert plan.sorter.folder_structure == "YYYY"


class TestSortingPlanAddFile:
    """Tests for SortingPlan.add_file method."""

    def test_add_single_file(self, temp_dir: Path):
        plan = SortingPlan(destination_root=temp_dir)
        source = Path("/source/photo.jpg")
        date = datetime(2024, 3, 15)

        result = plan.add_file(source, date)

        assert result == temp_dir / "2024" / "03" / "photo.jpg"
        assert source in plan.destinations

    def test_add_file_with_rename(self, temp_dir: Path):
        plan = SortingPlan(destination_root=temp_dir)
        source = Path("/source/IMG_001.jpg")
        date = datetime(2024, 3, 15)

        result = plan.add_file(source, date, "20240315_143045.jpg")

        assert result == temp_dir / "2024" / "03" / "20240315_143045.jpg"

    def test_add_multiple_files(self, temp_dir: Path):
        plan = SortingPlan(destination_root=temp_dir)
        source1 = Path("/source/photo1.jpg")
        source2 = Path("/source/photo2.jpg")
        date1 = datetime(2024, 3, 15)
        date2 = datetime(2024, 4, 20)

        plan.add_file(source1, date1)
        plan.add_file(source2, date2)

        assert len(plan.destinations) == 2
        assert source1 in plan.destinations
        assert source2 in plan.destinations


class TestSortingPlanConflicts:
    """Tests for conflict detection in SortingPlan."""

    def test_no_conflicts_different_destinations(self, temp_dir: Path):
        plan = SortingPlan(destination_root=temp_dir)
        source1 = Path("/source/photo1.jpg")
        source2 = Path("/source/photo2.jpg")
        date = datetime(2024, 3, 15)

        plan.add_file(source1, date, "file1.jpg")
        plan.add_file(source2, date, "file2.jpg")

        assert plan.has_conflicts is False
        assert plan.conflicts == []

    def test_detects_conflict_same_destination(self, temp_dir: Path):
        plan = SortingPlan(destination_root=temp_dir)
        source1 = Path("/source/photo1.jpg")
        source2 = Path("/source/photo2.jpg")
        date = datetime(2024, 3, 15)

        # Both files get same destination
        plan.add_file(source1, date, "same_name.jpg")
        plan.add_file(source2, date, "same_name.jpg")

        assert plan.has_conflicts is True
        assert len(plan.conflicts) == 1
        assert (source2, source1) in plan.conflicts

    def test_multiple_conflicts(self, temp_dir: Path):
        plan = SortingPlan(destination_root=temp_dir)
        date = datetime(2024, 3, 15)

        # Three files all going to same destination
        plan.add_file(Path("/a.jpg"), date, "same.jpg")
        plan.add_file(Path("/b.jpg"), date, "same.jpg")
        plan.add_file(Path("/c.jpg"), date, "same.jpg")

        assert plan.has_conflicts is True
        assert len(plan.conflicts) == 2  # b conflicts with a, c conflicts with a


class TestSortingPlanProperties:
    """Tests for SortingPlan property accessors."""

    def test_destinations_returns_copy(self, temp_dir: Path):
        plan = SortingPlan(destination_root=temp_dir)
        source = Path("/source/photo.jpg")
        plan.add_file(source, datetime(2024, 3, 15))

        destinations = plan.destinations
        destinations[Path("/other.jpg")] = temp_dir / "fake"

        # Original should not be modified
        assert Path("/other.jpg") not in plan.destinations

    def test_conflicts_returns_copy(self, temp_dir: Path):
        plan = SortingPlan(destination_root=temp_dir)
        date = datetime(2024, 3, 15)
        plan.add_file(Path("/a.jpg"), date, "same.jpg")
        plan.add_file(Path("/b.jpg"), date, "same.jpg")

        conflicts = plan.conflicts
        conflicts.append((Path("/fake1"), Path("/fake2")))

        # Original should not be modified
        assert len(plan.conflicts) == 1


class TestEdgeCases:
    """Edge case tests for sorter."""

    def test_january_first(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY/MM/DD")
        date = datetime(2024, 1, 1)

        result = sorter.compute_destination_folder(date)

        assert result == temp_dir / "2024" / "01" / "01"

    def test_december_31st(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY/MM/DD")
        date = datetime(2024, 12, 31)

        result = sorter.compute_destination_folder(date)

        assert result == temp_dir / "2024" / "12" / "31"

    def test_leap_year_feb_29(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir, folder_structure="YYYY/MM/DD")
        date = datetime(2024, 2, 29)  # 2024 is a leap year

        result = sorter.compute_destination_folder(date)

        assert result == temp_dir / "2024" / "02" / "29"

    def test_various_extensions(self, temp_dir: Path):
        sorter = Sorter(destination_root=temp_dir)
        date = datetime(2024, 3, 15)

        for ext in [".jpg", ".png", ".heic", ".mp4", ".cr2"]:
            source = Path(f"/source/file{ext}")
            result = sorter.compute_full_destination(source, date)
            assert result.suffix == ext
