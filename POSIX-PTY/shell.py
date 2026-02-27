import sys
import os
from interpreter.interpreter import Shell


def main():
    default_shell = os.environ.get("SHELL", "bash")
    interpreter = Shell(shell=default_shell)
    try:
        interpreter._run()
    except KeyboardInterrupt:
        print("\n[Interrupted]")
    finally:
        interpreter.cleanup()


if __name__ == "__main__":
    if sys.platform == "win32":
        print("Error: This is the POSIX build. Use the Windows version for Win32.")
        sys.exit(1)
    main()