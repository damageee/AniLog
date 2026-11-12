# AniLog / Bangumi — Project Instructions

## Project
AniLog is a Flet anime watch-log app. Keep changes consistent with the
existing view patterns. Do not touch data/storage/app/routes unless asked.

## Stack & checks
- Flet 1.0.5, Python 3.14, virtualenv at `.venv`.
- Compile: `& ".\.venv\Scripts\python.exe" -m compileall -q bangumi main.py`
- Import: `& ".\.venv\Scripts\python.exe" -c "import bangumi.views, bangumi.app"`
- Startup (only if needed): `flet run -v -n main.py`.

## Conventions
- Views live in `bangumi/views/`; prefer `common.py` helpers such as
  `vertical_page`, `page_padding`, `foreground_color`, `background_color`.
- Register new detail kinds in `detail_kinds.py` and `catalog.py`, and export
  public kinds from `views/__init__.py`.
- Data logic: `watched_data.py`; preferences: `preferences.py`.
- Never modify `storage/`, `app.py`, or routes unless explicitly requested.

## Working agreement
- Treat each instruction as a standalone checkpoint. Do not read
  `chat_history.txt` or rely on prior chat history unless explicitly asked.
- Prefer targeted grep and local reads; avoid reading whole files.
- Keep tests to a smoke test: compile + imports. Run the app only if needed;
  the user manually verifies UI.
- Keep the final summary to 100–200 Chinese characters; no long code dumps.
- If blocked, ambiguous, or a change is risky, say so in large red text:
  `<span style="color:red;font-size:1.6em">...</span>`
- **日志脱敏与截断 (Log Truncation):** 绝对不要把完整的终端（Terminal）
  报错日志或庞大编译输出加入上下文。如果遇到报错，只提取前 10 行和后 10
  行，或者提取报错的“核心错误名（Error Type）”和“具体行号”进行修复。
- **禁止擅自扩充范围 (Strict Scope):** 严格按照提供的修改意见和指定的文件
  执行。在未明确要求的情况下，绝对不要重写整个文件，不要改动其他未提及的
  文件，也不要擅自引入新的第三方库。
- **遇错即停 (Stop on Failure):** 如果执行编译或 `import` 检查时发生报错，
  不要自行开启无限试错循环（Infinite Retry）。尝试修复 1 次仍失败，请立即
  停止并输出“需要人工介入”的警告。
- **职责边界 (No Runtime Debugging):** 只负责按指令修改代码，并保证
  `compileall` 与 `import` 检查不报错；不要实际运行程序或自行调试。用户会
  自行测试，出现问题后再交由你调试。
- **完成回报 (Completion Reports):** 每完成一项任务，在最终回复前使用
  `session_send` 向派发任务的会话（如 ses_e2fe3）发送一句简要的完成消息，
  包含任务名与检查结果。不要使用 `session_broadcast`，也不要发送协调或警告
  消息；若发现文件可能被其他会话改动，只在最终回复中说明风险，由用户自行
  协调。
