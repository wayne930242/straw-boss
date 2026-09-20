"""Descriptor-relative access to the user-owned Jev recovery store."""
from __future__ import annotations

import os
import stat
import uuid
from contextlib import contextmanager
from pathlib import Path


def root() -> Path:
    return Path(os.environ.get("STRAW_BOSS_HOME", str(Path.home() / ".straw-boss"))) / "jev"


def _owned(info: os.stat_result, directory: bool) -> None:
    valid_type = stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)
    if info.st_uid != os.getuid() or not valid_type or (not directory and info.st_nlink != 1):
        raise ValueError("unsafe-jev-storage-path")


@contextmanager
def private_directory(path: Path):
    """Resolve the configured parent, then reject links within the store."""
    store = root().absolute()
    relative = path.absolute().relative_to(store)
    if ".." in relative.parts:
        raise ValueError("unsafe-jev-storage-path")
    base = store.parent.resolve()
    base.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(base, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        _owned(os.fstat(fd), True)
        for part in (store.name, *relative.parts):
            try:
                os.mkdir(part, 0o700, dir_fd=fd)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd)
            try:
                _owned(os.fstat(child), True)
                os.fchmod(child, 0o700)
            except BaseException:
                os.close(child)
                raise
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _open(directory: int, name: str, flags: int) -> int:
    fd = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
    try:
        _owned(os.fstat(fd), False)
        os.fchmod(fd, 0o600)
        return fd
    except BaseException:
        os.close(fd)
        raise


@contextmanager
def _copy_parent(path: Path):
    """Walk a physical path from root using POSIX ownership/mode boundaries."""
    if ".." in path.parts:
        raise ValueError("unsafe-jev-storage-path")
    path = path.absolute()
    parent = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        for part in path.parts[1:]:
            info = os.fstat(parent)
            if not stat.S_ISDIR(info.st_mode) or info.st_uid not in (0, os.getuid()):
                raise ValueError("unsafe-jev-copy-ancestor")
            # Sticky directories protect root/user-owned child entries from
            # replacement by other users, as in a conventional /private/tmp.
            if info.st_mode & 0o022 and not info.st_mode & stat.S_ISVTX:
                raise ValueError("writable-by-others-jev-copy-ancestor")
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = child
        info = os.fstat(parent)
        _owned(info, True)
        if info.st_mode & 0o022:
            raise ValueError("writable-by-others-jev-copy-parent")
        yield parent
    finally:
        os.close(parent)


@contextmanager
def private_copy_directory(path: Path):
    """Pin a new copy directory beneath a descriptor-validated ancestry."""
    if path.name in ("", ".", ".."):
        raise ValueError("unsafe-jev-storage-path")
    with _copy_parent(path.parent) as parent:
        os.mkdir(path.name, 0o700, dir_fd=parent)
        directory = os.open(path.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
        try:
            _owned(os.fstat(directory), True)
            os.fchmod(directory, 0o700)
            yield directory
            os.fsync(directory)
        finally:
            os.close(directory)


@contextmanager
def private_new_file(directory: int, name: str):
    """Create one private child exclusively through its pinned directory."""
    if name in ("", ".", "..") or Path(name).name != name:
        raise ValueError("unsafe-jev-storage-path")
    fd = _open(directory, name, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    with os.fdopen(fd, "w") as file:
        yield file
        file.flush()
        os.fsync(file.fileno())


@contextmanager
def private_file(path: Path, flags: int, mode: str):
    with private_directory(path.parent) as directory:
        fd = _open(directory, path.name, flags)
        with os.fdopen(fd, mode) as file:
            yield file


def private_read(path: Path) -> str:
    with private_file(path, os.O_RDONLY, "r") as file:
        return file.read()


def private_replace(path: Path, content: str) -> None:
    with private_directory(path.parent) as directory:
        try:
            existing = _open(directory, path.name, os.O_RDONLY)
        except FileNotFoundError:
            pass
        else:
            os.close(existing)
        temporary = f".tmp-{uuid.uuid4().hex}"
        fd = _open(directory, temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
        try:
            with os.fdopen(fd, "w") as file:
                file.write(content)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, path.name, src_dir_fd=directory, dst_dir_fd=directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass


def private_unlink(path: Path) -> None:
    with private_directory(path.parent) as directory:
        try:
            os.unlink(path.name, dir_fd=directory)
        except FileNotFoundError:
            pass
