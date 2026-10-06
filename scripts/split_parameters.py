
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.cleaning import export_split_air_quality_datasets


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Tách dữ liệu PM2.5 và PM10 sau làm sạch thành hai tệp riêng biệt."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=REPO_ROOT / "data" / "interim" / "air_quality_canonical.parquet",
        help="Đường dẫn đến tệp Parquet chất lượng không khí đã làm sạch (mặc định: data/interim/air_quality_canonical.parquet)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=REPO_ROOT / "data" / "interim",
        help="Thư mục xuất các tệp đã tách (mặc định: data/interim)",
    )
    parser.add_argument(
        "--drop-na",
        action="store_true",
        help="Nếu bật, loại bỏ các dòng có giá trị NaN ở biến mục tiêu tương ứng của mỗi tệp.",
    )
    parser.add_argument(
        "--prefix",
        type=str,
        default="air_quality",
        help="Tiền tố tên tệp đầu ra (mặc định: 'air_quality' -> 'air_quality_pm25.parquet', 'air_quality_pm10.parquet')",
    )

    args = parser.parse_args()

    input_path: Path = args.input
    if not input_path.exists():
        print(f"❌ LỖI: Tệp đầu vào không tồn tại: {input_path}")
        print("   Hãy đảm bảo bạn đã chạy pipeline làm sạch dữ liệu trước:")
        print("   python scripts/fetch_dataset.py")
        print("   jupyter nbconvert --to notebook --execute notebooks/03_data_cleaning.ipynb")
        return 1

    print(f"Đang đọc dữ liệu từ: {input_path}")
    df_air = pd.read_parquet(input_path)
    print(f"  Số dòng: {len(df_air):,}, Số cột: {len(df_air.columns)}")

    pm25_file, pm10_file = export_split_air_quality_datasets(
        df_air=df_air,
        output_dir=args.output_dir,
        drop_target_na=args.drop_na,
        prefix=args.prefix,
    )

    df_p25 = pd.read_parquet(pm25_file)
    df_p10 = pd.read_parquet(pm10_file)

    print("\n✓ ĐÃ TÁCH THÀNH CÔNG:")
    print(f"  1. PM2.5: {pm25_file}")
    print(f"     - Kích thước: {len(df_p25):,} dòng × {len(df_p25.columns)} cột")
    print(f"     - Các cột   : {list(df_p25.columns)}")
    print(f"  2. PM10 : {pm10_file}")
    print(f"     - Kích thước: {len(df_p10):,} dòng × {len(df_p10.columns)} cột")
    print(f"     - Các cột   : {list(df_p10.columns)}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
