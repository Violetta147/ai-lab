---
name: learned-yarp-routing
description: "Ensure YARP gateway route prefixes match backend controller routes to prevent 404s during E2E testing."
---

# YARP Gateway Routing Mismatch

**Context:** Khi cấu hình YARP API Gateway (BFF) dùng `PathRemovePrefix` để trỏ về các Microservices.

## Problem
Nếu Postman test trực tiếp vào Microservice (VD: `http://localhost:5000/api/Orders`) thay vì đi qua Gateway (`http://localhost:5200/api/ordering/Orders`), nó sẽ báo lỗi 404 Not Found nếu Controller trong code chỉ cấu hình `[Route("[controller]")]`. Hệ quả là Gateway và Microservice bị lệch tiền tố (prefix).

## Solution
1. **Đồng bộ Route Attribute:** Luôn đảm bảo Controller route có chứa tiền tố `api/` (VD: `[Route("api/[controller]")]`) nếu hệ thống mong đợi URL có `/api/`.
2. **Thói quen Testing:** Postman E2E Testing nên gọi trực tiếp qua URL của Gateway (`http://localhost:5200/api/ordering`) để đảm bảo luồng routing giống 100% với Frontend gọi thực tế, tránh các lỗi bypass 404 giả.

## When to Use
Áp dụng khi fix lỗi 404 Not Found trên .NET Microservices đằng sau YARP Gateway.
