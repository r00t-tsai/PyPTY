# Web-based environment integration
## ANSI Preservation:
#### This replaces the local main() loop with an WebSocket-ready structure that preserves ANSI colors for a frontend like Xterm.js
EXAMPLE:

```python
class webbridge(IOBridge):
    def __init__(self, master_fd: int, on_output_callback):
        super().__init__(master_fd)
        # We override the reader to send data to a callback (like a WebSocket)
        self._reader = webreader(master_fd, on_output_callback)

class webreader(OutputReader):
    def __init__(self, master_fd, callback):
        super().__init__(master_fd)
        self.callback = callback

    def _emit(self, data: bytes):
        # Send raw bytes to the callback (which forwards to WebSocket)
        if data:
            self.callback(data)
```
## WebSocket Integration:
#### This example uses `websockets` to bridge the PTY to a browser.
EXAMPLE:
```python
import asyncio
import websockets
from session.session import Session

async def terminal_handler(websocket):
    # Initialize the Session
    # This uses os.openpty()
    session = Session(shell="/bin/bash", cols=80, rows=24)
    
    # Define output handling from the PTY
    def on_pty_output(data):
        # Schedule the raw ANSI data to be sent over the socket
        asyncio.run_coroutine_threadsafe(
            websocket.send(data), asyncio.get_event_loop()
        )

    # Use callback instead of sys.stdout
    session._bridge = WebIOBridge(session._pty.master_fd, on_pty_output)
    session._bridge.start()

    try:
        # Listen for input from the browser
        async for message in websocket:
            # message is the keypress/string from Xterm.js
            if isinstance(message, str):
                session.send_raw(message.encode())
            else:
                session.send_raw(message)
    finally:
        session.stop()

# Start the server
# start_server = websockets.serve(terminal_handler, "localhost", 8080)
```
