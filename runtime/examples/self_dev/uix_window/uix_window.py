"""Open GUPPI's UIX as its own Windows window (a browser in app mode: no address bar, no tabs, own taskbar entry).

Pure: no processes, no file system access, no environment reads; only the standard library. The caller passes the
environment and an `exists(path) -> bool` function and starts the returned argument list itself.

Safety rule: the window may only ever show GUPPI's own UIX on the loopback address. Any other URL is refused.
"""

DEFAULT_SIZE = (1280, 820)
BROWSERS = (
    ("ProgramFiles(x86)", r"Microsoft\Edge\Application\msedge.exe"),
    ("ProgramFiles", r"Microsoft\Edge\Application\msedge.exe"),
    ("LOCALAPPDATA", r"Microsoft\Edge\Application\msedge.exe"),
    ("ProgramFiles", r"Google\Chrome\Application\chrome.exe"),
    ("ProgramFiles(x86)", r"Google\Chrome\Application\chrome.exe"),
    ("LOCALAPPDATA", r"Google\Chrome\Application\chrome.exe"),
)


def browser_candidates(env):
    """Full paths to try, in the order of BROWSERS. `env` maps variable names to values (like os.environ).
    A pair whose variable is missing or empty in `env` is skipped. Join with a single backslash; a trailing backslash on the
    variable's value does not double it. No duplicates (keep the first occurrence; compare case-insensitively)."""
    raise NotImplementedError


def pick_browser(candidates, exists):
    """The first candidate for which exists(candidate) is True, or None."""
    raise NotImplementedError


def check_uix_url(url):
    """Return `url` unchanged if it is GUPPI's own UIX, else raise ValueError("uix_url_not_allowed").
    Allowed exactly: starts with "http://127.0.0.1:", then a port of 1 to 5 digits whose value is 1..65535, then "/",
    then optionally "#" followed by anything except whitespace. Nothing else (no path, no query, no other host, no https)."""
    raise NotImplementedError


def window_argv(browser, url, profile_dir, size=DEFAULT_SIZE):
    """Argument list that opens `url` as an app window.
    `url` must pass check_uix_url (else its ValueError). `profile_dir` must be a non-empty string, else
    ValueError("profile_dir_required"). `size` is (width, height) of ints, each 400..7680, else ValueError("invalid_window_size").
    Returns exactly:
      [browser, "--app=<url>", "--user-data-dir=<profile_dir>", "--window-size=<width>,<height>",
       "--no-first-run", "--no-default-browser-check", "--disable-extensions"]"""
    raise NotImplementedError
