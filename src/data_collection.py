"""
Module thu thập và chuẩn hóa dữ liệu chất lượng không khí & khí tượng Hà Nội.

Tuân thủ:
- Milestone 1 / GitHub Issue #3 & #19.
- Canonical Data Schema trong docs/data_dictionary.md.
- Nguyên tắc an toàn dữ liệu chuỗi thời gian trong .agents/rules/data.md.
- Nguyên tắc kỹ thuật & không over-engineering trong .agents/rules/project.md.
"""

from __future__ import annotations

import concurrent.futures
import gzip
import hashlib
import io
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

# Thiết lập logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Bounding box Hà Nội theo docs/data_dictionary.md & metadata.json
HANOI_BBOX = {
    "lat_min": 20.50,
    "lat_max": 21.60,
    "lon_min": 105.30,
    "lon_max": 106.10,
}

CANONICAL_TIMEZONE = "Asia/Ho_Chi_Minh"
DEFAULT_STATION_CODE = "VN001_HANOI_US_EMBASSY"
DEFAULT_LOCATION_NAME = "US Diplomatic Post: Hanoi"


def compute_file_sha256(filepath: Path) -> str:
    """Tính toán mã băm SHA-256 của tệp để bảo toàn tính toàn vẹn và provenance."""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(65536), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()


