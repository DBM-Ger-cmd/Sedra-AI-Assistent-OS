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
    result = []
    seen = set()
    for var, rel_path in BROWSERS:
        value = env.get(var, "")
        if not value:
            continue
        if value.endswith("\\"):
            full_path = value + rel_path
        else:
            full_path = value + "\\" + rel_path
        lower_path = full_path.lower()
        if lower_path not in seen:
            seen.add(lower_path)
            result.append(full_path)
    return result


def pick_browser(candidates, exists):
    """The first candidate for which exists(candidate) is True, or None."""
    for candidate in candidates:
        if exists(candidate):
            return candidate
    return None


def check_uix_url(url):
    """Return `url` unchanged if it is GUPPI's own UIX, else raise ValueError("uix_url_not_allowed").
    Allowed exactly: starts with "http://127.0.0.1:", then a port of 1 to 5 digits whose value is 1..65535, then "/",
    then optionally "#" followed by anything except whitespace. Nothing else (no path, no query, no other host, no https)."""
    import re
    if not isinstance(url, str) or url != url.strip():
        raise ValueError("uix_url_not_allowed")
    match = re.fullmatch(r"http://127\.0\.0\.1:(\d{1,5})/(?:#(.*))?$", url, re.ASCII)
    if not match:
        raise ValueError("uix_url_not_allowed")
    try:
        port = int(match.group(1))
    except ValueError:
        raise ValueError("uix_url_not_allowed")
    if not (1 <= port <= 65535):
        raise ValueError("uix_url_not_allowed")
    fragment = match.group(2)
    if fragment and re.search(r"\s", fragment):
        raise ValueError("uix_url_not_allowed")
    return url


def window_argv(browser, url, profile_dir, size=DEFAULT_SIZE):
    """Argument list that opens `url` as an app window.
    `url` must pass check_uix_url (else its ValueError). `profile_dir` must be a non-empty string, else
    ValueError("profile_dir_required"). `size` is (width, height) of ints, each 400..7680, else ValueError("invalid_window_size").
    Returns exactly:
      [browser, "--app=<url>", "--user-data-dir=<profile_dir>", "--window-size=<width>,<height>",
       "--no-first-run", "--no-default-browser-check", "--disable-extensions"]"""
    if not isinstance(profile_dir, str) or not profile_dir:
        raise ValueError("profile_dir_required")
    if not isinstance(size, tuple) or len(size) != 2:
        raise ValueError("invalid_window_size")
    width, height = size
    if (
        not isinstance(width, int)
        or not isinstance(height, int)
        or not (400 <= width <= 7680)
        or not (400 <= height <= 7680)
    ):
        raise ValueError("invalid_window_size")
    check_uix_url(url)
    return [
        browser,
        "--app=" + url,
        "--user-data-dir=" + profile_dir,
        f"--window-size={width},{height}",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-extensions",
    ]
