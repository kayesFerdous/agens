# Safety and Limits

## Confirmation
- The assistant asks before doing risky actions (for example, destructive commands).
- Once you confirm, the approval is only for your current session.

## How confirmation appears
- Web app: a confirmation dialog.
- Terminal app (TUI): a secure prompt.
- Telegram: a confirm button.

## Where tools can act
- File and search tools only work inside the workspace folder.
- Shell commands run only inside the workspace folder.
- Web access is limited to search and page reading.

## API key safety
- Your API keys are stored locally in encrypted form.
- If a key or model hits a rate limit, the app can switch to another one.
