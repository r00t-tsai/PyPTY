# PyPTY
### A lightweight Python shell built on Windows ConPTY and POSIX PTY
#### This project aims to give you a fully functional terminal session (console emulation).
---

#### PROBLEM:
Shell stacking (tracking diskpart → cmd → powershell nesting) is something most tools don't do at all. They either close everything on exit or leave orphaned processes.
This project handles it explicitly, which makes it more robust for deeply nested interactive sessions than most lightweight shell wrappers, and it uses Windows' native ConPTY to support ANSI escape codes (colors, bold text) and complex interactive CLI tools.

# Built-in commands
| Command | Description |
|---|---|
| `!help` | Show available commands |
| `!shell <exe>` | Open a new shell session (e.g. `!shell powershell.exe`) |
| `!resize <cols> <rows>` | Resize the terminal |
| `!restart` | Restart the root shell |
| `exit` | Exits the child shell, or close if at parent shell |
