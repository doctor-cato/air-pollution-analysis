"""Regression tests for the CP0 public-mirror inventory; fixtures are synthetic."""

from __future__ import annotations

import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "profile_airnow_mirror.py"
SPEC = importlib.util.spec_from_file_location("profile_airnow_mirror", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
PROFILE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PROFILE)


def _rows(timestamps: pd.DatetimeIndex, value: float = 10.0) -> pd.DataFrame:
    return pd.DataFrame({
        "Site": "Hanoi",
        "Parameter": "PM2.5 - Principal",
        "Date (LT)": timestamps.strftime("%m/%d/%Y %I:%M:%S %p"),
        "Raw Conc.": value,
        "NowCast Conc.": 999.0,
    })


class TestAirNowMirrorProfiler(unittest.TestCase):
    def _write(self, root: Path, relative_path: str, frame: pd.DataFrame) -> None:
        target = PROFILE.local_raw_path(root, relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(target, index=False)

    @staticmethod
    def _file(path: str, kind: str = "YTD") -> dict[str, str]:
        return {"path": path, "kind": kind}

    @staticmethod
    def _full_calendar() -> pd.DatetimeIndex:
        return pd.date_range("2022-01-01", "2025-12-31 23:00", freq="h")

    def test_relative_paths_prevent_same_basename_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = PROFILE.local_raw_path(root, "Data/Hanoi/2022/Hanoi_PM2.5_2022_YTD.csv")
            second = PROFILE.local_raw_path(root, "Data/Hanoi/2023/Hanoi_PM2.5_2022_YTD.csv")
            self.assertNotEqual(first, second)
            self._write(root, str(first.relative_to(root)), _rows(pd.date_range("2022-01-01", periods=1, freq="h")))
            self._write(root, str(second.relative_to(root)), _rows(pd.date_range("2022-01-02", periods=1, freq="h")))
            self.assertTrue(first.exists())
            self.assertTrue(second.exists())

    def test_download_pins_commit_and_verifies_git_blob(self) -> None:
        payload = b"timestamp,value\n2022-01-01,10\n"
        blob_sha = hashlib.sha1(f"blob {len(payload)}\0".encode("ascii") + payload).hexdigest()
        item = {"path": "Data/Hanoi/2022/Hanoi_PM2.5_2022_YTD.csv", "sha": blob_sha}
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(PROFILE, "fetch_bytes", return_value=payload) as fetch:
                destination, verified = PROFILE.download_verified_blob(item, "a" * 40, Path(temporary))
            self.assertEqual(verified, blob_sha)
            self.assertEqual(destination.read_bytes(), payload)
            self.assertIn("/" + "a" * 40 + "/", fetch.call_args.args[0])

    def test_download_rejects_mismatched_git_blob(self) -> None:
        item = {"path": "Data/Hanoi/2022/Hanoi_PM2.5_2022_YTD.csv", "sha": "0" * 40}
        with tempfile.TemporaryDirectory() as temporary:
            with patch.object(PROFILE, "fetch_bytes", return_value=b"different"):
                with self.assertRaisesRegex(ValueError, "Git blob SHA mismatch"):
                    PROFILE.download_verified_blob(item, "b" * 40, Path(temporary))

    def test_coverage_separates_ytd_mtd_identical_duplicates(self) -> None:
        path = "Data/Hanoi/2022/Hanoi_PM2.5_2022_YTD.csv"
        mtd_path = "Data/Hanoi/2022/Hanoi_PM2.5_2022_01_MTD.csv"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calendar = self._full_calendar()
            self._write(root, path, _rows(calendar))
            self._write(root, mtd_path, _rows(calendar[:1]))
            coverage = PROFILE.coverage_from_downloads(
                [self._file(path), self._file(mtd_path, "MTD")], root
            )
        self.assertEqual(coverage["duplicate_source_rows"], 1)
        self.assertEqual(coverage["ytd_mtd_overlap_hours"], 1)
        self.assertEqual(coverage["identical_duplicate_hours"], 1)
        self.assertEqual(coverage["conflicting_duplicate_hours"], 0)
        self.assertEqual(coverage["annual"][0]["valid_hours"], 8760)

    def test_conflicting_duplicate_is_not_counted_as_valid(self) -> None:
        path = "Data/Hanoi/2022/Hanoi_PM2.5_2022_YTD.csv"
        mtd_path = "Data/Hanoi/2022/Hanoi_PM2.5_2022_01_MTD.csv"
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            calendar = self._full_calendar()
            self._write(root, path, _rows(calendar, 10.0))
            self._write(root, mtd_path, _rows(calendar[:1], 20.0))
            coverage = PROFILE.coverage_from_downloads(
                [self._file(path), self._file(mtd_path, "MTD")], root
            )
        self.assertEqual(coverage["conflicting_duplicate_hours"], 1)
        self.assertEqual(coverage["annual"][0]["valid_hours"], 8759)
        self.assertEqual(coverage["annual"][0]["conflicting_hours"], 1)

    def test_longest_gap_carries_across_month_and_year(self) -> None:
        path = "Data/Hanoi/2022/Hanoi_PM2.5_2022_YTD.csv"
        calendar = self._full_calendar()
        missing = {pd.Timestamp("2022-12-31 23:00"), pd.Timestamp("2023-01-01 00:00")}
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._write(root, path, _rows(calendar[~calendar.isin(missing)]))
            coverage = PROFILE.coverage_from_downloads([self._file(path)], root)
        monthly = {row["month"]: row for row in coverage["monthly"]}
        annual = {row["year"]: row for row in coverage["annual"]}
        self.assertEqual(monthly["2022-12"]["longest_gap_hours"], 2)
        self.assertEqual(monthly["2023-01"]["longest_gap_hours"], 2)
        self.assertEqual(annual[2022]["longest_gap_hours"], 2)
        self.assertEqual(annual[2023]["longest_gap_hours"], 2)
