# Agent Capabilities

## What I can do

### File Operations
- Read files (`file_read`)
- Write files (`file_write`)
- Edit files (`file_edit`)
- List directory contents (`list_directory`)

### Search & Discovery
- Search file contents by pattern (`grep`)
- Find files by name or type (`find`)
- Search the web (`search_web`)

### System
- Run shell commands (`shell_command`)

### Schedule
- Add events (`schedule_add`)
- List events by today, tomorrow, this week, date, or all (`schedule_list`)
- Update events by id (`schedule_update`)
- Delete events by id or title match (`schedule_delete`)

### Configuration
- Update your personal config (`update_config`)
  - Adjustable: user profile, assistant tone, preferences

### Knowledge
- Read knowledge files on demand
- Topics available: see the knowledge file index in context

## What I cannot do
- Access the internet beyond web search
- Remember anything between separate conversations
- Modify my own source code or tools

## Interfaces
Available on: TUI, API, Telegram, Web

## Notes
- Config changes take effect immediately
- Knowledge files can be added or edited by you in the runtime config directory
