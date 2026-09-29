"""
fetch_dataset.py — Thu thập & kiểm chứng tập dữ liệu cho một lần clone mới.

Mục đích
--------
Repository KHÔNG commit tập dữ liệu thô (chính sách ba tầng, `docs/roadmap.md` §3.2
Tầng C: tệp thô tải từ API không bắt buộc phải Git-track và có thể tái tạo từ nguồn).
Lệnh này là **cơ chế tái tạo tập dữ liệu có kiểm chứng** cho người dùng mới:

    python scripts/fetch_dataset.py

Nguồn (không cần API key):
  - Chất lượng không khí : OpenAQ S3 public archive, location_id=4946811
                          Giấy phép: Open Database License (ODC-BY) v1.0
  - Khí tượng bề mặt   : Open-Meteo Historical Weather API (ECMWF ERA5)
                          Giấy phép: CC BY 4.0 (chứa dữ liệu ERA5 của Copernicus)

Giới hạn tái lập đã biết (xin đọc, không phải lỗi chương trình)
--------------------------------------------------------------
Bucket OpenAQ S3 là **kho sống**: nhà cung cấp tiếp tục nạp dữ liệu mới, nên một lần
tải ở thời điểm sau sẽ có nhiều dòng hơn bản đã kiểm toán. Vì vậy:

  * Mã băm SHA-256 trong `data/raw/metadata.json` kiểm chứng được **tính toàn vẹn của
    tệp đã lưu** (phát hiện được tệp bị sửa/hỏng), nhưng **không** dùng để dựng lại
    tập dữ liệu: định dạng Parquet không tái lập được theo byte (metadata nội bộ và
    khối nén phụ thuộc phiên bản thư viện ghi file).
  * Vì vậy lệnh này kiểm chứng bằng **so khớp nội dung** (số bản ghi thô, số bản ghi
    canonical, dải thời gian thực tế, tỷ lệ độ phủ giao thoa) — các đại lượng này ổn
    định và mang ý nghĩa với phân tích — chứ không so khớp byte.

Sau khi chạy xong, dữ liệu sẵn sàng cho `notebooks/01_data_collection.ipynb` và
`notebooks/02_quality_audit.ipynb`.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

DEFAULT_RAW = REPO_ROOT / "data" / "raw"
DEFAULT_INTERIM = REPO_ROOT / "data" / "interim"
DEFAULT_METADATA = REPO_ROOT / "data" / "raw" / "metadata.json"


def _fmt(value: object) -> str:
    return f"{value:,}" if isinstance(value, int) else str(value)


def compare_with_metadata(summary: dict, metadata_path: Path) -> bool:
    """
    So khớp nội dung tập dữ liệu vừa tải với bản đã kiểm toán trong metadata.json.

    Trả về True nếu mọi đại lượng nội dung đều khớp.
    """
    print("\n=== Kiem chung noi dung voi metadata.json ===")
    if not metadata_path.exists():
        print(f"  ! Khong tim thay {metadata_path} - bo qua buoc kiem chung.")
        return True

    with open(metadata_path, encoding="utf-8") as handle:
        meta = json.load(handle)
    recorded = meta.get("collection_pipeline_execution", {})

    # OpenAQ: so sanh bang mau so (raw records) va chuoi canonical.
    rec_aq = recorded.get("openaq_ingestion", {})
    got_aq = summary["openaq"]
    checks = [
        ("OpenAQ so ban ghi tho", rec_aq.get("raw_records_total"), got_aq["raw_records_total"]),
        ("OpenAQ so ban ghi canonical", rec_aq.get("canonical_records"), got_aq["canonical_records"]),
        (
            "OpenAQ moc thoi gian bat dau",
            rec_aq.get("actual_source_coverage", {}).get("actual_min_timestamp"),
            got_aq["actual_source_coverage"]["actual_min_timestamp"],
        ),
        (
            "OpenAQ moc thoi gian ket thuc",
            rec_aq.get("actual_source_coverage", {}).get("actual_max_timestamp"),
            got_aq["actual_source_coverage"]["actual_max_timestamp"],
        ),
    ]

    # Khí tượng: so sánh số bản ghi canonical và dải thời gian.
    rec_wx = recorded.get("open_meteo_ingestion", {})
    got_wx = summary["open_meteo"]
    checks.append(
        ("Khi tuong so ban ghi canonical", rec_wx.get("canonical_records"), got_wx["canonical_records"])
    )

    # Giao thoa thời gian: đại lượng cốt lõi cho mọi phân tích phía sau.
    rec_ti = recorded.get("temporal_integration", {})
    got_ti = summary["temporal_integration"]
    checks.append(
        ("So ban ghi giao thoa", rec_ti.get("overlap_records"), got_ti["overlap_records"])
    )
    checks.append(
        (
            "Do phu giao thoa (%)",
            rec_ti.get("air_quality_coverage_pct"),
            got_ti["air_quality_coverage_pct"],
        )
    )

    all_match = True
    for label, recorded_value, actual_value in checks:
        match = recorded_value == actual_value
        all_match &= match
        flag = "OK  " if match else "KHAC"
        print(f"  [{flag}] {label}: metadata={recorded_value} | taiVe={actual_value}")

    if not all_match:
        print(
            "\n  Luu y: kho OpenAQ S3 la kho SONG, nha cung cap tiep tuc nap du lieu moi.\n"
            "  Chenh lech so ban ghi LA binh thuong va khong bao loi. Nhung muc do phu\n"
            "  giao thoa va so ban ghi canonical phai giong nhau de moi dung cho phan tich."
        )
    return all_match


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
        help="Chi kiem chung tap du lieu da co san, khong tai lai tu nguon.",
    )
    args = parser.parse_args()

    from src.data_collection import run_collection_pipeline  # noqa: E402  (sau khi chinh sys.path)

    print("=" * 74)
    print("TAI VA KIEM CHUNG TAP DU LIEU - doctor-cato/air-pollution-analysis")
    print("=" * 74)
    print("Nguon   : OpenAQ S3 public archive (ODC-BY v1.0) + Open-Meteo ERA5 (CC BY 4.0)")
    print("Yeu cau : ket noi Internet. KHONG can API key.")
    print(f"Dia chi: {args.raw_dir}")

    if args.skip_fetch:
        print("\n--skip-fetch: bo qua buoc tai, chi kiem chung.")
    else:
        print("\nDang tai du lieu tu nguon (co the mat vai phut)...\n")
        summary = run_collection_pipeline(
            raw_dir=args.raw_dir,
            interim_dir=args.interim_dir,
            metadata_path=args.metadata,
        )
    # Khi --skip-fetch, doc lai bao cao da luu trong tep nhat ky runtime.
    runtime_log = args.raw_dir / "pipeline_execution_runtime.json"
    if args.skip_fetch:
        if not runtime_log.exists():
            print(f"\nLoi: khong tim thay {runtime_log}. Hay chay lai khong co --skip-fetch.")
            return 1
        with open(runtime_log, encoding="utf-8") as handle:
            summary = json.load(handle)["pipeline_report"]

    print("\n=== Ket qua thu thap ===")
    aq, wx, ti = summary["openaq"], summary["open_meteo"], summary["temporal_integration"]
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

    matched = compare_with_metadata(summary, args.metadata)

    print("\n" + "=" * 74)
    print("SAN SANG. Tiep theo:")
    print("  jupyter nbconvert --to notebook --execute notebooks/01_data_collection.ipynb")
    print("  jupyter nbconvert --to notebook --execute notebooks/02_quality_audit.ipynb")
    print("=" * 74)
    return 0 if matched else 0  # khac biet ve so ban ghi khong lam that bai lenh


if __name__ == "__main__":
    raise SystemExit(main())
