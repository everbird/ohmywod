"""Release metadata is local, truthful, read-only and cached per app instance."""

import importlib
from pathlib import Path
import subprocess
from types import SimpleNamespace
from unittest.mock import Mock

from lxml import html
import pytest

from ohmywod import release


SHA = "a" * 40
NOTES = """# 更新日志

## [Unreleased]
### 新增
- Secret upcoming change

## [v2.3] - 2026-10-04
### 修复
- Original published note with **formatting**.

## [v2.2] - 2026-10-04
- Earlier note
"""


def git(root, *args):
    return subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-c", "tag.gpgsign=false",
         "-c", "user.name=Release test", "-c", "user.email=release@example.invalid",
         "-C", str(root), *args],
        check=True, capture_output=True, text=True,
    ).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "app"
    root.mkdir()
    git(root, "init", "-q", "--initial-branch=main")
    (root / "docs").mkdir()
    (root / "docs" / "changelog.md").write_text(NOTES, encoding="utf-8")
    (root / "code.txt").write_text("original\n", encoding="utf-8")
    (root / ".gitignore").write_text(
        "local_config.py\n.venv/\n.data/\nsupervisord.conf\n", encoding="utf-8"
    )
    git(root, "add", ".")
    git(root, "commit", "-q", "-m", "Initial release")
    return root


@pytest.mark.parametrize("annotated", [False, True])
def test_exact_lightweight_and_annotated_tags(repo, annotated):
    if annotated:
        git(repo, "tag", "-a", "v2.3", "-m", "Release")
    else:
        git(repo, "tag", "v2.3")
    git(repo, "tag", "latest")  # An alias is not an official numeric version.
    info = release.read_version(repo)
    assert info.status == "tagged"
    assert info.tag == "v2.3"
    assert info.commit == git(repo, "rev-parse", "HEAD")
    assert info.short_commit == info.commit[:7]
    assert info.commit_url.endswith("/commit/" + info.commit)
    assert info.label == "v2.3"
    assert not info.dirty and not info.preview


def test_no_exact_tag_does_not_claim_ancestor_or_highest_version(repo):
    git(repo, "tag", "v2.3")
    git(repo, "tag", "v99.0")
    (repo / "code.txt").write_text("ahead of release\n", encoding="utf-8")
    git(repo, "add", "code.txt")
    git(repo, "commit", "-q", "-m", "Not released")
    info = release.read_version(repo)
    assert info.status == "untagged" and info.tag is None
    assert info.label == "未打标签" and info.preview


def test_multiple_official_tags_are_ambiguous(repo):
    git(repo, "tag", "v2.3")
    git(repo, "tag", "v2.3.1")
    info = release.read_version(repo)
    assert info.status == "ambiguous" and info.tag is None
    assert info.commit and info.label == "版本待确认"


@pytest.mark.parametrize("kind", ["unstaged", "staged", "untracked"])
def test_dirty_includes_tracked_and_new_files(repo, kind):
    git(repo, "tag", "v2.3")
    if kind == "untracked":
        (repo / "new-code.py").write_text("# new code\n", encoding="utf-8")
    else:
        (repo / "code.txt").write_text("edited\n", encoding="utf-8")
        if kind == "staged":
            git(repo, "add", "code.txt")
    info = release.read_version(repo)
    assert info.dirty and info.preview
    assert info.label == "v2.3 + 本地修改"
    assert info.commit == git(repo, "rev-parse", "HEAD")


def test_ignored_local_configuration_does_not_make_release_dirty(repo):
    git(repo, "tag", "v2.3")
    (repo / "local_config.py").write_text("# local\n", encoding="utf-8")
    (repo / "supervisord.conf").write_text("# generated\n", encoding="utf-8")
    (repo / ".data").mkdir()
    (repo / ".data" / "preview.txt").write_text("local data", encoding="utf-8")
    assert release.read_version(repo).label == "v2.3"
    assert not release.read_version(repo).dirty


def test_no_git_does_not_walk_up_into_parent_repository(repo, monkeypatch):
    child = repo / "archive"
    child.mkdir()
    run = Mock(side_effect=AssertionError("Must not read parent Git"))
    monkeypatch.setattr(release.subprocess, "run", run)
    info = release.read_version(child)
    assert info.status == "unavailable" and info.commit is None
    assert info.commit_url is None
    run.assert_not_called()