class OpenAQAdapter:
    """Adapter thu thập và chuẩn hóa dữ liệu ô nhiễm không khí OpenAQ (Trạm BAM-1020)."""

    def __init__(
        self,
        location_id: int = 2178,
        station_id: str = DEFAULT_STATION_CODE,
        location_name: str = DEFAULT_LOCATION_NAME,
        raw_dir: Path = Path("data/raw"),
        interim_dir: Path = Path("data/interim"),
    ):
        self.location_id = location_id
        self.station_id = station_id
        self.location_name = location_name
        self.raw_dir = Path(raw_dir)
        self.interim_dir = Path(interim_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.interim_dir.mkdir(parents=True, exist_ok=True)

    def _generate_s3_url(self, dt: date) -> str:
        """Tạo đường dẫn URL tải file nén S3 public archive theo ngày."""
        year_str = f"{dt.year}"
        month_str = f"{dt.month:02d}"
        date_str = f"{dt.year}{dt.month:02d}{dt.day:02d}"
        return (
            f"https://openaq-data-archive.s3.amazonaws.com/records/csv.gz/"
            f"locationid={self.location_id}/year={year_str}/month={month_str}/"
            f"location-{self.location_id}-{date_str}.csv.gz"
        )

    def _fetch_single_day(self, url: str) -> Optional[pd.DataFrame]:
        """Tải và giải nén tệp CSV.gz của một ngày từ OpenAQ S3 public archive."""
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "HanoiAirPollutionResearch/1.0 (academic; INFO3020)"},
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as response:
                if response.status == 200:
                    compressed_data = response.read()
                    with gzip.GzipFile(fileobj=io.BytesIO(compressed_data)) as gz:
                        df_day = pd.read_csv(gz)
                        return df_day
        except urllib.error.HTTPError as e:
            if e.code == 404:
                # Ngày trạm ngừng phát sóng hoặc không có file
                return None
            logger.warning(f"Lỗi HTTP {e.code} khi tải {url}: {e.reason}")
            return None
        except Exception as e:
            logger.warning(f"Lỗi khi tải {url}: {str(e)}")
            return None
        return None

    def fetch_raw_data(
        self,
        start_date: str = "2023-01-01",
        end_date: str = "2024-12-31",
        max_workers: int = 10,
        raw_output_name: str = "openaq_raw_2023_2024.parquet",
        force_reload: bool = False,
    ) -> Tuple[pd.DataFrame, Path]:
        """
        Thu thập toàn bộ dữ liệu thô từ OpenAQ S3 archive trong khoảng thời gian xác định.
        Lưu nguyên trạng vào data/raw/ ở chế độ bất biến (raw immutability).
        """
        raw_path = self.raw_dir / raw_output_name
        if not force_reload and raw_path.exists() and raw_path.stat().st_size > 0:
            logger.info(
                f"Tệp thô OpenAQ đã tồn tại tại {raw_path}. Đang nạp từ kho lưu trữ bất biến..."
            )
            df_raw = pd.read_parquet(raw_path)
            return df_raw, raw_path

        start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()

        date_list = []
        curr = start_dt
        while curr <= end_dt:
            date_list.append(curr)
            curr += timedelta(days=1)

        urls = [self._generate_s3_url(d) for d in date_list]
        logger.info(
            f"Bắt đầu tải dữ liệu OpenAQ S3 cho location_id={self.location_id} từ {start_date} đến {end_date} ({len(urls)} ngày)..."
        )

        daily_dfs: List[pd.DataFrame] = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(self._fetch_single_day, urls))

        for df_item in results:
            if df_item is not None and not df_item.empty:
                daily_dfs.append(df_item)

        if not daily_dfs:
            raise RuntimeError(
                f"Không tải được bản ghi nào từ OpenAQ S3 cho location_id={self.location_id} trong dải {start_date} -> {end_date}!"
            )

        df_raw = pd.concat(daily_dfs, ignore_index=True)

        # Lưu dữ liệu thô nguyên trạng không sửa đổi
        df_raw.to_parquet(raw_path, index=False, engine="pyarrow", compression="snappy")
        logger.info(
            f"Đã lưu dữ liệu thô OpenAQ vào {raw_path} ({len(df_raw)} dòng thô, {len(df_raw.columns)} cột)."
        )

        return df_raw, raw_path

    def to_canonical(self, df_raw: pd.DataFrame) -> pd.DataFrame:
        """
        Chuẩn hóa dữ liệu thô OpenAQ sang Canonical Schema theo docs/data_dictionary.md:
        - Parse datetime sang tz-aware Asia/Ho_Chi_Minh (UTC+7).
        - Trích xuất PM2.5 (và PM10 nếu có).
        - Kiểm tra giá trị hợp lệ: âm -> NaN, -999/-9999 -> NaN, giữ 0.0 hợp lệ.
        - Kiểm tra tính duy nhất của khóa quan trắc (station_id, timestamp).
        - Xác thực địa lý Hà Nội.
        """
        df = df_raw.copy()

        # 1. Parse datetime sang múi giờ Asia/Ho_Chi_Minh (hỗ trợ mixed timezones bằng utc=True)
        df["dt_parsed"] = pd.to_datetime(df["datetime"], errors="coerce", utc=True)
        df["timestamp"] = df["dt_parsed"].dt.tz_convert(CANONICAL_TIMEZONE)

        # 2. Lọc các tham số chất lượng không khí quan tâm
        df_pollutants = df[df["parameter"].isin(["pm25", "pm10"])].copy()

        # 3. Xử lý giá trị lỗi / disguised missing markers
        # Theo rule: < 0 -> NaN; -999, -9999 -> NaN
        def clean_val(v: float) -> float:
            if pd.isna(v) or v in (-999.0, -9999.0) or v < 0:
                return np.nan
            return float(v)

        df_pollutants["val_clean"] = df_pollutants["value"].apply(clean_val)

        # 4. Pivot bảng để đưa pm25 và pm10 thành các cột canonical riêng biệt
        df_pivot = df_pollutants.pivot_table(
            index="timestamp",
            columns="parameter",
            values="val_clean",
            aggfunc="first",
        ).reset_index()

        # Đảm bảo có đủ 2 cột pm25 và pm10 trong canonical
        if "pm25" not in df_pivot.columns:
            df_pivot["pm25"] = np.nan
        if "pm10" not in df_pivot.columns:
            df_pivot["pm10"] = np.nan

        # 5. Gán metadata thực thể quan trắc
        df_pivot["station_id"] = self.station_id
        df_pivot["location"] = self.location_name

        # 6. Sắp xếp thứ tự thời gian tuyến tính
        df_canonical = df_pivot[
            ["timestamp", "station_id", "location", "pm25", "pm10"]
        ].sort_values("timestamp").reset_index(drop=True)

        # 7. Kiểm tra trùng lặp khóa quan trắc
        duplicates = df_canonical.duplicated(subset=["station_id", "timestamp"]).sum()
        if duplicates > 0:
            logger.warning(f"Phát hiện {duplicates} bản ghi trùng lặp khóa (station_id, timestamp)! Giữ bản ghi đầu tiên.")
            df_canonical = df_canonical.drop_duplicates(subset=["station_id", "timestamp"], keep="first").reset_index(drop=True)

        return df_canonical

    def validate_geographic_bounds(self, df_raw: pd.DataFrame) -> Tuple[bool, Dict[str, Any]]:
        """Kiểm chứng tọa độ trạm quan trắc đối chiếu với bounding box Hà Nội."""
        lat_col = "lat" if "lat" in df_raw.columns else "latitude"
        lon_col = "lon" if "lon" in df_raw.columns else "longitude"

        if lat_col not in df_raw.columns or lon_col not in df_raw.columns:
            return False, {"error": "Không tìm thấy cột tọa độ trong raw data"}

        coords = df_raw[[lat_col, lon_col]].dropna().drop_duplicates()
        if coords.empty:
            return False, {"error": "Không có bản ghi tọa độ hợp lệ"}

        station_lat = coords.iloc[0][lat_col]
        station_lon = coords.iloc[0][lon_col]

        in_bounds = (
            HANOI_BBOX["lat_min"] <= station_lat <= HANOI_BBOX["lat_max"]
            and HANOI_BBOX["lon_min"] <= station_lon <= HANOI_BBOX["lon_max"]
        )

        return in_bounds, {
            "latitude": float(station_lat),
            "longitude": float(station_lon),
            "bounding_box": HANOI_BBOX,
            "is_within_hanoi": bool(in_bounds),
        }


