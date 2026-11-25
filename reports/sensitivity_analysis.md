# Báo Cáo Phân Tích Độ Nhạy Đa Chiều (Issue #15)

- **Run ID:** `issue15_sens_20261120T072026Z_seed42`
- **Generated (UTC):** `2026-11-20T07:20:26.123506+00:00`
- **Deterministic Seed:** `42`
- **Giao thức trạm:** Protocol A đơn trạm nghiêm ngặt (cấm gộp đa trạm lệch pha Protocol B).
- **Khung mô hình:** Phân loại dùng `LogisticRegression(class_weight='balanced')` trong `Pipeline` chống rò rỉ (`SimpleImputer` + `RobustScaler`, tinh chỉnh ngưỡng $F_2$ trên Train 5-fold `TimeSeriesSplit`); Hồi quy dùng OLS kèm sai số chuẩn `HAC Newey-West (maxlags=24)`.

## 1. Cấu Hình Phạm Vi Dữ Liệu & Minh Bạch Khác Biệt Mốc Chia

| cohort_name | station_id | dataset_version | split_protocol | effective_test_start | grid_rows | train_grid_rows | test_grid_rows | valid_pm25_rows | dataset_sha256 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | VN001_HANOI_556_NGUYEN_VAN_CU | 1.0.0-m2-baseline | fixed_timestamp (2026-01-15 00:00:00+07:00) | 2026-01-15 00:00:00+07:00 | 9044 | 4682 | 4362 | 7495 | 866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd |
| VN003_extended_80_20 | VN003_HANOI_OPENAQ_7441 | 2.0.0-issue44-extended | station_specific_80_20 (Protocol A) | 2024-08-13 23:00:00+07:00 | 28678 | 22942 | 5736 | 18208 | 6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02 |
| VN001_extended_80_20 | VN001_HANOI_556_NGUYEN_VAN_CU | 2.0.0-issue44-extended | station_specific_80_20 (Protocol A) | 2026-05-01 09:00:00+07:00 | 9044 | 7235 | 1809 | 7495 | 6930557fbfc8e31dbcb062065b1903ccf27c433e9c0f062bd0dc382a9a1f9b02 |

> **Lưu ý quan trọng về khác biệt giao thức giữa `VN001_baseline_2026_01_15` và `VN001_extended_80_20`:**
> Cả hai phạm vi đều dùng cùng trạm `VN001_HANOI_556_NGUYEN_VAN_CU` (9,044 giờ lưới, 7,495 giờ `pm25` hợp lệ), nhưng mốc cắt thời gian khác nhau:
> - `VN001_baseline_2026_01_15` cắt tại `2026-01-15 00:00:00+07:00` (Train gồm mùa Thu–Đông 07/2025–01/2026; Test trải dài Đông–Xuân–Hạ 01–07/2026 có cả đợt ô nhiễm cao lẫn mùa sạch).
> - `VN001_extended_80_20` dùng cột `split` 80/20 chuẩn hóa của Issue #44 (Test bắt đầu từ `2026-05-01 09:00+07:00` rơi trọn vào mùa Hạ mưa nhiều + đợt mất dữ liệu dài 630 giờ), dẫn đến **0 ca dương tính** ở ngưỡng 50.0 µg/m³ (`UNESTIMABLE`).
> Khi truyền cùng mốc cắt và giao thức trên cùng trạm, hai luồng cho kết quả đồng nhất tuyệt đối (được kiểm chứng bởi `tests/test_sensitivity.py`).

## 2. Kiểm Chứng Bất Biến Artifact Baseline (SHA-256 Before/After)

| Artifact | SHA-256 Before | SHA-256 After | Immutable |
| --- | --- | --- | --- |
| air_pollution_final.parquet | 866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd | 866f39de1720c7273dc1f09c4932e508835589383820ad425c19521592586efd | PASS |
| reports/classification_results.md | 80a15f61038d1e57eab9873d0d88486c4dde01756e5ed2e7ca4da6cc68fd0909 | 80a15f61038d1e57eab9873d0d88486c4dde01756e5ed2e7ca4da6cc68fd0909 | PASS |
| reports/regression_results.md | 7dd79d8b1f3d1bf4385c436157109eb853c74ef857c064b7b56cfd6becc8fc46 | 7dd79d8b1f3d1bf4385c436157109eb853c74ef857c064b7b56cfd6becc8fc46 | PASS |

