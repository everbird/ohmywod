"""Read-only, per-app release snapshots; no Git or file IO during requests."""

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import re
import subprocess

from markdown_it import MarkdownIt


PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORY_URL = "https://github.com/everbird/ohmywod"
VERSION_RE = re.compile(r"v[0-9]+\.[0-9]+(?:\.[0-9]+)?")
HEADING_RE = re.compile(r"\[(v[0-9]+\.[0-9]+(?:\.[0-9]+)?)\](?:\s+-\s+(.+))?")
SHA_RE = re.compile(r"[0-9a-f]{40}")


@dataclass(frozen=True)
class VersionInfo:
    status: str = "unavailable"
    commit: str | None = None
    tag: str | None = None
    dirty: bool = False

    @property
    def label(self):
        label = {
            "unavailable": "版本信息暂不可用",
            "untagged": "未打标签",
            "ambiguous": "版本待确认",
            "tagged": self.tag,
        }[self.status]
        return label + (" + 本地修改" if self.dirty else "")

    @property
    def short_commit(self):
        return self.commit[:7] if self.commit else None

    @property
    def commit_url(self):
        # Local, untagged commits may never have been pushed to GitHub.
        return f"{REPOSITORY_URL}/commit/{self.commit}" if self.commit and self.tag else None

    @property
    def preview(self):
        return self.dirty or self.status in ("untagged", "ambiguous")


@dataclass(frozen=True)
class ChangelogEntry:
    version: str
    date: str | None
    body_html: str

    @property
    def anchor(self):
        return self.version.replace(".", "-")

    @property
    def source_url(self):
        return f"{REPOSITORY_URL}/tree/{self.version}"


@dataclass(frozen=True)
class Changelog:
    entries: tuple[ChangelogEntry, ...] = ()
    available: bool = True


@dataclass(frozen=True)
class ReleaseSnapshot:
    version: VersionInfo
    changelog: Changelog

    @property
    def current_anchor(self):
        for entry in self.changelog.entries:
            if entry.version == self.version.tag:
                return entry.anchor
        return None


def _git(root, *args):
    # Inherited repository selectors must not redirect -C into another checkout.
    env = os.environ.copy()
    for key in ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_COMMON_DIR",
                "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_NAMESPACE"):
        env.pop(key, None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    # Never trust every repository globally or refresh the index from a worker.
    result = subprocess.run(
        ["git", "--no-optional-locks", "-c", f"safe.directory={root}",
         "-C", str(root), *args],
        env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        check=True, timeout=2,
    )
    return result.stdout.strip()


def read_version(root, logger=None):
    logger = logger or logging.getLogger(__name__)
    try:
        root = Path(root).resolve()
        # A Git command would otherwise walk up into an unrelated parent repo.
        # .git may be either a directory (checkout) or a file (Git worktree).
        if not (root / ".git").exists():
            logger.warning("Application version unavailable (no application checkout).")
            return VersionInfo()
        commit = _git(root, "rev-parse", "--verify", "HEAD").lower()
        if not SHA_RE.fullmatch(commit):
            raise ValueError("Invalid application commit")
        tags = sorted({tag for tag in _git(root, "tag", "--points-at", commit).splitlines()
                       if VERSION_RE.fullmatch(tag)})
        dirty = bool(_git(root, "status", "--porcelain=v1", "--untracked-files=normal"))
        if len(tags) > 1:
            logger.warning("Application version ambiguous (multiple official tags at HEAD).")
            return VersionInfo("ambiguous", commit, dirty=dirty)
        if tags:
            return VersionInfo("tagged", commit, tags[0], dirty)
        return VersionInfo("untagged", commit, dirty=dirty)
    except (OSError, subprocess.SubprocessError, ValueError) as exc:
        # Keep stderr, paths and command details out of public templates.
        logger.warning("Application version unavailable (%s).", type(exc).__name__)
        return VersionInfo()


def render_changelog(source):
    """Use the Markdown token stream, not a home-grown Markdown/HTML sanitizer.

    Only top-level release sections are public. Unreleased and the document's
    H1/preamble are omitted. Version headings/IDs are rendered by Jinja; only
    the body HTML produced with raw HTML disabled is marked safe later.
    """
    markdown = MarkdownIt("commonmark", {"html": False})
    env = {}
    tokens = markdown.parse(source, env)
    starts = [i for i, token in enumerate(tokens)
              if token.type == "heading_open" and token.tag == "h2" and token.level == 0]
    entries = []
    seen = set()
    for pos, start in enumerate(starts):
        heading = tokens[start + 1].content.strip()
        if heading.casefold() in ("[unreleased]", "unreleased"):
            continue
        match = HEADING_RE.fullmatch(heading)
        if not match:
            raise ValueError("Invalid changelog release heading")
        version, date = match.groups()
        if version in seen:
            raise ValueError("Duplicate changelog release")
        seen.add(version)
        end = starts[pos + 1] if pos + 1 < len(starts) else len(tokens)
        body = markdown.renderer.render(tokens[start + 3:end], markdown.options, env)
        entries.append(ChangelogEntry(version, date, body))
    return Changelog(tuple(entries))


def load_release_snapshot(root=None, logger=None):
    root = PROJECT_ROOT if root is None else Path(root)
    logger = logger or logging.getLogger(__name__)
    version = read_version(root, logger)
    try:
        # Fixed, repository-maintained source; never a request parameter/upload.
        source = (root / "docs" / "changelog.md").read_text(encoding="utf-8")
        changelog = render_changelog(source)
    except Exception as exc:
        # This optional page must not prevent the main application from booting.
        logger.warning("Changelog unavailable (%s).", type(exc).__name__)
        changelog = Changelog(available=False)
    return ReleaseSnapshot(version, changelog)
