# n8n Workflows

This folder documents the minimal n8n setup used in the MVP.

## Inbound (chat-message)
- Webhook: `POST /webhook/chat-message`
- Action: HTTP Request → `http://backend:8000/inbound`

## Outbound (ops-outbound)
- Webhook: `POST /webhook/ops-outbound`
- Action: route by `action` field:
  - `send_slack_message` → Slack channel message
  - `send_slack_dm` → Slack DM using `user_id`

## Optional Enforcement Cron
- Cron schedule (e.g., 16:00 / 18:00 / 20:00)
- HTTP Request → `http://backend:8000/tasks/enforce`
