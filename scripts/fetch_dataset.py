
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_RAW = REPO_ROOT / "data" / "raw"
DEFAULT_INTERIM = REPO_ROOT / "data" / "interim"
DEFAULT_METADATA = REPO_ROOT / "data" / "raw" / "metadata.json"


def summarise_interim_on_disk(interim_dir: Path) -> Dict[str, Any]:
    air_path = interim_dir / "air_quality_canonical.parquet"
    wx_path = interim_dir / "weather_canonical.parquet"
    for path in (air_path, wx_path):
        if not path.exists():
            raise FileNotFoundError(
                f"Không tìm thấy {path}. Hãy chạy `python scripts/fetch_dataset.py` "
                "để tải và tạo dữ liệu canonical trước."
            )

    air = pd.read_parquet(air_path)
    weather = pd.read_parquet(wx_path)
    overlap = pd.merge(air, weather, on="timestamp", how="inner")

    return {
        "openaq": {
            "raw_records_total": None,
            "canonical_records": len(air),
            "actual_source_coverage": {
                "actual_min_timestamp": str(air["timestamp"].min()),
                "actual_max_timestamp": str(air["timestamp"].max()),
            },
        },
        "open_meteo": {
            "canonical_records": len(weather),
            "actual_source_coverage": {
                "actual_min_timestamp": str(weather["timestamp"].min()),
                "actual_max_timestamp": str(weather["timestamp"].max()),
            },
        },
        "temporal_integration": {
            "overlap_records": len(overlap),
            "air_quality_coverage_pct": round(len(overlap) / len(air) * 100, 2),
            "row_explosion_detected": len(overlap) > len(air),
        },
    }


def compare_with_metadata(summary: Dict[str, Any], metadata_path: Path) -> bool:
    print("\n=== Kiem chung noi dung voi metadata.json ===")
    if not metadata_path.exists():
        print(f"  ! Khong tim thay {metadata_path} - bo qua buoc kiem chung.")
        return True

    with open(metadata_path, encoding="utf-8") as handle:
        meta = json.load(handle)
    recorded = meta.get("collection_pipeline_execution", {})

    rec_aq = recorded.get("openaq_ingestion", {})
    got_aq = summary["openaq"]
    rec_wx = recorded.get("open_meteo_ingestion", {})
    got_wx = summary["open_meteo"]
    rec_ti = recorded.get("temporal_integration", {})
    got_ti = summary["temporal_integration"]

    checks = [
        ("OpenAQ so ban ghi tho",
         rec_aq.get("raw_records_total"), got_aq["raw_records_total"]),
        ("OpenAQ so ban ghi canonical",
         rec_aq.get("canonical_records"), got_aq["canonical_records"]),
        ("OpenAQ moc thoi gian bat dau",
         rec_aq.get("actual_source_coverage", {}).get("actual_min_timestamp"),
         got_aq["actual_source_coverage"]["actual_min_timestamp"]),
        ("OpenAQ moc thoi gian ket thuc",
         rec_aq.get("actual_source_coverage", {}).get("actual_max_timestamp"),
         got_aq["actual_source_coverage"]["actual_max_timestamp"]),
        ("Khi tuong so ban ghi canonical",
         rec_wx.get("canonical_records"), got_wx["canonical_records"]),
        ("So ban ghi giao thoa",
         rec_ti.get("overlap_records"), got_ti["overlap_records"]),
        ("Do phu giao thoa (%)",
         rec_ti.get("air_quality_coverage_pct"), got_ti["air_quality_coverage_pct"]),
    ]

    all_match = True
    compared = 0
    for label, recorded_value, actual_value in checks:
        if recorded_value is None or actual_value is None:
            print(f"  [--  ] {label}: bo qua (khong dan xuat duoc o che do nay)")
            continue
        compared += 1
        match = recorded_value == actual_value
        all_match &= match
        flag = "OK  " if match else "KHAC"
        print(f"  [{flag}] {label}: metadata={recorded_value} | taiVe={actual_value}")

    if compared == 0:
        print("  ! Khong co muc nao de so sanh.")
        return False
    if not all_match:
        print(
            "\n  Luu y: kho OpenAQ S3 la kho SONG, nha cung cap tiep tuc nap du lieu moi.\n"
            "  Chenh lech so ban ghi LA binh thuong va khong bao loi. Nhung muc do phu\n"
            "  giao thoa va so ban ghi canonical phai giong nhau de moi dung cho phan tich."
        )
    return all_match