## 3. Độ Nhạy Ngưỡng Cảnh Báo Phân Loại (Task 9.4: 40 / 45 / 50 / 55 µg/m³)

> Chỉ mức **`50.0 µg/m³`** (trung bình trượt 24h) tham chiếu **`QCVN 05:2023/BTNMT (24h reference)`**. Các mức `40.0`, `45.0` và `55.0 µg/m³` là **`technical_sensitivity_threshold`** phục vụ kiểm tra độ nhạy kỹ thuật, **không** phải quy chuẩn pháp lý.

| cohort_name | threshold_ug_m3 | threshold_label | valid_n_train | valid_n_test | prevalence_train | prevalence_test | tuned_prob_threshold | test_pr_auc | test_recall | test_precision | test_f1 | test_f2 | test_far | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | 40.0 | technical_sensitivity_threshold | 2965 | 2302 | 0.4634 | 0.4557 | 0.17 | 0.9991 | 0.9971 | 0.9298 | 0.9623 | 0.9829 | 0.063 | OK |
| VN001_baseline_2026_01_15 | 45.0 | technical_sensitivity_threshold | 2965 | 2302 | 0.3855 | 0.3684 | 0.42 | 0.998 | 0.9894 | 0.9699 | 0.9796 | 0.9854 | 0.0179 | OK |
| VN001_baseline_2026_01_15 | 50.0 | QCVN 05:2023/BTNMT (24h reference) | 2965 | 2302 | 0.3298 | 0.2893 | 0.43 | 0.9989 | 0.9955 | 0.9418 | 0.9679 | 0.9843 | 0.0251 | OK |
| VN001_baseline_2026_01_15 | 55.0 | technical_sensitivity_threshold | 2965 | 2302 | 0.2678 | 0.2328 | 0.26 | 0.9981 | 1.0 | 0.7283 | 0.8428 | 0.9306 | 0.1133 | OK |
| VN003_extended_80_20 | 40.0 | technical_sensitivity_threshold | 10636 | 3439 | 0.4243 | 0.6412 | 0.29 | 0.9998 | 0.9991 | 0.9582 | 0.9782 | 0.9906 | 0.0778 | OK |
| VN003_extended_80_20 | 45.0 | technical_sensitivity_threshold | 10636 | 3439 | 0.3259 | 0.5696 | 0.36 | 0.9996 | 0.9985 | 0.9664 | 0.9822 | 0.9919 | 0.0459 | OK |
| VN003_extended_80_20 | 50.0 | QCVN 05:2023/BTNMT (24h reference) | 10636 | 3439 | 0.2517 | 0.4981 | 0.36 | 0.9995 | 0.9977 | 0.9553 | 0.976 | 0.9889 | 0.0463 | OK |
| VN003_extended_80_20 | 55.0 | technical_sensitivity_threshold | 10636 | 3439 | 0.1981 | 0.4318 | 0.39 | 0.9993 | 0.9987 | 0.9482 | 0.9728 | 0.9881 | 0.0415 | OK |
| VN001_extended_80_20 | 40.0 | technical_sensitivity_threshold | 5025 | 242 | 0.4744 | 0.1612 | 0.23 | 0.998 | 1.0 | 0.7222 | 0.8387 | 0.9286 | 0.0739 | OK |
| VN001_extended_80_20 | 45.0 | technical_sensitivity_threshold | 5025 | 242 | 0.394 | 0.0455 | 0.4 | 0.9842 | 1.0 | 0.7857 | 0.88 | 0.9483 | 0.013 | OK |
| VN001_extended_80_20 | 50.0 | QCVN 05:2023/BTNMT (24h reference) | 5025 | 242 | 0.3272 | 0.0 | 0.47 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.0 | UNESTIMABLE (0 positives in Test) |
| VN001_extended_80_20 | 55.0 | technical_sensitivity_threshold | 5025 | 242 | 0.2647 | 0.0 | 0.5 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.0 | UNESTIMABLE (0 positives in Test) |

## 4. Độ Nhạy Độ Phủ Cửa Sổ Trượt (`min_periods` ∈ {12, 18, 24} tại 50.0 µg/m³)

