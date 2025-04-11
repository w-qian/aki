"""Simple chat application with Chainlit."""

import sys
import socket
import logging
import chainlit as cl
from chainlit.cli import chainlit_run
from aki.version import __version__

# Configure basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@cl.on_chat_start
async def on_chat_start():
    """Initialize the chat session when a new conversation starts."""
    # Welcome message
    await cl.Message(
        content=f"Welcome to Aki v{__version__}! How can I help you today?"
    ).send()


@cl.on_message
async def on_message(message: cl.Message):
    """Process incoming user messages."""
    try:
        # Process the user's message here
        # This is a simple echo response for demonstration
        response = f"You said: {message.content}"

        # Send response back to the user
        await cl.Message(content=response).send()
    except Exception as e:
        error_message = f"An error occurred: {str(e)}"
        logger.error(error_message, exc_info=True)
        await cl.Message(content=error_message).send()


def is_port_in_use(port: int) -> bool:
    """Check if a port is in use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        try:
            s.bind(("localhost", port))
            return False
        except OSError:
            return True


def find_available_port(start_port: int) -> int:
    """Find the next available port starting from start_port."""
    port = start_port
    while is_port_in_use(port):
        port += 1
        if port > 65535:  # Maximum port number
            raise RuntimeError("No available ports found")
    return port


def print_welcome_message():
    """Print a welcome message to the console."""
    print(f"\n{'=' * 60}")
    print(f"Welcome to Aki v{__version__}!")
    print(f"{'=' * 60}\n")


def main():
    """Entry point for the application."""
    # Simple manual argument parsing
    default_port = 8888
    debug_mode = False

    # Process command line arguments manually
    args = sys.argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ["-v", "--version"]:
            print(f"Aki {__version__}")
            sys.exit(0)
        elif arg == "--debug":
            debug_mode = True
        elif arg == "--port" and i + 1 < len(args):
            try:
                default_port = int(args[i + 1])
                i += 1  # Skip next argument as we've used it
            except ValueError:
                print(f"Invalid port number: {args[i + 1]}")
        i += 1

    # Handle port configuration
    port = find_available_port(default_port)
    if port != default_port:
        print(f"Port {default_port} is in use. Using port {port} instead.")

    # Set up chainlit arguments
    sys.argv = [sys.argv[0], __file__, "--port", str(port)]
    if debug_mode:
        sys.argv.extend(["--debug"])

    print_welcome_message()
    print(f"Aki {__version__} is available at http://localhost:{port}")
    chainlit_run()


if __name__ == "__main__":
    main()
