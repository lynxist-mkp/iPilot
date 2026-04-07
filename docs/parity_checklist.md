# Parity Checklist

## 已完成

- [x] config
- [x] session
- [x] provider abstraction
- [x] basic tools
- [x] context builder
- [x] agent loop
- [x] CLI
- [x] SDK facade
- [x] minimal API
- [x] retry polish
- [x] streaming polish for CLI and SDK
- [x] hooks
- [x] cron persistence
- [x] heartbeat tick loop
- [x] Twitch channel adapter
- [x] README 收口
- [x] pytest 工程化收口

## 本轮明确不做

- [ ] API streaming
- [ ] command router
- [ ] message tool
- [ ] web tools
- [ ] memory consolidation
- [ ] multi-channel orchestration
- [ ] Docker packaging
- [ ] OAuth refresh
- [ ] security hardening

## 每轮回归检查

- [ ] `uv run pytest -q`
- [ ] `uv run ipilot --help`
- [ ] `uv run ipilot status`
- [ ] `uv run uvicorn ipilot.api.server:app --port 8900`

