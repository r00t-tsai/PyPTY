import sys
import signal
from interpreter.interpreter import Shell


def main():
    interpreter = Shell()
    old_sigint = signal.signal(signal.SIGINT, signal.SIG_IGN)
    try:
        interpreter._run()
    finally:
        signal.signal(signal.SIGINT, old_sigint)
        interpreter.cleanup()


if __name__ == "__main__":
    if sys.platform != "win32":
        print("Error: ConPTY is only available on Windows.")
        sys.exit(1)
    main()