class OpenMeteoAdapter:
    """Adapter thu thập và chuẩn hóa dữ liệu khí tượng bề mặt ERA5 từ Open-Meteo."""

    def __init__(
        self,
        latitude: float = 21.0285,
        longitude: float = 105.8542,
        timezone: str = CANONICAL_TIMEZONE,
        raw_dir: Path = Path("data/raw"),
        interim_dir: Path = Path("data/interim"),
    ):
        self.latitude = latitude
        self.longitude = longitude
        self.timezone = timezone
        self.raw_dir = Path(raw_dir)
        self.interim_dir = Path(interim_dir)
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.interim_dir.mkdir(parents=True, exist_ok=True)

    def fetch_raw_data(
        self,
        start_date: str = "2023-01-01",
        end_date: str = "2024-12-31",
        raw_output_name: str = "open_meteo_raw_2023_2024.json",
        force_reload: bool = False,
    ) -> Tuple[Dict[str, Any], Path]:
        """
        Gọi Open-Meteo Historical Archive API, lấy 6 biến khí tượng Canonical.
        Lưu raw payload JSON nguyên gốc vào data/raw/ ở chế độ bất biến.
        """
        raw_path = self.raw_dir / raw_output_name
        if not force_reload and raw_path.exists() and raw_path.stat().st_size > 0:
            logger.info(
                f"Tệp thô Open-Meteo đã tồn tại tại {raw_path}. Đang nạp từ kho lưu trữ bất biến..."
            )
            with open(raw_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
            return raw_json, raw_path

        params = {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "start_date": start_date,
            "end_date": end_date,
            "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation,surface_pressure",
            "wind_speed_unit": "ms",
            "timezone": self.timezone,
        }
        encoded_params = urllib.parse.urlencode(params)
        url = f"https://archive-api.open-meteo.com/v1/archive?{encoded_params}"

        logger.info(f"Bắt đầu tải dữ liệu thời tiết Open-Meteo ERA5 từ {start_date} đến {end_date}...")
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "HanoiAirPollutionResearch/1.0 (academic; INFO3020)"},
        )

        with urllib.request.urlopen(req, timeout=45) as response:
            if response.status != 200:
                raise RuntimeError(f"Open-Meteo API trả về mã lỗi HTTP {response.status}")
            raw_content = response.read().decode("utf-8")
            raw_json = json.loads(raw_content)

        raw_path = self.raw_dir / raw_output_name
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_json, f, indent=2, ensure_ascii=False)

        num_hours = len(raw_json.get("hourly", {}).get("time", []))
        logger.info(f"Đã lưu dữ liệu thô Open-Meteo vào {raw_path} ({num_hours} mốc giờ).")

        return raw_json, raw_path

    def to_canonical(self, raw_data: Dict[str, Any]) -> pd.DataFrame:
        """
        Chuẩn hóa payload Open-Meteo sang Canonical Schema:
        - timestamp: datetime64[ns, Asia/Ho_Chi_Minh]
        - temperature, relative_humidity, wind_speed, wind_direction, precipitation, surface_pressure
        """
        hourly = raw_data.get("hourly", {})
        if not hourly or "time" not in hourly:
            raise ValueError("Payload Open-Meteo không chứa cấu trúc 'hourly.time' hợp lệ!")

        df = pd.DataFrame(
            {
                "timestamp": pd.to_datetime(hourly["time"]),
                "temperature": hourly.get("temperature_2m"),
                "relative_humidity": hourly.get("relative_humidity_2m"),
                "wind_speed": hourly.get("wind_speed_10m"),
                "wind_direction": hourly.get("wind_direction_10m"),
                "precipitation": hourly.get("precipitation"),
                "surface_pressure": hourly.get("surface_pressure"),
            }
        )

        # Định dạng múi giờ Asia/Ho_Chi_Minh
        if df["timestamp"].dt.tz is None:
            df["timestamp"] = df["timestamp"].dt.tz_localize(self.timezone)
        else:
            df["timestamp"] = df["timestamp"].dt.tz_convert(self.timezone)

        # Sắp xếp tuyến tính
        df_canonical = df.sort_values("timestamp").reset_index(drop=True)

        # Đảm bảo tính duy nhất
        assert df_canonical["timestamp"].is_unique, "Phát hiện timestamp trùng lặp trong dữ liệu thời tiết Open-Meteo!"

        return df_canonical


