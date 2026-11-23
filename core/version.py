"""App version and GitHub update endpoint (single source of truth)."""

__version__ = "0.2.2"

GITHUB_REPO = "spidychoipro/chess-brain"
TAGS_API = f"https://api.github.com/repos/{GITHUB_REPO}/tags?per_page=1"
RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"
