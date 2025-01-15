# tests/test_cli.py

import os
import shutil
from pathlib import Path
from unittest.mock import mock_open, patch

import pytest
from typer.testing import CliRunner

from scanmate.cli import app, build_stats, load_exclusions, print_stats

runner = CliRunner()


@pytest.fixture
def temp_dir(tmp_path):
    """
    A pytest fixture that sets up a temporary directory for testing.
    """
    # Create some files/folders inside tmp_path for testing
    (tmp_path / "file1.txt").write_text("Line1\nLine2\n")
    (tmp_path / "file2.txt").write_text("OnlyOneLine")
    sub_dir = tmp_path / "subdir"
    sub_dir.mkdir()
    (sub_dir / "nested.txt").write_text("NestedFileLine\nSecondLine")

    return tmp_path


def test_load_exclusions_no_file():
    """
    If excludes.toml doesn't exist, load_exclusions should return empty lists.
    """
    folders, files = load_exclusions("does_not_exist.toml")
    assert folders == []
    assert files == []


def test_load_exclusions_valid(tmp_path):
    """
    Test parsing a valid excludes.toml file.
    """
    toml_path = tmp_path / "excludes.toml"
    toml_content = """[exclude]
folders = [".git", "node_modules"]
files = [".gitignore", "*.pyc"]
"""
    toml_path.write_text(toml_content, encoding="utf-8")

    folders, files = load_exclusions(str(toml_path))
    assert ".git" in folders
    assert "node_modules" in folders
    assert ".gitignore" in files
    assert "*.pyc" in files


def test_build_stats_files(temp_dir):
    """
    Check that build_stats correctly counts files and lines.
    """
    stats = build_stats(str(temp_dir), [], [])
    assert stats["type"] == "dir"
    # We have 2 files at top-level + 1 file in subdir = 3 total
    assert stats["files_count"] == 3
    # file1 has 2 lines, file2 has 1 line, nested.txt has 2 lines = 5 total
    assert stats["lines_count"] == 5

    # Check entries
    entries = stats["entries"]
    assert "file1.txt" in entries
    assert "subdir" in entries
    assert entries["file1.txt"]["lines_count"] == 2
    assert entries["file2.txt"]["lines_count"] == 1


def test_build_stats_exclusion(temp_dir):
    """
    Exclude a file and folder, make sure they are not counted.
    """
    stats = build_stats(
        str(temp_dir), exclude_folders=["subdir"], exclude_files=["file2.txt"]
    )
    # file1 is included
    # file2 is excluded
    # subdir is excluded -> nested.txt is also excluded
    assert stats["files_count"] == 1  # only file1 remains
    assert stats["lines_count"] == 2  # only file1's 2 lines


def test_print_stats_capture(temp_dir):
    """
    Use Typer's CliRunner or a manual capture to ensure print_stats outputs the correct structure.
    """
    # Build stats normally
    stats = build_stats(str(temp_dir), [], [])

    # We'll capture the output of print_stats
    import sys
    from io import StringIO

    backup_stdout = sys.stdout
    try:
        sys.stdout = StringIO()
        print_stats(stats, "temp_dir")
        output = sys.stdout.getvalue()
    finally:
        sys.stdout = backup_stdout

    # Just do a basic check for text in the output
    assert "temp_dir [3 files, 5 lines]" in output
    # Check that a file was printed
    assert "file1.txt (2 lines)" in output


def test_scan_command_help():
    """
    Ensure the 'scan' command can show help.
    """
    result = runner.invoke(app, ["scan", "--help"])
    assert result.exit_code == 0
    assert "Directory to scan in a tree view" in result.output
    assert "file-count/line-count stats" in result.output


def test_init_command_abort(tmp_path):
    """
    If 'excludes.toml' exists and user says no, command should abort.
    """
    excludes_file = tmp_path / "excludes.toml"
    excludes_file.write_text("dummy data", encoding="utf-8")

    # Run 'init' with NO to overwrite
    with patch("typer.confirm", return_value=False):
        result = runner.invoke(app, ["init"], env={"PWD": str(tmp_path)})
        assert "Aborting." in result.output
        assert result.exit_code != 0  # or 1


def test_init_command_overwrite(tmp_path, monkeypatch):
    """
    If 'excludes.toml' exists and user says yes, it should be recreated.
    """
    excludes_file = tmp_path / "excludes.toml"
    excludes_file.write_text("dummy data", encoding="utf-8")

    # Change into tmp_path so 'init' sees excludes.toml in that directory
    monkeypatch.chdir(tmp_path)

    with patch("typer.confirm", return_value=True):
        result = runner.invoke(app, ["init"])
        assert "has been created." in result.output
        assert result.exit_code == 0

    new_content = excludes_file.read_text()
    assert "folders = [" in new_content
    assert "files = [" in new_content
