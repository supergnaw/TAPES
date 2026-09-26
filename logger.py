import os
import sys

from datetime import datetime

from sympy.integrals.intpoly import strip


class Style:
    # Normal Colors
    Black: int = 30
    Red: int = 31
    Green: int = 32
    Yellow: int = 33
    Blue: int = 34
    Magenta: int = 35
    Cyan: int = 36
    White: int = 37

    # Bright Colors
    BrightBlack: int = 90
    BrightRed: int = 91
    BrightGreen: int = 92
    BrightYellow: int = 93
    BrightBlue: int = 94
    BrightMagenta: int = 95
    BrightCyan: int = 96
    BrightWhite: int = 97

    # Effects
    Normal: int = 0
    Bold: int = 1
    Faint: int = 2
    Italic: int = 3
    Underline: int = 4
    CrossedOut: int = 9
    Framed: int = 51


# Attempt at reliable color detection
USE_COLOR = (
        sys.stdout.isatty()
        or os.environ.get("FORCE_COLOR")
        or os.environ.get("TERM") in ("xterm", "xterm-color", "xterm-256color")
)

USE_COLOR = True

# Primary functions
def format(text: str, *styles: str) -> str:
    codes = []

    for style in styles:
        style = style.capitalize().strip()
        if style.startswith("Bright"):
            style = f"Bright{style[6:].strip().capitalize()}"

        code = getattr(Style, style, None)
        if isinstance(code, int):
            codes.append(str(code))

    if not codes:
        return text

    prefix = "\033[" + ";".join(codes) + "m"
    suffix = "\033[0m"

    return f"{prefix}{text}{suffix}" if USE_COLOR else text


def log(text: str, *styles: str, log_file: str = "") -> None:
    _write(text, log_file)
    print(format(text, *styles))


def _write(text: str, log_file: str = "") -> None:
    log_file = log_file if log_file else f"build_{datetime.now().strftime('%Y-%m-%d')}.log"
    with open(log_file, "a", encoding="utf-8") as file_handle:
        file_handle.write(f"{text}\n")


# Convenience Wrappers

def success(text, log_file=""): log(text, "Green", log_file=log_file)


def warning(text, log_file=""): log(text, "Yellow", log_file=log_file)


def info(text, log_file=""): log(text, "Cyan", log_file=log_file)


def error(text, log_file=""): log(text, "Red", log_file=log_file)


def bold(text, log_file=""): log(text, "Bold", log_file=log_file)


# Tester
if "__main__" == __name__:
    print(f"\n=== Checking logger.py Colors ===")
    print(f"\nColors enabled: {USE_COLOR}")
    print("\nDefault ANSI colors and styles:")
    for s in Style.__dict__:
        if not isinstance(getattr(Style, s), int): continue
        print(f"  - \033[{getattr(Style, s)}m{s}\033[0m")