@pytest.mark.parametrize("error", [
    FileNotFoundError("private git path"),
    PermissionError("private checkout path"),
    subprocess.TimeoutExpired("private git command", 2),
    subprocess.CalledProcessError(128, "git", stderr="private stderr"),
])
def test_git_failure_is_nonfatal_and_does_not_expose_details(repo, monkeypatch, caplog, error):
    monkeypatch.setattr(release.subprocess, "run", Mock(side_effect=error))
    info = release.read_version(repo)
    assert info.status == "unavailable" and info.commit is None
    assert info.label == "版本信息暂不可用"
    assert "private" not in caplog.text


def test_git_calls_are_fixed_readonly_scoped_and_time_bounded(tmp_path, monkeypatch):
    (tmp_path / ".git").mkdir()
    commands = []
    outputs = iter([SHA, "latest\nv2.3\nv2.3-rc1\nnot-a-version", ""])

    def run(argv, **kwargs):
        commands.append(argv)
        assert argv[:6] == [
            "git", "--no-optional-locks", "-c", f"safe.directory={tmp_path}",
            "-C", str(tmp_path),
        ]
        assert kwargs["env"]["GIT_OPTIONAL_LOCKS"] == "0"
        assert kwargs["timeout"] == 2 and kwargs["check"]
        assert not kwargs.get("shell", False)
        return SimpleNamespace(stdout=next(outputs))

    monkeypatch.setattr(release.subprocess, "run", run)
    info = release.read_version(tmp_path)
    assert info.commit == SHA and info.tag == "v2.3"
    assert [argv[6:] for argv in commands] == [
        ["rev-parse", "--verify", "HEAD"],
        ["tag", "--points-at", SHA],
        ["status", "--porcelain=v1", "--untracked-files=normal"],
    ]


def test_invalid_commit_is_not_used_as_a_public_link(repo, monkeypatch):
    monkeypatch.setattr(release, "_git", lambda *args: "not a commit")
    assert release.read_version(repo).commit_url is None


def test_markdown_sections_index_and_unreleased_filter():
    notes = release.render_changelog(NOTES)
    assert [e.version for e in notes.entries] == ["v2.3", "v2.2"]
    assert [e.anchor for e in notes.entries] == ["v2-3", "v2-2"]
    assert notes.entries[0].date == "2026-10-04"
    assert "<strong>formatting</strong>" in notes.entries[0].body_html
    assert "Secret upcoming" not in "".join(e.body_html for e in notes.entries)
    assert notes.entries[0].source_url.endswith("/tree/v2.3")


def test_only_top_level_sections_are_split():
    source = """# Title
## [v2.3]
```markdown
## [Unreleased]
```
> ## A quoted heading

## [Unreleased]
- private draft

## [v2.2]
- published
"""
    notes = release.render_changelog(source)
    assert len(notes.entries) == 2
    assert "[Unreleased]" in notes.entries[0].body_html  # A code example remains text.
    assert "private draft" not in "".join(e.body_html for e in notes.entries)


@pytest.mark.parametrize("scheme", ["javascript:alert(1)", "vbscript:x", "file:///tmp/a", "data:text/html,hi"])
def test_markdown_disables_raw_html_and_dangerous_links(scheme):
    source = f"""## [v2.3]
<script>window.bad=1</script>

<img src=x onerror="window.bad=1" data-safe-onerror="window.bad=1">

[bad]({scheme})

[good](/changelog#v2-3)
"""
    body = release.render_changelog(source).entries[0].body_html
    tree = html.fragment_fromstring(body, create_parent="div")
    assert not tree.xpath(".//script | .//img")
    assert tree.xpath(".//a/@href") == ["/changelog#v2-3"]
    assert "&lt;script&gt;" in body


@pytest.mark.parametrize("source", [
    "## [v2.3]\n- first\n## [v2.3]\n- duplicate",
    "## malformed version\n- something",
])
def test_duplicate_or_invalid_release_headings_fail_validation(source):
    with pytest.raises(ValueError):
        release.render_changelog(source)