> Thay đổi đồng bộ `min_periods` cho cả nhãn trung bình trượt 24h và đặc trưng trượt quá khứ 24h (kết thúc ở `t-1`) để đo lường thực chất lượng mẫu thu hồi và độ ổn định hiệu năng.

| cohort_name | min_periods | valid_n_train | valid_n_test | prevalence_train | prevalence_test | tuned_prob_threshold | test_pr_auc | test_recall | test_precision | test_f2 | test_far | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | 12 | 4400 | 3236 | 0.3084 | 0.2376 | 0.42 | 0.9986 | 1.0 | 0.8699 | 0.971 | 0.0466 | OK |
| VN001_baseline_2026_01_15 | 18 | 4183 | 3016 | 0.3029 | 0.243 | 0.4 | 0.9988 | 1.0 | 0.8737 | 0.9719 | 0.0464 | OK |
| VN001_baseline_2026_01_15 | 24 | 2965 | 2302 | 0.3298 | 0.2893 | 0.43 | 0.9989 | 0.9955 | 0.9418 | 0.9843 | 0.0251 | OK |
| VN003_extended_80_20 | 12 | 14027 | 4423 | 0.2656 | 0.4956 | 0.38 | 0.9994 | 0.9977 | 0.9538 | 0.9886 | 0.0475 | OK |
| VN003_extended_80_20 | 18 | 13566 | 4368 | 0.2638 | 0.4991 | 0.36 | 0.9994 | 0.9977 | 0.9481 | 0.9874 | 0.0544 | OK |
| VN003_extended_80_20 | 24 | 10636 | 3439 | 0.2517 | 0.4981 | 0.36 | 0.9995 | 0.9977 | 0.9553 | 0.9889 | 0.0463 | OK |
| VN001_extended_80_20 | 12 | 6912 | 724 | 0.3047 | 0.0276 | 0.42 | 0.9433 | 0.95 | 0.76 | 0.9048 | 0.0085 | OK |
| VN001_extended_80_20 | 18 | 6638 | 561 | 0.3002 | 0.0125 | 0.54 | 0.8163 | 1.0 | 0.7 | 0.9211 | 0.0054 | OK |
| VN001_extended_80_20 | 24 | 5025 | 242 | 0.3272 | 0.0 | 0.47 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.0 | UNESTIMABLE (0 positives in Test) |

## 5. Độ Nhạy Độ Trễ & Cửa Sổ Trượt Trong Hồi Quy OLS + HAC-24 (Task 9.5)

> Mọi biến `lag_*` và `roll_mean_*` được tính strictly-past-only trong nội bộ từng `station_id` trên lưới giờ chuẩn (không bắc cầu qua gap, không lookahead). Các hệ số phản ánh liên hệ quan sát (*associational, ceteris paribus*), không diễn giải nhân quả.

