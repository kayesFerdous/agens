# Configuration and Data

## Settings folder
Agens creates a private settings folder on your computer. It contains:
- config.json (your settings)
- knowledge/ (help files you can edit)
- prompts/ (prompt templates you can edit)
- sessions/ (saved chats)
- logs/ (app logs)

Default files are copied the first time you run the app. Your edits are kept
and are not overwritten unless you force a reset.

## Changing settings
- The assistant can update settings for you.
- It only changes these top sections: user, assistant, preferences.

## API keys and models
- Your API keys are stored locally and encrypted.
- You can add more than one key. If one is rate-limited, another can be used.
- Supported providers include Gemini and OpenAI.

## Chats and memory
- Conversations are saved locally.
- You can continue a past chat later.
- There is no cloud sync; your data stays on this device.