@pytest.mark.parametrize("kind", ["missing", "malformed", "render-error"])
def test_optional_changelog_failure_does_not_prevent_snapshot(repo, monkeypatch, kind):
    if kind == "missing":
        (repo / "docs" / "changelog.md").unlink()
    elif kind == "malformed":
        (repo / "docs" / "changelog.md").write_text("## invalid", encoding="utf-8")
    else:
        monkeypatch.setattr(release, "render_changelog", Mock(side_effect=RuntimeError("renderer failed")))
    snapshot = release.load_release_snapshot(repo)
    assert snapshot.version.commit
    assert not snapshot.changelog.available and not snapshot.changelog.entries


def test_app_factory_snapshots_are_separate_and_context_only_returns_cache(monkeypatch):
    factory = importlib.import_module("ohmywod.app")
    first = release.ReleaseSnapshot(release.VersionInfo("tagged", SHA, "v2.3"), release.render_changelog(NOTES))
    second = release.ReleaseSnapshot(release.VersionInfo("untagged", "b" * 40), release.Changelog())
    loader = Mock(side_effect=[first, second])
    monkeypatch.setattr(factory, "load_release_snapshot", loader)
    # Only exercise app factory/context setup, not unrelated global extensions.
    monkeypatch.setattr(factory, "configure_extensions", lambda app: None)
    one = factory.create_app(modules=())
    two = factory.create_app(modules=())
    assert one.extensions["site_release"] is first
    assert two.extensions["site_release"] is second
    for app, expected in [(one, first), (two, second)]:
        inject = next(f for f in app.template_context_processors[None]
                      if f.__name__ == "inject_site_release")
        assert inject()["site_release"] is expected
        assert inject()["site_release"] is expected
    assert loader.call_count == 2


def test_requests_keep_startup_snapshot_after_git_and_notes_change(client, app, repo, monkeypatch):
    git(repo, "tag", "v2.3")
    original = release.load_release_snapshot(repo)
    monkeypatch.setitem(app.extensions, "site_release", original)
    (repo / "docs" / "changelog.md").write_text(
        "## [v2.4]\n- New published note\n", encoding="utf-8"
    )
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "Next release")
    git(repo, "tag", "v2.4")
    with monkeypatch.context() as locked:
        locked.setattr(release, "_git", Mock(side_effect=AssertionError("Git during request")))
        locked.setattr(Path, "read_text", Mock(side_effect=AssertionError("File read during request")))
        for _ in range(2):
            response = client.get("/changelog?file=../../local_config.py")
            assert response.status_code == 200
            page = html.fromstring(response.get_data(as_text=True))
            assert page.xpath('//dd[@class="current-release-label"]/text()') == ["v2.3"]
            assert "Original published note" in page.text_content()
            assert "New published note" not in page.text_content()
            assert client.get("/r/all").status_code == 200
    fresh = release.load_release_snapshot(repo)
    assert fresh.version.tag == "v2.4"
    assert fresh.version.commit != original.version.commit
    assert "New published note" in fresh.changelog.entries[0].body_html


def test_anonymous_changelog_and_main_content_release_links(client, app, monkeypatch):
    notes = release.render_changelog("## [v2.4]\n- Newer record\n" + NOTES)
    snapshot = release.ReleaseSnapshot(release.VersionInfo("tagged", SHA, "v2.3"), notes)
    monkeypatch.setitem(app.extensions, "site_release", snapshot)
    for path in ("/changelog", "/", "/help", "/login", "/r/all"):
        response = client.get(path)
        assert response.status_code == 200
        page = html.fromstring(response.get_data(as_text=True))
        lines = page.xpath('//nav[@aria-label="版本与更新日志"]')
        assert len(lines) == 1
        assert not page.xpath('//nav[@id="sidebar"]//nav[@aria-label="版本与更新日志"]')
        assert lines[0].xpath('ancestor::div[@id="content"]')
        # The compact version line must survive the standalone copyright hide.
        assert not lines[0].xpath('ancestor::div[@id="footer"]')
        assert "main-release-footer" in lines[0].getparent().get("class", "").split()
        for line in lines:
            assert line.xpath('.//a[@class="release-version"]/@href') == ["/changelog#v2-3"]
            assert line.xpath('.//a[@class="release-version"]/text()') == ["v2.3"]
            assert line.xpath('.//a[@class="release-commit"]/code/text()') == [SHA[:7]]
            assert line.xpath('.//a[@class="release-commit"]/@href') == [f"{release.REPOSITORY_URL}/commit/{SHA}"]
            assert not line.xpath('.//a[@class="release-changelog"]/@target')
    page = html.fromstring(client.get("/changelog").get_data(as_text=True))
    assert page.xpath('//dd[@class="current-release-label"]/text()') == ["v2.3"]
    assert page.xpath('//a[@class="release-full-commit"]/code/text()') == [SHA]
    assert page.xpath('//section[contains(@class,"changelog-entry")]/h2/@id') == ["v2-4", "v2-3", "v2-2"]
    assert "Secret upcoming" not in page.text_content()


