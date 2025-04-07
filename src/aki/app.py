import sys
import chainlit as cl
from chainlit.cli import chainlit_run
from aki.version import __version__


@cl.on_message
async def on_message(message: cl.Message):
    # Your custom logic goes here...

    # Send a response back to the user
    await cl.Message(
        content=f"Received: {message.content}",
    ).send()


def main():
    """Entry point for the application."""
    port = 8888
    sys.argv = [sys.argv[0], __file__, "--port", str(port)]
    chainlit_run()


if __name__ == "__main__":
    main()
