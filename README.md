# PyPTY
### A lightweight Python shell library built on Windows ConPTY and POSIX PTY
#### This project aims to give you a fully functional terminal session (console emulation).
---

#### PROBLEMS TO ADDRESS:
Shell stacking (tracking diskpart → cmd → powershell nesting) is something most tools don't do at all. They either close everything on exit or leave orphaned processes.
This project handles it explicitly, which makes it more robust for deeply nested interactive sessions than most lightweight shell wrappers, and it uses Windows' native ConPTY and POSIX Pseudoterminals to support ANSI escape codes (colors, bold text) and complex interactive CLI tools.

# Built-in commands
| Command | Description |
|---|---|
| `!help` | Show available commands |
| `!shell <exe>` | Open a new shell session (e.g. `!shell powershell.exe`) |
| `!resize <cols> <rows>` | Resize the terminal |
| `!restart` | Restart the root shell |
| `exit` | Exits the child shell, or close if at parent shell |

# Integration

### Windows
```python
from session.session import Session

s = Session("cmd.exe")
s.start()
s.send_command("echo Hello from Windows!")
s.stop()
```

### Linux
```python
from session.session import Session

s = Session("bash")
s.start()
s.send_command("echo Hello from Linux!")
s.stop()
```

### macOS
```python
from session.session import Session

s = Session("zsh")
s.start()
s.send_command("echo Hello from macOS!")
s.stop()
```

### Cross-platform (auto-detect shell)

```python
import sys
from session.session import Session

shell = "cmd.exe" if sys.platform == "win32" else None
s = Session(shell)
s.start()
s.send_command("echo Hello!")
s.stop()
```