@pytest.mark.parametrize("available", [True, False])
def test_missing_current_record_has_no_dead_fragment(client, app, monkeypatch, available):
    snapshot = release.ReleaseSnapshot(
        release.VersionInfo("tagged", SHA, "v2.9"), release.Changelog(available=available)
    )
    monkeypatch.setitem(app.extensions, "site_release", snapshot)
    page = html.fromstring(client.get("/changelog").get_data(as_text=True))
    assert page.xpath('//a[@class="release-version"]/@href') == ["/changelog"]
    assert "当前版本记录尚未补录" in page.text_content()
    if not available:
        assert "更新记录暂不可用" in page.text_content()


def test_version_unavailable_and_preview_are_clear(client, app, monkeypatch):
    for info, text in [(release.VersionInfo(), "版本信息暂不可用"),
                       (release.VersionInfo("untagged", SHA, dirty=True), "未打标签 + 本地修改")]:
        monkeypatch.setitem(app.extensions, "site_release", release.ReleaseSnapshot(info, release.Changelog()))
        response = client.get("/changelog")
        assert response.status_code == 200
        page = html.fromstring(response.get_data(as_text=True))
        assert text in page.text_content()
        if info.commit is None:
            assert not page.xpath('//a[@class="release-commit" or @class="release-full-commit"]')
        else:
            assert "预览代码" in page.text_content()


def test_git_environment_cannot_select_another_repository(repo, monkeypatch):
    git(repo, "tag", "v2.3")
    expected = git(repo, "rev-parse", "HEAD")
    other = repo.parent / "ops"
    other.mkdir()
    git(other, "init", "-q", "--initial-branch=main")
    (other / "other.txt").write_text("different repository", encoding="utf-8")
    git(other, "add", ".")
    git(other, "commit", "-q", "-m", "Other repo")
    git(other, "tag", "v9.0")
    for key, value in [("GIT_DIR", other / ".git"), ("GIT_WORK_TREE", other),
                       ("GIT_INDEX_FILE", other / ".git" / "index")]:
        monkeypatch.setenv(key, str(value))
    info = release.read_version(repo)
    assert info.commit == expected and info.tag == "v2.3" and not info.dirty


def test_git_worktree_file_and_unrelated_cwd_are_supported(repo, monkeypatch):
    git(repo, "tag", "v2.3")
    linked = repo.parent / "linked"
    git(repo, "worktree", "add", "--detach", str(linked), "HEAD")
    assert (linked / ".git").is_file()
    monkeypatch.chdir(repo / "docs")
    assert release.read_version(linked).label == "v2.3"


def test_git_inspection_does_not_refresh_index(repo):
    index = repo / ".git" / "index"
    before = (index.read_bytes(), index.stat().st_mtime_ns)
    release.read_version(repo)
    assert (index.read_bytes(), index.stat().st_mtime_ns) == before


def test_git_directory_stat_permission_failure_is_nonfatal(repo, monkeypatch):
    monkeypatch.setattr(Path, "exists", Mock(side_effect=PermissionError("private directory")))
    assert release.read_version(repo).status == "unavailable"


def test_local_untagged_commits_do_not_create_unpushed_github_links(client, app, monkeypatch):
    info = release.VersionInfo("untagged", SHA)
    monkeypatch.setitem(app.extensions, "site_release", release.ReleaseSnapshot(info, release.Changelog()))
    page = html.fromstring(client.get("/changelog").get_data(as_text=True))
    assert SHA in page.text_content()
    assert not page.xpath('//a[contains(@href,"github.com/everbird/ohmywod/commit/")]')


def test_real_changelog_is_unique_and_contains_recent_versions():
    notes = release.render_changelog((release.PROJECT_ROOT / "docs" / "changelog.md").read_text(encoding="utf-8"))
    assert [e.version for e in notes.entries] == ["v2.3", "v2.2", "v2.1"]
    assert "[Unreleased]" not in "".join(e.body_html for e in notes.entries)