| cohort_name | spec | valid_n_train | valid_n_test | beta_wind_speed | se_wind_speed_hac24 | beta_temperature | beta_relative_humidity | beta_lag_or_roll | test_mae | test_rmse | test_r2 | test_adj_r2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | baseline_no_lag | 4279 | 3216 | -6.0673 | 1.1173 | 0.1664 | 0.0638 | UNESTIMABLE | 37.325 | 41.4604 | -1.954 | -1.9623 |
| VN001_baseline_2026_01_15 | lag_6h | 4064 | 2977 | -4.2423 | 0.7109 | -0.1876 | 0.1935 | 0.4588 | 22.0381 | 26.1903 | -0.2085 | -0.2126 |
| VN001_baseline_2026_01_15 | lag_12h | 4013 | 2961 | -5.8435 | 0.7103 | -0.5898 | 0.0552 | 0.4064 | 21.2588 | 25.9136 | -0.181 | -0.185 |
| VN001_baseline_2026_01_15 | lag_24h | 4013 | 3010 | -6.2912 | 0.8686 | -0.9325 | -0.1234 | 0.5127 | 17.4618 | 22.344 | 0.1316 | 0.1287 |
| VN001_baseline_2026_01_15 | lag_48h | 3910 | 3005 | -6.6427 | 1.0672 | -0.3036 | -0.0377 | 0.2873 | 25.7636 | 29.7637 | -0.6375 | -0.643 |
| VN001_baseline_2026_01_15 | roll_mean_6h | 3768 | 2844 | -2.3291 | 0.396 | -0.9572 | 0.1664 | 0.8202 | 11.2662 | 16.0723 | 0.5419 | 0.5403 |
| VN001_baseline_2026_01_15 | roll_mean_24h | 2965 | 2302 | -4.9506 | 0.648 | -0.9146 | 0.0891 | 0.8147 | 14.1778 | 19.4275 | 0.3541 | 0.3512 |
| VN001_baseline_2026_01_15 | roll_mean_72h | 1929 | 1540 | -7.6881 | 1.1325 | -0.2162 | -0.0159 | 0.7522 | 14.4987 | 19.3298 | 0.2986 | 0.294 |
| VN003_extended_80_20 | baseline_no_lag | 13835 | 4373 | -6.2864 | 0.4482 | -0.238 | -0.348 | UNESTIMABLE | 23.9798 | 32.8238 | 0.1498 | 0.1481 |
| VN003_extended_80_20 | lag_6h | 13427 | 4281 | -3.8848 | 0.2638 | -0.428 | -0.0868 | 0.5042 | 20.2559 | 28.6843 | 0.3489 | 0.3473 |
| VN003_extended_80_20 | lag_12h | 13236 | 4251 | -4.9155 | 0.3438 | -0.4299 | -0.2238 | 0.4069 | 21.5164 | 29.5185 | 0.3132 | 0.3116 |
| VN003_extended_80_20 | lag_24h | 12871 | 4206 | -5.3742 | 0.3967 | -0.4209 | -0.3193 | 0.4028 | 20.3062 | 28.4772 | 0.3589 | 0.3574 |
| VN003_extended_80_20 | lag_48h | 12537 | 4138 | -6.2661 | 0.4433 | -0.4734 | -0.3593 | 0.2409 | 22.7559 | 31.2 | 0.224 | 0.2221 |
| VN003_extended_80_20 | roll_mean_6h | 12844 | 4101 | -1.7564 | 0.1836 | -0.4992 | 0.0402 | 0.8429 | 14.4494 | 21.9748 | 0.6182 | 0.6173 |
| VN003_extended_80_20 | roll_mean_24h | 10636 | 3439 | -2.8267 | 0.3677 | -0.4488 | -0.0393 | 0.8418 | 18.0361 | 25.4391 | 0.4981 | 0.4967 |
| VN003_extended_80_20 | roll_mean_72h | 7030 | 2200 | -3.8789 | 0.4784 | -0.8229 | -0.1893 | 0.8045 | 22.4833 | 30.6291 | 0.3102 | 0.307 |
| VN001_extended_80_20 | baseline_no_lag | 6749 | 746 | -7.2891 | 0.7769 | -0.4541 | -0.1144 | UNESTIMABLE | 15.6255 | 21.1167 | -0.1073 | -0.1209 |
| VN001_extended_80_20 | lag_6h | 6471 | 570 | -4.7282 | 0.5078 | -0.1757 | 0.1179 | 0.5002 | 14.8584 | 20.2674 | -0.2394 | -0.2616 |
| VN001_extended_80_20 | lag_12h | 6409 | 565 | -5.9836 | 0.4877 | -0.2754 | -0.0129 | 0.4132 | 14.6367 | 19.3754 | -0.206 | -0.2277 |
| VN001_extended_80_20 | lag_24h | 6402 | 621 | -6.2651 | 0.5985 | -0.6367 | -0.1324 | 0.5134 | 13.3494 | 17.5798 | 0.0499 | 0.0343 |
| VN001_extended_80_20 | lag_48h | 6294 | 621 | -7.1792 | 0.702 | -0.4181 | -0.1422 | 0.3602 | 14.458 | 19.1719 | -0.0245 | -0.0413 |
| VN001_extended_80_20 | roll_mean_6h | 6118 | 494 | -2.4649 | 0.3106 | -0.4288 | 0.1428 | 0.8259 | 12.3432 | 17.4807 | 0.0053 | -0.0153 |
| VN001_extended_80_20 | roll_mean_24h | 5025 | 242 | -4.1111 | 0.4837 | -0.1413 | 0.0847 | 0.8011 | 10.855 | 14.0424 | 0.0585 | 0.0177 |
| VN001_extended_80_20 | roll_mean_72h | 3416 | 53 | -6.3934 | 0.7845 | 0.4576 | -0.059 | 0.7334 | 9.7869 | 12.0572 | -0.067 | -0.3211 |

