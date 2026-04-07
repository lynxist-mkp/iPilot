from __future__ import annotations

from pathlib import Path


TEXT_SUFFIXES: tuple[str, ...] = (".md", ".markdown", ".txt")


def _ensure_within_root(path: Path, workspace_root: Path) -> None:
    root = workspace_root.expanduser().resolve()
    candidate = path.expanduser().resolve()
    if candidate == root:
        return
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"path escapes workspace root: {candidate}") from exc


def _dedupe_sorted(paths: list[Path]) -> list[Path]:
    seen: set[str] = set()
    result: list[Path] = []
    for path in sorted(paths, key=lambda item: item.as_posix()):
        key = path.as_posix()
        if key in seen:
            continue
        seen.add(key)
        result.append(path)
    return result


def resolve_input_paths(workspace_root: Path, raw_paths: list[str]) -> list[Path]:
    workspace_root = workspace_root.expanduser().resolve()
    resolved: list[Path] = []

    for raw in raw_paths:
        candidate = Path(raw).expanduser()
        if candidate.is_absolute():
            absolute = candidate.resolve()
        else:
            absolute = (workspace_root / candidate).resolve()

        if not absolute.exists():
            raise FileNotFoundError(f"path does not exist: {absolute}")

        _ensure_within_root(absolute, workspace_root)
        resolved.append(absolute)

    return _dedupe_sorted(resolved)


def collect_indexable_files(
    workspace_root: Path,
    raw_paths: list[str],
    *,
    text_suffixes: tuple[str, ...] = TEXT_SUFFIXES,
) -> list[Path]:
    indexable: list[Path] = []
    candidates = resolve_input_paths(workspace_root, raw_paths)

    for candidate in candidates:
        if candidate.is_file():
            if candidate.suffix.lower() in text_suffixes:
                indexable.append(candidate)
            continue

        for child in candidate.rglob("*"):
            if not child.is_file():
                continue
            if child.suffix.lower() not in text_suffixes:
                continue
            _ensure_within_root(child, workspace_root)
            indexable.append(child.resolve())

    return _dedupe_sorted(indexable)