def run_collection_pipeline(
    start_date: str = "2023-01-01",
    end_date: str = "2024-12-31",
    save_interim: bool = True,
) -> Dict[str, Any]:
    """
    Hàm thực thi toàn bộ pipeline thu thập và chuẩn hóa dữ liệu ô nhiễm & khí tượng:
    1. Thu thập dữ liệu thô OpenAQ S3 & lưu bất biến vào data/raw/
    2. Thu thập dữ liệu thô Open-Meteo ERA5 & lưu bất biến vào data/raw/
    3. Chuẩn hóa về Canonical Schema
    4. Xác thực địa lý và kiểm toán tính toàn vẹn
    5. Lưu các tập canonical trung gian vào data/interim/
    6. Cập nhật và trả về báo cáo provenance
    """
    t_start = time.time()
    openaq_adapter = OpenAQAdapter()
    weather_adapter = OpenMeteoAdapter()

    # 1. Thu thập OpenAQ
    df_openaq_raw, openaq_raw_path = openaq_adapter.fetch_raw_data(
        start_date=start_date, end_date=end_date
    )
    df_air_canonical = openaq_adapter.to_canonical(df_openaq_raw)
    is_hanoi, geo_details = openaq_adapter.validate_geographic_bounds(df_openaq_raw)

    # 2. Thu thập Open-Meteo
    weather_raw_json, weather_raw_path = weather_adapter.fetch_raw_data(
        start_date=start_date, end_date=end_date
    )
    df_weather_canonical = weather_adapter.to_canonical(weather_raw_json)

    # 3. Lưu interim canonical files nếu được yêu cầu
    air_interim_path = None
    weather_interim_path = None
    if save_interim:
        air_interim_path = openaq_adapter.interim_dir / "air_quality_canonical.parquet"
        weather_interim_path = weather_adapter.interim_dir / "weather_canonical.parquet"
        df_air_canonical.to_parquet(air_interim_path, index=False, compression="snappy")
        df_weather_canonical.to_parquet(weather_interim_path, index=False, compression="snappy")
        logger.info(f"Đã lưu canonical interim files: {air_interim_path} và {weather_interim_path}")

    # 4. Tính toán chỉ số kiểm toán
    openaq_sha256 = compute_file_sha256(openaq_raw_path)
    weather_sha256 = compute_file_sha256(weather_raw_path)

    summary = {
        "execution_time_seconds": round(time.time() - t_start, 2),
        "study_window": {"start": start_date, "end": end_date},
        "openaq": {
            "raw_file": str(openaq_raw_path),
            "sha256": openaq_sha256,
            "raw_rows": len(df_openaq_raw),
            "canonical_rows": len(df_air_canonical),
            "pm25_valid_count": int(df_air_canonical["pm25"].notna().sum()),
            "pm25_missing_count": int(df_air_canonical["pm25"].isna().sum()),
            "pm25_missing_rate_pct": round(float(df_air_canonical["pm25"].isna().mean() * 100), 2),
            "min_timestamp": str(df_air_canonical["timestamp"].min()),
            "max_timestamp": str(df_air_canonical["timestamp"].max()),
            "geographic_validation": geo_details,
        },
        "open_meteo": {
            "raw_file": str(weather_raw_path),
            "sha256": weather_sha256,
            "canonical_rows": len(df_weather_canonical),
            "missing_rates_pct": {
                col: round(float(df_weather_canonical[col].isna().mean() * 100), 2)
                for col in ["temperature", "relative_humidity", "wind_speed", "wind_direction", "precipitation", "surface_pressure"]
            },
            "min_timestamp": str(df_weather_canonical["timestamp"].min()),
            "max_timestamp": str(df_weather_canonical["timestamp"].max()),
        },
    }

    logger.info("Hoàn tất pipeline thu thập và chuẩn hóa dữ liệu thành công!")
    return summary


if __name__ == "__main__":
    import sys
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    summary_report = run_collection_pipeline()
    print("\n--- BÁO CÁO KẾT QUẢ THU THẬP ---")
    print(json.dumps(summary_report, indent=2, ensure_ascii=False))
