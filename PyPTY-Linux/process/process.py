import os
import signal


class ChildProcess:

    def __init__(self, pid: int):
        self._pid = pid

    @property
    def pid(self) -> int:
        return self._pid

    def wait(self) -> int:
        try:
            _, status = os.waitpid(self._pid, 0)
            return os.waitstatus_to_exitcode(status)
        except ChildProcessError:
            return -1

    def terminate(self):
        try:
            os.kill(self._pid, signal.SIGTERM)
        except ProcessLookupError:
            pass

    def kill(self):
        try:
            os.kill(self._pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def spawn(command: str, slave_fd: int) -> ChildProcess:

    pid = os.fork()

    if pid == 0:

        try:
            os.setsid()

            import fcntl, termios
            fcntl.ioctl(slave_fd, termios.TIOCSCTTY, 0)

            os.dup2(slave_fd, 0)
            os.dup2(slave_fd, 1)
            os.dup2(slave_fd, 2)

            try:
                max_fd = os.sysconf("SC_OPEN_MAX")
            except (AttributeError, ValueError):
                max_fd = 256
            for fd in range(3, max_fd):
                try:
                    os.close(fd)
                except OSError:
                    pass

            import shlex
            args = shlex.split(command)
            os.execvp(args[0], args)
        except Exception:
            os._exit(1)

    else:

        os.close(slave_fd)
        return ChildProcess(pid)