## 6. Độ Nhạy Chiều Dài Cửa Sổ Huấn Luyện (50% / 75% / 100% Đuôi Train Trên Test Cố Định)

### 6.1. Phân Loại (50.0 µg/m³, `min_periods=24`)

| cohort_name | train_window_pct | valid_n_train | valid_n_test | tuned_prob_threshold | test_pr_auc | test_recall | test_precision | test_f2 | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | 50 | 1482 | 2302 | 0.2 | 0.9948 | 1.0 | 0.7208 | 0.9281 | OK |
| VN001_baseline_2026_01_15 | 75 | 2224 | 2302 | 0.1 | 0.9981 | 1.0 | 0.7384 | 0.9338 | OK |
| VN001_baseline_2026_01_15 | 100 | 2965 | 2302 | 0.43 | 0.9989 | 0.9955 | 0.9418 | 0.9843 | OK |
| VN003_extended_80_20 | 50 | 5318 | 3439 | 0.43 | 0.9993 | 0.9988 | 0.9543 | 0.9896 | OK |
| VN003_extended_80_20 | 75 | 7977 | 3439 | 0.45 | 0.9995 | 0.9965 | 0.9601 | 0.989 | OK |
| VN003_extended_80_20 | 100 | 10636 | 3439 | 0.36 | 0.9995 | 0.9977 | 0.9553 | 0.9889 | OK |
| VN001_extended_80_20 | 50 | 2512 | 242 | 0.33 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| VN001_extended_80_20 | 75 | 3769 | 242 | 0.29 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |
| VN001_extended_80_20 | 100 | 5025 | 242 | 0.47 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (0 positives in Test) |

### 6.2. Hồi Quy OLS + HAC-24 (9 Biến Gốc)

| cohort_name | train_window_pct | valid_n_train | valid_n_test | beta_wind_speed | se_wind_speed_hac24 | test_mae | test_rmse | test_r2 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | 50 | 2140 | 3216 | -11.8421 | 1.4639 | 24.0174 | 30.7256 | -0.6223 |
| VN001_baseline_2026_01_15 | 75 | 3209 | 3216 | -8.2285 | 1.1253 | 36.2709 | 40.6758 | -1.8433 |
| VN001_baseline_2026_01_15 | 100 | 4279 | 3216 | -6.0673 | 1.1173 | 37.325 | 41.4604 | -1.954 |
| VN003_extended_80_20 | 50 | 6918 | 4373 | -5.8579 | 0.615 | 24.0732 | 34.0942 | 0.0827 |
| VN003_extended_80_20 | 75 | 10376 | 4373 | -5.1319 | 0.4523 | 24.2923 | 33.9101 | 0.0926 |
| VN003_extended_80_20 | 100 | 13835 | 4373 | -6.2864 | 0.4482 | 23.9798 | 32.8238 | 0.1498 |
| VN001_extended_80_20 | 50 | 3374 | 746 | -9.3377 | 0.9954 | 22.1235 | 27.0142 | -0.8122 |
| VN001_extended_80_20 | 75 | 5062 | 746 | -8.7795 | 0.8031 | 16.9994 | 23.3936 | -0.359 |
| VN001_extended_80_20 | 100 | 6749 | 746 | -7.2891 | 0.7769 | 15.6255 | 21.1167 | -0.1073 |

## 7. Độ Nhạy Phân Tầng Theo Mùa Trên Tập Test (Xuân / Hạ / Thu / Đông)

### 7.1. Phân Loại Theo Mùa

