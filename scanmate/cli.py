# scanfiles/cli.py

import os

import toml
import typer

app = typer.Typer(
    help="A CLI tool for scanning directories in a tree structure with file counts and line counts."
)


def load_exclusions(toml_path: str = "excludes.toml"):
    """
    Loads folders and files to exclude from a TOML file.
    """
    if not os.path.exists(toml_path):
        typer.echo(f"Warning: '{toml_path}' does not exist. No exclusions defined.")
        return [], []

    data = toml.load(toml_path)
    exclude_folders = data.get("exclude", {}).get("folders", [])
    exclude_files = data.get("exclude", {}).get("files", [])

    return exclude_folders, exclude_files


def build_stats(path: str, exclude_folders: list, exclude_files: list) -> dict:
    """
    Recursively build a structure with file/folder counts and line counts.

    Returns a dict:
    {
      'type': 'dir' or 'file',
      'files_count': <int>,  # total files in this directory (recursively)
      'lines_count': <int>,  # total lines in this directory (recursively)
      'entries': {
          '<entry_name>': <subdict or None for files>
      }
    }
    or
    {
      'type': 'file',
      'files_count': 1,
      'lines_count': <lines_in_file>,
      'entries': None
    }
    """
    if os.path.isfile(path):
        # It's a file
        lines_count = 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                # Count lines naively
                lines_count = sum(1 for _ in f)
        except Exception:
            # Could not read, treat as 0 lines or mark as unreadable
            lines_count = "(unreadable)"

        return {
            "type": "file",
            "files_count": 1,
            "lines_count": lines_count,
            "entries": None,
        }

    # Otherwise it's a directory
    result = {"type": "dir", "files_count": 0, "lines_count": 0, "entries": {}}

    try:
        entries = sorted(os.listdir(path))
    except OSError as e:
        # e.g., permission error
        typer.echo(f"Cannot list directory '{path}': {e}")
        return result

    for entry in entries:
        # Skip if in exclude lists
        if entry in exclude_folders:
            continue
        if entry in exclude_files:
            continue

        full_path = os.path.join(path, entry)

        # Recurse
        child_stats = None
        if os.path.isdir(full_path):
            child_stats = build_stats(full_path, exclude_folders, exclude_files)
        else:
            child_stats = build_stats(full_path, exclude_folders, exclude_files)

        # Merge child stats into the parent's totals
        if child_stats["type"] == "file":
            if isinstance(child_stats["lines_count"], int):
                result["lines_count"] += child_stats["lines_count"]
            # Add 1 file to the parent's count
            result["files_count"] += 1
        else:
            # It's a directory
            result["files_count"] += child_stats["files_count"]
            # Accumulate lines
            if isinstance(child_stats["lines_count"], int):
                result["lines_count"] += child_stats["lines_count"]

        # Store in the tree
        result["entries"][entry] = child_stats

    return result


def print_stats(tree: dict, name: str, prefix: str = "", is_last: bool = True):
    """
    Pretty-print the nested dict as a tree structure,
    along with file and line counts.
    """
    connector = "└── " if is_last else "├── "

    # For directories, show "[X files, Y lines]"
    # For files, show "(Y lines)" if Y is int, else "(unreadable)"
    if tree["type"] == "dir":
        # e.g. "scanfiles [3 files, 252 lines]"
        files_str = (
            f"{tree['files_count']} file{'s' if tree['files_count'] != 1 else ''}"
        )
        lines_str = (
            f"{tree['lines_count']} line{'s' if tree['lines_count'] != 1 else ''}"
            if isinstance(tree["lines_count"], int)
            else "unreadable lines"
        )
        typer.echo(f"{prefix}{connector}{name} [{files_str}, {lines_str}]")

        # Print children
        entries = sorted(tree["entries"].items())
        for i, (child_name, child_dict) in enumerate(entries):
            child_is_last = i == len(entries) - 1
            new_prefix = prefix + ("    " if is_last else "│   ")
            print_stats(child_dict, child_name, new_prefix, child_is_last)

    else:
        # It's a file
        lines_str = (
            f"{tree['lines_count']} line{'s' if tree['lines_count'] != 1 else ''}"
            if isinstance(tree["lines_count"], int)
            else "(unreadable)"
        )
        # e.g. "cli.py (100 lines)"
        typer.echo(f"{prefix}{connector}{name} ({lines_str})")


@app.command("scan")
def scan_command(
    directory: str = typer.Argument(
        ".",
        help="Directory to scan in a tree view with file-count/line-count stats (default = current directory).",
    ),
    toml_path: str = typer.Option(
        "excludes.toml",
        "--exclude-config",
        "-e",
        help="Path to the TOML file defining exclusions.",
    ),
):
    """
    Recursively scans directories/files, printing them as a tree
    and showing file counts + total lines. Ignores items listed in excludes.toml.
    """
    exclude_folders, exclude_files = load_exclusions(toml_path)

    stats_tree = build_stats(directory, exclude_folders, exclude_files)

    # We'll label the top as the directory name + aggregated stats
    # so let's create a "fake parent" to unify the printing approach
    parent_name = os.path.basename(os.path.abspath(directory))
    # If directory is ".", set it to "." as the name
    if not parent_name:
        parent_name = directory

    print_stats(stats_tree, parent_name)


@app.command("init")
def init_excludes():
    """
    Creates a sample excludes.toml with typical entries for Python/JS projects.
    If excludes.toml exists, you will be prompted to overwrite it.
    """
    excludes_file = "excludes.toml"
    if os.path.exists(excludes_file):
        overwrite = typer.confirm(f"'{excludes_file}' already exists. Overwrite it?")
        if not overwrite:
            typer.echo("Aborting.")
            raise typer.Exit(code=1)

    sample_excludes = """[exclude]
folders = [
  ".git",
  "node_modules",
  ".venv",
  "venv",
  "dist",
  "build",
  "coverage",
  "__pycache__",
  ".pytest_cache",
  ".mypy_cache",
  ".idea",
  ".vscode"
]
files = [
  ".gitignore",
  "poetry.lock",
  ".eslintcache",
  "yarn.lock",
  "package-lock.json",
  "*.pyc"
]
"""

    try:
        with open(excludes_file, "w", encoding="utf-8") as f:
            f.write(sample_excludes.strip() + "\n")
        typer.echo(f"Sample '{excludes_file}' has been created.")
    except Exception as e:
        typer.echo(f"Could not create '{excludes_file}': {e}")


if __name__ == "__main__":
    app()
