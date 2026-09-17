# BÁO CÁO TỔNG HỢP CÁC THAY ĐỔI VÀ TÍNH NĂNG MỚI (xTS REPORT GENERATOR)

> **Repository:** [https://github.com/PhamDuc001/GenerateReport_xTS.git](https://github.com/PhamDuc001/GenerateReport_xTS.git)  
> **Branch:** `main`  
> **File chính:** `ReportGenerator.py`  
> **Thời gian cập nhật:** Tháng 09/2026  

---

## I. TỔNG QUAN MỤC TIÊU CẢI TIẾN

Tool ban đầu (`ReportGenerator.py`) có nhiệm vụ tự động giải nén, thu thập kết quả kiểm thử (XML/HTML), tạo cấu trúc thư mục báo cáo chuẩn (`00.Internal`, `00.OEM_APFE`, `00.OEM_APFE_UPLOAD`) và nén zip kết quả cho các bộ kiểm thử Android xTS (CTS, STS, VTS, CTSonGSI, CTS_Verifier...).

Tuy nhiên, mã nguồn gốc gặp các hạn chế sau:
1. **Thiếu kiểm tra tính toàn vẹn dữ liệu đầu vào:** Chưa kiểm tra tính tương ứng giữa thư mục kết quả và file nén `.zip`, cũng như chưa đối chiếu sự đồng bộ giữa thư mục `results/` và `logs/`.
2. **Dễ phát sinh lỗi do file/folder rác:** Sự tồn tại của các symlink/folder tạm như `lastest` hoặc `latest` làm sai lệch logic sắp xếp thời gian session hoặc gây báo lỗi sai.
3. **Quản lý log phân tán và trôi lỗi:** Lỗi phát sinh trong quá trình chạy chỉ được `print()` ra console rồi trôi đi, người dùng không nắm được trước khi ấn xác nhận đổi tên/nén file `(Y/N)`.
4. **Lỗi hệ quả dây chuyền & trùng lặp log:** Khi thiếu file zip, nhiều hàm độc lập cùng cố copy và cùng ghi nhận lỗi trùng lặp, gây loãng báo cáo.
5. **Giao diện dòng lệnh (CLI) chưa trực quan:** Log lỗi không có màu sắc cảnh báo, các comment và thông báo còn pha trộn ngôn ngữ.

Toàn bộ các hạn chế trên đã được tái cấu trúc, chuẩn hóa và bổ sung giải pháp toàn diện.

---

## II. BẢNG SO SÁNH NHANH TRƯỚC VÀ SAU CẢI TIẾN

| Hạng mục | Source gốc ban đầu | Phiên bản hiện tại sau cải tiến |
| :--- | :--- | :--- |
| **Quản lý log lỗi** | Dùng `print()` phân tán, không lưu lại; log trôi đi khi chạy xong. | Tập trung qua `log_fail()`, gom vào `failed_logs = []`. |
| **Báo cáo lỗi trước khi nén** | Hỏi luôn `(Y/N)` dù quá trình chạy có phát sinh lỗi hay không. | Hiển thị bảng tổng hợp **`FAILED LOGS SUMMARY`** trước dòng `(Y/N)`. |
| **Kiểm tra cặp Folder - Zip** | Không kiểm tra. Nếu thiếu zip hoặc thiếu folder giải nén thì bỏ qua. | Kiểm tra 1-1 giữa folder session và file `.zip` tương ứng (`results/` và `CTS_Verifier`). |
| **Xử lý `CTS_Verifier`** | Dùng chung hoặc không có logic kiểm tra riêng. | Kiểm tra trực tiếp tại root `CTS_Verifier/` (không có `results/`, bỏ qua `logs/`). |
| **Xử lý folder rác `lastest`/`latest`** | Giữ nguyên gây lỗi phân tích thời gian và báo thiếu `.zip`. | Tự động quét và xóa sạch symlink/folder `lastest` trong cả `results/` và `logs/`. |
| **Đối chiếu `results/` và `logs/`** | Không kiểm tra thư mục `logs/`. | Kiểm tra khớp 1-1 session folder giữa `results/` và `logs/` (ở cả suite cha và `single/`). |
| **Định dạng hiển thị lỗi** | In text trắng thông thường, khó phân biệt với log info. | Tự động gắn nhãn **`fail` (màu đỏ ANSI)** ở cuối câu, đồng bộ với nhãn `... success`. |
| **Xử lý trùng lặp log lỗi** | Bị lặp lỗi copy zip 2 lần ở `MakeOemApfe` và `MakeOemApfeUpload`. | Kiểm tra tồn tại trước khi copy, lọc trùng lặp trong `failed_logs` (Deduplication). |
| **Chuẩn hóa ngôn ngữ** | Pha trộn tiếng Việt có dấu, không dấu và tiếng Anh. | 100% comment mã nguồn, docstrings, print statements dùng **tiếng Anh**. |
| **Quản lý mã nguồn** | Chưa khởi tạo Git. | Đã khởi tạo Git repo, cấu hình `.gitignore` và đồng bộ lên GitHub remote. |

---

## III. CHI TIẾT CÁC TÍNH NĂNG VÀ LOGIC MỚI

### 1. Thu thập log lỗi tập trung & Hiển thị tóm tắt (`FAILED LOGS SUMMARY`)
- **Vị trí logic:** Hàm `log_fail(*args, **kwargs)` và `rename_and_zip_xts_folders(base_path)`.
- **Cơ chế hoạt động:**
  - Mọi thao tác gặp ngoại lệ (file not found, corrupt zip, key error...) đều gọi qua hàm `log_fail()`.
  - Toàn bộ nội dung lỗi được lưu vào danh sách `failed_logs`.
  - Trước khi yêu cầu người dùng nhập `(Y/N)` để đổi tên và nén `01.xxx`, hệ thống in bảng tổng kết:
    ```text
    ===============================================================================================
    !!!!!!!!!!!!!!!!!!!!!!!! FAILED LOGS SUMMARY !!!!!!!!!!!!!!!!!!!!!!!!
    Total failed logs detected: 2
      [1] [CTSonGSI/single/10.CtsCarTestCases_01/results] Folder '2026.09.15_11.38.57.870_5136' is missing zip file: '2026.09.15_11.38.57.870_5136.zip' fail
      [2] [CTSonGSI/single/10.CtsCarTestCases_01/results] Zip file '2026.09.15_11.38.57.870_513.zip' is missing folder: '2026.09.15_11.38.57.870_513' fail
    ===============================================================================================
    Do you want to rename + zip folders in: /path/to/01.Full
    (Y/N): 
    ```

---

### 2. Kiểm tra tính toàn vẹn cặp Folder - Zip (`check_folder_zip_pairs`)
- **Vị trí logic:** Hàm `check_folder_zip_pairs(target_dir, context_label)`.
- **Cơ chế hoạt động:**
  - Quét toàn bộ thư mục `results/` của từng suite (hoặc `single/<module>/results`):
    - **Lỗi 1:** Folder session `X` tồn tại nhưng không tìm thấy file `X.zip` $\rightarrow$ Báo lỗi `Folder 'X' is missing zip file: 'X.zip'`.
    - **Lỗi 2:** File `X.zip` tồn tại nhưng không có folder `X` giải nén $\rightarrow$ Báo lỗi `Zip file 'X.zip' is missing folder: 'X'`.
    - **Lỗi 3:** Thư mục rỗng (không có kết quả) $\rightarrow$ Báo lỗi thư mục rỗng.
  - **Quy tắc đặc thù cho `CTS_Verifier`:**
    - Cấu trúc `CTS_Verifier` không chứa thư mục con `results/` mà chứa trực tiếp folder kết quả và file zip tại thư mục gốc `CTS_Verifier/`.
    - Tool tự động nhận diện và kiểm tra cặp folder-zip trực tiếp tại đây, không kiểm tra thư mục `logs/` (và loại trừ cho `ATS_Verifier`).

---

### 3. Tự động dọn dẹp các thư mục/symlink không hợp lệ (`lastest`/`latest`)
- **Vị trí logic:** `is_valid_result_name()`, `clean_invalid_results_items()`, `check_and_clean_logs_folder()`, `clean_all_logs_in_base_path()`.
- **Cơ chế hoạt động:**
  - Định nghĩa định dạng chuẩn của session kiểm thử xTS thông qua biểu thức chính quy:
    $$\text{Regex: } \verb|^\d{4}\.\d{2}\.\d{2}_\d{2}\.\d{2}\.\d{2}| \quad (\text{Ví dụ: } 2026.09.15\_11.38.57)$$
  - Tự động phát hiện và xóa bỏ (`os.unlink` nếu là symlink, `shutil.rmtree` nếu là thư mục) các mục mang tên `lastest`, `latest` hoặc bất kỳ thư mục nào không đúng chuẩn timestamp.
  - Tự động áp dụng cho cả thư mục `results/` và toàn bộ các thư mục `logs/` trong toàn bộ cây thư mục workspace.

---

### 4. Kiểm tra khớp 1-1 giữa thư mục `results/` và `logs/` (`check_results_logs_matching`)
- **Vị trí logic:** Hàm `check_results_logs_matching(results_dir, logs_dir, context_label)`.
- **Cơ chế hoạt động:**
  - Đối chiếu danh sách các folder session hợp lệ giữa `results/` và `logs/`:
    - **Trường hợp 1:** Session có trong `results/` nhưng thiếu trong `logs/`:
      $$\text{Báo lỗi: } \verb|[<suite>] Session folder 'X' in results/ is missing in logs/ fail|$$
    - **Trường hợp 2:** Session có trong `logs/` nhưng thiếu trong `results/`:
      $$\text{Báo lỗi: } \verb|[<suite>] Session folder 'X' in logs/ is missing in results/ fail|$$
  - Phạm vi áp dụng:
    - Suite kiểm thử tổng hợp ngoài: `<suite>/results` $\longleftrightarrow$ `<suite>/logs`.
    - Suite kiểm thử đơn lẻ trong single: `<suite>/single/<module>/results` $\longleftrightarrow$ `<suite>/single/<module>/logs`.

---

### 5. Giao diện trực quan với thẻ `fail` màu đỏ ANSI
- **Vị trí logic:** Cấu hình ANSI Windows và định dạng chuỗi trong `log_fail()`.
- **Cơ chế hoạt động:**
  - Gọi lệnh `os.system('')` trên nền tảng Windows để bật tính năng hỗ trợ mã thoát ANSI VT100 trên Command Prompt và PowerShell.
  - Định nghĩa hằng số mã màu:
    ```python
    COLOR_RED = "\033[91m"
    COLOR_RESET = "\033[0m"
    FAIL_TAG = f"{COLOR_RED}fail{COLOR_RESET}"
    ```
  - Mọi dòng thông báo lỗi ghi nhận qua `log_fail()` đều tự động được gắn nhãn `fail` (màu đỏ) ở cuối câu.
  - Tương thích thẩm mỹ với các dòng copy thành công kết thúc bằng `... success`:
    ```text
    Created Report Struct
    [CTS/single/04.CtsHostsideNetworkTests] Session folder '2026.09.12_09.28.46.050_7063' in logs/ is missing in results/ fail
    [STS] Session folder '2026.09.15_08.53.40' in results/ is missing in logs/ fail
    [STS] Session folder '2026.09.15_08.53.41' in logs/ is missing in results/ fail
    Copy 12.CtsAccessibilityServiceTestCases.xml file success
    Copy 04.CtsHostsideNetworkTests.xml file success
    ```

---

### 6. Triệt tiêu lỗi hệ quả dây chuyền & Khử trùng lặp log (Deduplication)
- **Vấn đề trước đây:**
  - Khi folder và zip bị lệch tên (ví dụ folder `..._5136` nhưng file zip là `..._513.zip`):
    - Đã có log cảnh báo lệch tên từ `check_folder_zip_pairs`.
    - Nhưng sau đó, hàm `MakeOemApfe` và `MakeOemApfeUpload` vẫn cố tìm và copy file zip không tồn tại `..._5136.zip`.
    - Dẫn đến phát sinh thêm 2 dòng lỗi thừa: `Source file ..._5136.zip not found fail`.
- **Giải pháp cải tiến:**
  1. **Kiểm tra tồn tại trước khi copy:**
     - Trong `MakeOemApfe` và `MakeOemApfeUpload`, bổ sung điều kiện:
       ```python
       if 'zip' in dict[i][j] and os.path.exists(dict[i][j]['zip']):
           CopyFile(dict[i][j]['zip'], ...)
       ```
     - Nếu file zip không tồn tại (đã được cảnh báo ở bước check cặp), tool sẽ bỏ qua không cố copy $\rightarrow$ triệt tiêu hoàn toàn 2 dòng log thừa.
     - Vẫn giữ nguyên logic bắt lỗi `Source file ... not found` đối với XML/HTML/Template để đảm bảo không bị sót lỗi thiếu file báo cáo thực sự.
  2. **Khử trùng lặp log trong `failed_logs`:**
     - Bổ sung điều kiện kiểm tra `if formatted_msg not in failed_logs:` trước khi `append()`.
     - Đảm bảo trong bảng `FAILED LOGS SUMMARY`, mỗi lỗi chỉ hiển thị 1 lần duy nhất, không bị trùng lặp.

---

### 7. Chuẩn hóa 100% ngôn ngữ tiếng Anh
- Toàn bộ comment giải thích code (`#`).
- Docstrings mô tả chức năng của tất cả các hàm mới.
- Toàn bộ chuỗi thông báo in ra terminal và prompt hỏi `(Y/N)` được dịch chuẩn hóa sang tiếng Anh.

---

## IV. DANH SÁCH COMMITS TRÊN REPOSITORY

| Commit Hash | Thông điệp Commit (Commit Message) | Nội dung thay đổi chính |
| :--- | :--- | :--- |
| `1135bd5` | *Initial commit: GenerateReport tool for xTS with failed log collector* | Khởi tạo Git repo, tạo `.gitignore`, bổ sung `log_fail` và xuất bảng tổng hợp lỗi trước `(Y/N)`. |
| `435942b` | *feat: validate folder and zip pairs in results and CTS_Verifier* | Thêm hàm `check_folder_zip_pairs` kiểm tra 1-1 folder và zip trong `results/` và `CTS_Verifier`. |
| `b8bd80e` | *fix: auto remove invalid non-timestamp folders (like lastest) in results/* | Tự động phát hiện và xóa folder/symlink `lastest` không đúng định dạng timestamp trong `results/`. |
| `84e6052` | *fix: auto remove lastest/latest and validate YYYY.MM.DD_HH.MM.SS in logs/ folders* | Mở rộng tự động dọn dẹp `lastest` và kiểm tra timestamp cho toàn bộ thư mục `logs/`. |
| `7287ec6` | *refactor: translate all comments, logs and terminal prints to English* | Chuẩn hóa toàn bộ comment mã nguồn, log và terminal prompt sang tiếng Anh. |
| `e4fbcd4` | *feat: validate 1-to-1 session folder matching between results/ and logs/* | Thêm hàm `check_results_logs_matching` đối chiếu 1-1 session giữa `results/` và `logs/`. |
| `2198518` | *feat: append red 'fail' badge to failure logs* | Bật ANSI Windows terminal, gắn thẻ `fail` màu đỏ nổi bật ở cuối mỗi dòng log lỗi. |
| `cc56206` | *fix: prevent cascading missing zip copy errors and deduplicate failed logs* | Kiểm tra tồn tại trước khi copy zip (triệt tiêu log thừa) và chống trùng lặp trong `failed_logs`. |

---

## V. KẾT LUẬN

Sau các đợt cải tiến, `ReportGenerator.py` hiện tại đạt được:
- **Độ tin cậy cao (Robustness):** Kiểm soát chặt chẽ toàn bộ tính toàn vẹn của dữ liệu đầu vào (cặp folder-zip, sự khớp 1-1 giữa kết quả và log).
- **Tự động hóa thông minh (Self-cleaning):** Tự động dọn dẹp các thư mục rác do bộ test sinh ra (`lastest`, `latest`) mà không cần người dùng thao tác thủ công.
- **Trải nghiệm người dùng rõ ràng (Clear UX/CLI):** Nhận diện lỗi ngay lập tức nhờ màu sắc đỏ ANSI; bảng tổng hợp đầy đủ, không trùng lặp và xuất hiện đúng thời điểm trước khi người dùng thực hiện thao tác nén/đổi tên quan trọng.
