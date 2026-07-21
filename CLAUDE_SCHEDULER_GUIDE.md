# HƯỚNG DẪN VẬN HÀNH HỆ THỐNG CLAUDE CODE SCHEDULER

Tài liệu này cung cấp toàn bộ thông tin về mục đích, cơ chế hoạt động, hướng dẫn cài đặt và vận hành hệ thống tự động làm mới hạn mức (wake-up scheduler) đa tài khoản Claude Code CLI cho doanh nghiệp.

---

## 1. Giới thiệu chung & Mục tiêu

*   **Tên dự án:** Claude Code Multi-Account Wake-up Scheduler (cswap-scheduler)
*   **Mục tiêu:** Tự động gửi tin nhắn "đánh thức" (ping) ngắn tới danh sách tài khoản **Claude Code CLI** vào lúc **05:00 sáng hàng ngày**.
*   **Tại sao cần thiết?** Hạn mức sử dụng (rate limit) của Claude hoạt động theo cơ chế cửa sổ cuốn 5 giờ (rolling 5-hour window). Việc đánh thức tài khoản sớm giúp kích hoạt trước chu kỳ reset, đảm bảo khi nhân sự vào làm việc lúc **10:00 sáng**, toàn bộ tài khoản đều đạt trạng thái **100% hạn mức trống** để làm việc hiệu quả nhất.

---

## 2. Cơ chế hoạt động (Workflow)

```
[Máy chủ VPS]
      │
      ├── (05:00 Sáng) ──> Kích hoạt tiến trình Daemon chạy ngầm
      │
      ├── Đọc danh sách tài khoản thực tế từ cơ sở dữ liệu `cswap`
      │
      ├── Chạy vòng lặp qua từng tài khoản:
      │         │
      │         ├── Trì hoãn ngẫu nhiên 30s - 120s (Jitter) để tránh gửi đồng loạt
      │         │
      │         └── Gửi lệnh: cswap run <ID> -- claude "Hello Claude..."
      │
      └── Lưu nhật ký kết quả vào file logs/wakeup.log
```

---

## 3. Thông số tiêu hao tài nguyên trên Server

Hệ thống được thiết kế dạng bất đồng bộ (Asynchronous Event Loop), tiêu tốn cực kỳ ít tài nguyên:
*   **Dung lượng ổ cứng:** **17 MB** (bao gồm mã nguồn, logs và thư viện Python).
*   **Bộ nhớ RAM:**
    *   *Trạng thái chờ:* **15 - 20 MB** RAM.
    *   *Trạng thái hoạt động (1-2 phút lúc 5h sáng):* **60 - 80 MB** RAM.
*   **Vi xử lý (CPU):** **0% CPU** lúc chờ, peak tối đa **2% - 5%** của một nhân CPU trong vài giây khi gửi tin nhắn.
*   **Băng thông mạng:** Tiêu thụ cực ít (dưới **5 MB dữ liệu / tháng** cho 10 tài khoản).

---

## 4. Hướng dẫn vận hành dành cho Thành viên / Lập trình viên

Mỗi lập trình viên khi được cấp quyền sử dụng tài khoản chỉ cần thực hiện 2 bước đơn giản để cấu hình:

### Bước 1: SSH kết nối vào Server công ty
Mở Terminal trên máy cá nhân và gõ:
```bash
ssh zstack@103.237.147.91
# Nhập mật khẩu được cấp: zstackai@010205
```

### Bước 2: Đăng nhập tài khoản Claude của bạn lên Server
1.  Gõ lệnh đăng nhập:
    ```bash
    claude
    ```
2.  Màn hình sẽ hiển thị một đường link kích hoạt (URL) kèm mã code gồm 8 ký tự.
3.  Copy đường link đó, dán lên trình duyệt trên máy tính cá nhân của bạn, đăng nhập tài khoản Claude của bạn và nhấn **Approve/Xác nhận**.
4.  Khi màn hình Terminal trên Server báo đăng nhập thành công, chạy lệnh sau để lưu tài khoản vào danh sách quản lý:
    ```bash
    /home/zstack/.local/bin/cswap add
    ```
*(Hệ thống sẽ tự động cập nhật và đưa tài khoản của bạn vào lịch quét tự động ngày hôm sau mà không cần restart lại Server).*

---

## 5. Hướng dẫn dành cho Quản trị viên (Admin)

### Quản lý dịch vụ lập lịch chạy ngầm (Systemd Service)
Dịch vụ được quản lý tự động qua `systemctl` trên Ubuntu:
*   **Kiểm tra trạng thái hoạt động:**
    ```bash
    sudo systemctl status claude-scheduler
    ```
*   **Khởi động dịch vụ:**
    ```bash
    sudo systemctl start claude-scheduler
    ```
*   **Dừng dịch vụ:**
    ```bash
    sudo systemctl stop claude-scheduler
    ```
*   **Khởi động lại dịch vụ (khi thay đổi giờ chạy trong config.json):**
    ```bash
    sudo systemctl restart claude-scheduler
    ```

### Theo dõi Nhật ký (Logs)
Quản trị viên có thể theo dõi tiến trình chạy và phản hồi của Claude thông qua file log:
```bash
# Xem 50 dòng log gần nhất
tail -n 50 /home/zstack/claude-code-scheduler/logs/wakeup.log

# Theo dõi log thời gian thực
tail -f /home/zstack/claude-code-scheduler/logs/wakeup.log
```
