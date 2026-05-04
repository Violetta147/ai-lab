---
name: learned-docker-service-names
description: "Use the compose service name (e.g. ordering.api), not the container_name, when building specific services."
---

# Docker Compose Service Name vs Container Name

**Context:** Khi muốn build lại hoặc restart một service cụ thể trong cụm Docker Compose.

## Problem
Lệnh `docker-compose up -d --build lms-ordering-api` văng lỗi `no such service: lms-ordering-api`. Nguyên nhân là do Docker Compose yêu cầu sử dụng **tên định danh service** trong file YAML (dưới block `services:`), chứ không chấp nhận `container_name`.

## Solution
Luôn mở file `docker-compose.yml` ra và tìm tên gốc của service.
Ví dụ:
```yaml
services:
  ordering.api:  # <--- DÙNG TÊN NÀY CHO docker-compose
    container_name: lms-ordering-api # <--- KHÔNG DÙNG TÊN NÀY
```
Lệnh đúng: `docker-compose up -d --build ordering.api`

## When to Use
Khi cần troubleshooting lỗi "no such service" khi tương tác với docker-compose CLI.
