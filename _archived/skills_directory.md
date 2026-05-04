# Skills directory — tổng hợp repo GitHub & thư mục skill

Tài liệu này gom thông tin từ: file memory OpenClaw (`C:\Users\violet\.openclaw\workspace\memory\`), transcript session (toàn bộ file trong `C:\Users\violet\.openclaw\agents\main\sessions\`, gồm `*.jsonl`, `*.jsonl.reset.*`, `*.jsonl.deleted.*`, `sessions.json`), và phần tổng hợp đã làm trong hội thoại.

**Ngày ghi:** 2026-04-12

---

## Thư mục skill cục bộ (Windows)

| Mục đích | Đường dẫn |
|----------|-----------|
| Skill đã cài (ClawHub / tải tay) | `C:\Users\violet\.agents\skills\` |
| Skill trong workspace OpenClaw | `C:\Users\violet\.openclaw\workspace\.agents\skills\` |

Theo `AGENTS.md` của OpenClaw, session startup đọc `memory/YYYY-MM-DD.md` (hôm nay + hôm qua) và `MEMORY.md` (main session); file daily có thể đặt tên theo chủ đề, ví dụ `memory/2026-04-10-backend-patterns.md`.

---

## Skill đã ghi nhận trong memory (cài vào `.agents\skills`)

Các thư mục skill (mỗi cái có `SKILL.md`, thường kèm `_meta.json`):

| Thư mục skill | Ghi chú ngắn |
|---------------|--------------|
| `amaofx-filesystem` | Thao tác filesystem |
| `office-document-specialist-suite` | Office (Python: `ods.py`, `requirements.txt`, `setup.sh`) |
| `backend-patterns` | Pattern backend Node.js / Express / Next.js API |
| `auto-test-generator` | Sinh test (`index.js`, `package.json`) |
| `academic-writing` | Viết học thuật |

Nguồn cài: repo **`openclaw/skills`** trên GitHub (một số skill chưa publish đầy đủ lên ClawHub).

---

## Repo GitHub — danh sách đã chuẩn hóa (org/repo)

Các URL dưới đây xuất hiện trong transcript session OpenClaw (đã gộp trùng `.git` / biến thể). Một số là kết quả **web search / web fetch** trong session, không nhất thiết là repo bạn đã clone.

### Trọng tâm: Copilot, Microsoft, .NET, OpenClaw

| Repo | Mô tả ngắn |
|------|------------|
| https://github.com/github/awesome-copilot | Awesome GitHub Copilot — agents (ví dụ Task Planner, Thinking Beast Mode), skills, instructions |
| https://github.com/dotnet/skills | Skills .NET / C# cho coding agent |
| https://github.com/microsoft/skills | Agent Skills Microsoft (`Agents.md`, plugins theo ngôn ngữ) |
| https://github.com/microsoft/MMCTAgent | Multi-modal Critical Thinking Agent (xuất hiện khi search “planner / thinking”) |
| https://github.com/microsoft/agent-framework | Microsoft Agent Framework (samples workflow) |
| https://github.com/microsoft/ai-agents-for-beginners | Tài liệu / README agents cho người mới |
| https://github.com/openclaw/skills | Registry skill OpenClaw (đường dẫn `skills/<author>/<name>/`) |

### Composio & OpenClaw

| Repo | Mô tả ngắn |
|------|------------|
| https://github.com/ComposioHQ/composio | Composio CLI / SDK |
| https://github.com/ComposioHQ/openclaw-composio | Fork / plugin tích hợp Composio với OpenClaw |

### Skill riêng lẻ (trùng với openclaw/skills)

| Repo |
|------|
| https://github.com/amaofx/filesystem |
| https://github.com/autogame-17/auto-test-generator |
| https://github.com/charmmm718/backend-patterns |
| https://github.com/robert-janssen/office-document-specialist-suite |
| https://github.com/teamolab/academic-writing |

### Danh sách / curated “awesome”

| Repo | Mô tả ngắn |
|------|------------|
| https://github.com/VoltAgent/awesome-openclaw-skills | Danh sách skill OpenClaw |
| https://github.com/heilcheng/awesome-agent-skills | Awesome agent skills |
| https://github.com/jim-schwoebel/awesome_ai_agents | Awesome AI agents |
| https://github.com/weitianxin/Awesome-Agentic-Reasoning | Agentic reasoning |
| https://github.com/wshobson/agents | Tài liệu agents / agent-skills |

### Khác (xuất hiện trong transcript)

| Repo | Ghi chú |
|------|---------|
| https://github.com/JoshLuedeman/teamwork | Có file `planner.agent.md` (kết quả search, không phải repo Microsoft chính thức) |
| https://github.com/agenticsorg/quantum-agentics | Repo có từ khóa “quantum” trong kết quả tìm |
| https://github.com/K-Dense-AI/claude-scientific-skills | Claude scientific skills |
| https://github.com/apache/airflow | Tham chiếu `AGENTS.md` trong nội dung fetch (ví dụ) |
| https://github.com/acme-org/acme-api | Có thể là ví dụ/issue trong transcript |

---

## Liên kết cụ thể (file / trang hay dùng)

- Awesome Copilot — repo gốc: https://github.com/github/awesome-copilot  
- Ví dụ agent “Thinking Beast Mode”: https://github.com/github/awesome-copilot/blob/main/agents/Thinking-Beast-Mode.agent.md  
- Task planner (awesome-copilot): https://github.com/github/awesome-copilot/blob/main/agents/task-planner.agent.md  
- Microsoft skills — `Agents.md`: https://github.com/microsoft/skills/blob/main/Agents.md  
- OpenClaw skills — cây thư mục: https://github.com/openclaw/skills/tree/main/skills  

---

## Ghi chú về memory vs file JSONL

- File trong **`memory/*.md`** thường là **tóm tắt** session sau `/new` hoặc `/reset`, không phải full transcript. Vì vậy nhiều URL chỉ xuất hiện trong **`.jsonl` / `.jsonl.reset`**, không được copy vào memory.
- Trong memory đã xác nhận có URL dạng: `https://github.com/microsoft/skills`.
- Chuỗi **`openclaw/skills`** (repo skill OpenClaw) thường **không** kèm full URL trong memory; URL chuẩn: `https://github.com/openclaw/skills`.

---

## Trang không phải GitHub nhưng liên quan skill

- ClawHub / discovery skill: https://clawskills.sh/

---

*Tệp được tạo theo yêu cầu: đặt trong thư mục `agents`, tên nội dung `skills_directory.md`.*