def _fmt(value: object) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tai va kiem chung tap du lieu tu nguon cong khai (khong can API key)."
    )
    parser.add_argument("--raw-dir", type=Path, default=DEFAULT_RAW)
    parser.add_argument("--interim-dir", type=Path, default=DEFAULT_INTERIM)
    parser.add_argument("--metadata", type=Path, default=DEFAULT_METADATA)
    parser.add_argument(
        "--skip-fetch",
        action="store_true",
        help=(
            "Chi kiem chung tap du lieu canonical da co san tren dia (doc "
            "data/interim/*.parquet), khong tai lai tu nguon. Dung khi kho OpenAQ S3 da "
            "co du lieu moi va khong muon lam thay doi ban dang kiem toan."
        ),
    )
    args = parser.parse_args()

    print("=" * 74)
    print("TAI VA KIEM CHUNG TAP DU LIEU - doctor-cato/air-pollution-analysis")
    print("=" * 74)
    print("Nguon   : OpenAQ S3 public archive (ODC-BY v1.0) + Open-Meteo ERA5 (CC BY 4.0)")
    print("Yeu cau : ket noi Internet (chi can o che do tai). KHONG can API key.")

    if args.skip_fetch:
        print("\nChe do --skip-fetch: kiem chung du lieu tren dia, khong goi mang.")
        try:
            summary = summarise_interim_on_disk(args.interim_dir)
        except FileNotFoundError as exc:
            print(f"\nLoi: {exc}")
            return 1
    else:
        print(f"\nDia chi: {args.raw_dir}")
        print("Dang tai du lieu tu nguon (co the mat vai phut)...\n")
        from src.data_collection import run_collection_pipeline

        summary = run_collection_pipeline(
            raw_dir=args.raw_dir,
            interim_dir=args.interim_dir,
            metadata_path=args.metadata,
        )

    print("\n=== Ket qua thu thap ===")
    aq, wx, ti = summary["openaq"], summary["open_meteo"], summary["temporal_integration"]
    if aq.get("raw_records_total") is not None:
        print(f"  Ban ghi tho OpenAQ      : {_fmt(aq['raw_records_total'])}")
    print(f"  Ban ghi canonical chat luong khong khí : {_fmt(aq['canonical_records'])}")
    print(f"  Do phu thoi gian       : {aq['actual_source_coverage']['actual_min_timestamp']}"
          f" -> {aq['actual_source_coverage']['actual_max_timestamp']}")
    print(f"  Ban ghi canonical khi tuong           : {_fmt(wx['canonical_records'])}")
    print(f"  Do phu thoi gian       : {wx['actual_source_coverage']['actual_min_timestamp']}"
          f" -> {wx['actual_source_coverage']['actual_max_timestamp']}")
    print(f"  Giao thoa thoi gian     : {_fmt(ti['overlap_records'])} ban ghi "
          f"({ti['air_quality_coverage_pct']}% do phu)")
    print(f"  Row explosion          : {'CO' if ti['row_explosion_detected'] else 'KHONG'}")

    compare_with_metadata(summary, args.metadata)

    print("\n" + "=" * 74)
    print("SAN SANG. Tiep theo:")
    print("  python -m unittest discover tests")
    print("  jupyter nbconvert --to notebook --execute notebooks/01_data_collection.ipynb")
    print("  jupyter nbconvert --to notebook --execute notebooks/02_quality_audit.ipynb")
    print("=" * 74)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
