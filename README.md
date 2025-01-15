# ScanMate

**ScanMate** is a Python package that scans directories in a tree structure, showing file counts and total lines. It also respects an `excludes.toml` file to skip specified folders or files (e.g., `.git`, `node_modules`, etc.).

## Installation

To install **ScanMate**, run:

```bash
pip install scanmate
```

After installation, the scanfiles command will be available.

1. Initialize a sample **excludes.toml**:

```bash
scanfiles init
```

2. Scan the current directory (showing a tree, file counts, and line counts):

```bash
scanfiles scan
```

3. Customize which folders/files to exclude by editing **excludes.toml**.

That’s it! Enjoy exploring your project structure with ScanMate.
