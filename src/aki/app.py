"""Simple chat application with Chainlit and LangGraph."""

import os
import sys
import socket

# Remove argparse import
from pathlib import Path
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
root_path = Path(__file__).parent
os.environ["CHAINLIT_APP_ROOT"] = str(root_path)
# If chainlit is already imported, patch it
if "chainlit.config" in sys.modules:
    sys.modules["chainlit.config"].APP_ROOT = str(Path(__file__).parent)

from aki.config.logging_config import setup_logging

setup_logging()

import chainlit as cl
from chainlit.cli import chainlit_run

from aki.init_aki import initialize_aki
from aki.console_print import print_welcome_message, print_info, print_debug
from aki.version import __version__
from aki.event_handler import EventHandler
from aki.callback.usage_callback import UsageCallback

# Create default usage callback (no metrics)
usage_callback = UsageCallback(metrics=None)

# Create the event handler instance with the default callback
handler = EventHandler(usage_callback=usage_callback)


@cl.data_layer
def get_data_layer():
    return handler.setup_data_layer()


@cl.set_chat_profiles
async def chat_profile():
    return await handler.setup_chat_profiles()


@cl.header_auth_callback
def header_auth_callback(headers: dict) -> cl.User | None:
    return handler.header_auth_callback(headers)


@cl.on_chat_start
async def on_chat_start():
    await handler.handle_chat_start()


@cl.on_settings_update
async def update_state_by_settings(settings: cl.ChatSettings):
    await handler.handle_settings_update(settings)


@cl.on_stop
async def on_stop():
    await handler.handle_stop()


@cl.on_chat_end
async def on_chat_end():
    await handler.handle_chat_end()


@cl.on_chat_resume
async def on_chat_resume(thread):
    await handler.handle_chat_resume(thread)


@cl.on_message
async def on_message(message: cl.Message):
    await handler.handle_message(message)


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


def main():
    """Entry point for the application."""
    # Simple manual argument parsing without argparse
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
                print_debug(f"Invalid port number: {args[i + 1]}")
        i += 1

    # Handle port configuration
    port = find_available_port(default_port)
    if port != default_port:
        print_debug(f"Port {default_port} is in use. Using port {port} instead.")

    # Set up chainlit arguments
    sys.argv = [sys.argv[0], __file__, "--port", str(port)]
    if debug_mode:
        sys.argv.extend(["--debug"])

    initialize_aki()
    # initialize_watcher()
    print_welcome_message()
    print_info(f"Aki {__version__} is available at http://localhost:{port}")
    chainlit_run()


if __name__ == "__main__":
    main()
