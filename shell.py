import sys
from interpreter.interpreter import Shell

def main():
    interpreter = Shell()
    try:
        interpreter._run()
    except KeyboardInterrupt:
        pass
    finally:
        interpreter.cleanup()
      
if __name__ == "__main__":
    if sys.platform != "win32":
        print("Error: PyPTY is only available on Windows.")
        sys.exit(1)
    main()
