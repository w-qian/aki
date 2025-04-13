"""Welcome message display for Aki."""

import os
from typing import List
from colorama import init, Fore, Style

# Initialize colorama for cross-platform color support
init()

# ASCII art for AKI - left aligned with more spacing
AKI_ASCII = r"""
   █████    ██   ██    ██
  ██   ██   ██  ██     ██
  ███████   █████      ██
  ██   ██   ██  ██     ██
  ██   ██   ██   ██    ██
"""


def format_link(text: str, url: str) -> str:
    """Format a link with color and underlining."""
    return f"{Fore.CYAN}{text}{Fore.BLUE} → {url}{Style.RESET_ALL}"


def format_section(title: str, items: List[str], color: str = Fore.GREEN) -> str:
    """Format a section with title and items."""
    section = [f"{color}{title}{Style.RESET_ALL}"]
    section.extend([f"  {item}" for item in items])
    return "\n".join(section)


def get_terminal_width() -> int:
    """Get terminal width, default to 80 if cannot be determined."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def print_welcome_message():
    """Display the welcome message with ASCII art and formatting."""
    # Welcome sections
    quick_links = [
        format_link(
            "Documentation",
            "https://github.com/Aki-community/aki/blob/main/README.md",
        )
    ]

    quick_start = [
        f"{Fore.YELLOW}1.{Style.RESET_ALL} Choose a profile or create your own in ~/.aki/profiles/",
        f"{Fore.YELLOW}2.{Style.RESET_ALL} Try commands like 'set your workspace to code_package/path and analyze it'",
    ]

    # Build the message
    message_parts = [
        f"\n{Fore.CYAN}{AKI_ASCII}{Style.RESET_ALL}",
        f"{Fore.YELLOW}Your AI Development Companion{Style.RESET_ALL}\n",
        format_section("Quick Links", quick_links),
        format_section("Getting Started", quick_start),
        f"\n{Fore.GREEN}Ready to help with your development tasks! 🚀{Style.RESET_ALL}\n",
    ]

    print("\n".join(message_parts))


def print_debug(*args, **kwargs):
    """
    Print debug-level information in dim grey color.
    Accepts same arguments as the built-in print function.
    """
    text = " ".join(str(arg) for arg in args)
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    print(Style.DIM + Fore.WHITE + text + Style.RESET_ALL, sep=sep, end=end)


def print_info(*args, **kwargs):
    text = " ".join(str(arg) for arg in args)
    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    print(Style.NORMAL + Fore.CYAN + text + Style.RESET_ALL, sep=sep, end=end)
