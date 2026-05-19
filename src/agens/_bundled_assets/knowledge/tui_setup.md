# Using the Terminal Interface (TUI)

Agens includes a powerful, interactive Terminal User Interface (TUI). This allows you to chat securely with your agent directly from your computer's terminal (or command prompt), without needing a web browser or external app.

## What to Expect
When you launch the TUI, your terminal window will transform into a full-screen chat application. It looks and feels similar to modern chat apps, but entirely text-based. You will see your messages, the agent's responses, and the tools the agent is executing in real-time.

## How to Start the TUI

Open your terminal application (such as Terminal on macOS/Linux, or PowerShell/Command Prompt on Windows) and type the following command, then press Enter:

```bash
agens tui
```

## Key Features & Navigation

- **Chatting:** Just type your request into the input box at the bottom and press Enter to send it.
- **Sudo & Security:** Because the TUI runs on your local machine, it is the *only* interface that is allowed to execute `sudo` (administrator) commands or actions requiring explicit security confirmation. When the agent needs to run a privileged command, the TUI will securely prompt you to approve it.
- **Copying/Pasting:** Depending on your terminal, pasting text might require a different shortcut than usual (e.g., `Ctrl+Shift+V` on Linux/Windows, or `Cmd+V` on macOS).
- **Session Resumption:** You can pick up a conversation right where you left off by providing the previous session's ID:
  ```bash
  agens tui -s <your_session_id>
  ```

## How to Exit

When you are finished, you can safely close the interface by doing any of the following:
- Type `/quit` or `/exit` in the chat input and press Enter.
- Press `Ctrl+C` on your keyboard.
- Simply close the terminal window.