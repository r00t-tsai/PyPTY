import sys
from interpreter.interpreter import Shell

def main():
    interpreter = Shell()
    try:
        interpreter._run()
    except KeyboardInterrupt:
        print("\n[Interrupted]")
    finally:
        interpreter.cleanup()


if __name__ == "__main__":
    if sys.platform == "win32":
        print("Error: This build is available only on Linux.")
        sys.exit(1)
    main()
