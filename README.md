# PyPTY
### A simple lightweight Python shell library built on Windows ConPTY and POSIX PTY
#### This project aims to give you a fully functional terminal session (console emulation). Useful for Web Terminal Development, Cloud IDEs, CLI Tool Automation, or if you just need Shell Stacking.
---

#### PROBLEMS TO ADDRESS:
Shell stacking (tracking diskpart → cmd → powershell nesting) is something most tools don't do at all. They either close everything on exit or leave orphaned processes.
This project handles it explicitly, which makes it more robust for deeply nested interactive sessions than most lightweight shell wrappers, and it uses Windows' native ConPTY and POSIX Pseudoterminals to support ANSI escape codes (colors, bold text) and complex interactive CLI tools.

---

#### UPDATES:
**3/1/2026** - Windows & Posix v1.1

* Ctrl+C and Ctrl+D now work instantly. They bypass input queues to stop processes immediately without crashing the script.
* Strips hidden formatting codes (ANSI) and suppresses "echoed" text, so you only see the command's actual results rather than a repeat of what you typed.
* Initial system banners (like Windows or Shell welcome messages) now display fully before the automated filters kick in.
* Added native support for both Windows `msvcrt` and Linux/Mac `termios` to ensure stable keyboard input across all systems.
* Web integration for the POSIX version is supported. Please see the separate ReadMe on the POSIX-PTY directory for more information.
---

#### SECURITY LIMITATIONS:
* This library gives the website user raw access to a shell (/bin/bash). Run this inside a Docker container or a Sandbox to prevent the user from deleting files on your host server.

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

