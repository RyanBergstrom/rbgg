from pathlib import Path
from collections import defaultdict
import tiktoken

# ==========================================
# CONFIGURATION
# ==========================================

REPO_PATH = r"C:\Users\p211587\personal\dev\rbgg"

INCLUDE_EXTENSIONS = {
    ".py",
    ".ipynb",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".ini",
    ".cfg",
    ".md",
    ".txt",
    ".sql"
}

EXCLUDED_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".idea",
    ".vscode",
    "dist",
    "build",
    ".tox"
}

# GPT tokenizer
encoder = tiktoken.get_encoding("cl100k_base")

# ==========================================
# SCAN REPO
# ==========================================

total_tokens = 0
total_files = 0
by_extension = defaultdict(int)
largest_files = []

repo = Path(REPO_PATH)

for file in repo.rglob("*"):

    if not file.is_file():
        continue

    if any(part in EXCLUDED_DIRS for part in file.parts):
        continue

    if file.suffix.lower() not in INCLUDE_EXTENSIONS:
        continue

    try:
        text = file.read_text(
            encoding="utf-8",
            errors="ignore"
        )

        tokens = len(encoder.encode(text))

        total_tokens += tokens
        total_files += 1
        by_extension[file.suffix.lower()] += tokens

        largest_files.append(
            (
                tokens,
                str(file.relative_to(repo))
            )
        )

    except Exception as ex:
        print(f"Skipped {file}: {ex}")

# ==========================================
# OUTPUT
# ==========================================

print("\n=== REPOSITORY SUMMARY ===")
print(f"Files     : {total_files:,}")
print(f"Tokens    : {total_tokens:,}")

print("\n=== CONTEXT WINDOWS ===")

for size in (
    128_000,
    200_000,
    400_000,
    1_000_000,
):
    pct = total_tokens / size * 100
    print(
        f"{size:>9,}: "
        f"{pct:6.1f}% utilized"
    )

print("\n=== TOKENS BY FILE TYPE ===")

for ext, count in sorted(
    by_extension.items(),
    key=lambda x: x[1],
    reverse=True,
):
    print(f"{ext:<8} {count:>12,}")

print("\n=== LARGEST FILES ===")

largest_files.sort(reverse=True)

for tokens, name in largest_files[:20]:
    print(f"{tokens:>8,}  {name}")