| cohort_name | season | valid_n_test | n_test_positive | prevalence_test | test_pr_auc | test_recall | test_precision | test_f2 | test_far | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | Xuân | 1467 | 257.0 | 0.1752 | 0.9982 | 0.9883 | 0.927 | 0.9754 | 0.0165 | OK |
| VN001_baseline_2026_01_15 | Hạ | 0 | 0.0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (empty season stratum in Test) |
| VN001_baseline_2026_01_15 | Thu | 0 | 0.0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (empty season stratum in Test) |
| VN001_baseline_2026_01_15 | Đông | 835 | 409.0 | 0.4898 | 0.9993 | 1.0 | 0.9512 | 0.9898 | 0.0493 | OK |
| VN003_extended_80_20 | Xuân | 782 | 241.0 | 0.3082 | 0.9998 | 1.0 | 0.9488 | 0.9893 | 0.024 | OK |
| VN003_extended_80_20 | Hạ | 0 | 0.0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (empty season stratum in Test) |
| VN003_extended_80_20 | Thu | 1439 | 791.0 | 0.5497 | 0.9997 | 0.9975 | 0.961 | 0.99 | 0.0494 | OK |
| VN003_extended_80_20 | Đông | 1218 | 681.0 | 0.5591 | 0.9992 | 0.9971 | 0.951 | 0.9875 | 0.0652 | OK |
| VN001_extended_80_20 | Xuân | 242 | 0.0 | 0.0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.0 | UNESTIMABLE (0 positives in Test) |
| VN001_extended_80_20 | Hạ | 0 | 0.0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (empty season stratum in Test) |
| VN001_extended_80_20 | Thu | 0 | 0.0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (empty season stratum in Test) |
| VN001_extended_80_20 | Đông | 0 | 0.0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (empty season stratum in Test) |

### 7.2. Hồi Quy Theo Mùa

| cohort_name | season | valid_n_test | test_mae | test_rmse | test_r2 | mean_bias | status |
| --- | --- | --- | --- | --- | --- | --- | --- |
| VN001_baseline_2026_01_15 | Xuân | 2042 | 38.1602 | 41.7814 | -3.8492 | 36.5317 | OK |
| VN001_baseline_2026_01_15 | Hạ | 152 | 27.8565 | 32.2512 | -0.4454 | 15.6483 | OK |
| VN001_baseline_2026_01_15 | Thu | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (empty season stratum in Test) |
| VN001_baseline_2026_01_15 | Đông | 1022 | 37.0643 | 42.0303 | -1.1208 | 30.9711 | OK |
| VN003_extended_80_20 | Xuân | 930 | 19.2238 | 27.2892 | -0.0301 | 5.3294 | OK |
| VN003_extended_80_20 | Hạ | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (empty season stratum in Test) |
| VN003_extended_80_20 | Thu | 1864 | 21.616 | 30.388 | 0.1193 | -7.7923 | OK |
| VN003_extended_80_20 | Đông | 1579 | 29.5713 | 38.1459 | 0.1322 | -4.4448 | OK |
| VN001_extended_80_20 | Xuân | 594 | 13.726 | 18.6591 | -0.0972 | -2.0938 | OK |
| VN001_extended_80_20 | Hạ | 152 | 23.0486 | 28.7737 | -0.1505 | -7.2695 | OK |
| VN001_extended_80_20 | Thu | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (empty season stratum in Test) |
| VN001_extended_80_20 | Đông | 0 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE (empty season stratum in Test) |

## 8. Độ Nhạy Nội Suy Phái Sinh (`pm25_derived_interpolated`, Chỉ Trên Train)

> Nội suy khoảng trống ngắn (`pm25_derived_interpolated`) chỉ được phép sử dụng trên tập Train; tập Test ground-truth (`pm25` quan trắc gốc) và `X_test` được khóa cứng bất biến (`test_ground_truth_unchanged = True`).

| cohort_name | task_type | valid_n_train_obs | valid_n_train_der | recovered_train_rows | valid_n_test | test_mae_obs | test_mae_der | delta_test_mae | test_rmse_obs | test_rmse_der | delta_test_rmse | test_pr_auc_obs | test_pr_auc_der | delta_test_pr_auc | test_ground_truth_unchanged | status |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| VN003_extended_80_20 | regression | 13835 | 13985 | 150 | 4373 | 23.9798 | 23.9901 | 0.0103 | 32.8238 | 32.8289 | 0.0051 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | True | OK |
| VN003_extended_80_20 | classification | 10636 | 10702 | 66 | 3439 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | 0.9995 | 0.9995 | 0.0 | True | OK |
| VN001_extended_80_20 | regression | 6749 | 6866 | 117 | 746 | 15.6255 | 15.6435 | 0.018 | 21.1167 | 21.137 | 0.0203 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | True | OK |
| VN001_extended_80_20 | classification | 5025 | 5051 | 26 | 242 | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | UNESTIMABLE | True | UNESTIMABLE (0 positives in Test) |
