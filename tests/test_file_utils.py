"""Tests for file utilities."""

import pytest
from pathlib import Path
import tempfile

from documentor.utils.file_utils import (
    find_files,
    read_file,
    write_file,
    get_language_from_extension,
    is_test_file,
)


class TestFileUtils:
    def test_read_write_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "test.txt"
            content = "Hello, World!"
            write_file(path, content)
            assert read_file(path) == content

    def test_get_language_from_extension(self):
        assert get_language_from_extension(Path("test.py")) == "python"
        assert get_language_from_extension(Path("test.js")) == "javascript"
        assert get_language_from_extension(Path("test.ts")) == "typescript"
        assert get_language_from_extension(Path("test.go")) == "go"
        assert get_language_from_extension(Path("test.rs")) == "rust"
        assert get_language_from_extension(Path("test.txt")) is None

    def test_is_test_file(self):
        assert is_test_file(Path("test_module.py")) is True
        assert is_test_file(Path("module_test.py")) is True
        assert is_test_file(Path("test.py")) is True
        assert is_test_file(Path("module.py")) is False
        assert is_test_file(Path("main.py")) is False

    def test_find_files(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "main.py").write_text("print('hello')")
            (root / "test_main.py").write_text("def test(): pass")
            (root / "utils.py").write_text("def util(): pass")
            (root / "subdir").mkdir()
            (root / "subdir" / "helper.py").write_text("def help(): pass")

            include = ["**/*.py"]
            exclude = ["**/test*.py"]

            files = find_files(root, include, exclude)
            assert len(files) == 3  # main.py, utils.py, subdir/helper.py
            names = [f.name for f in files]
            assert "main.py" in names
            assert "utils.py" in names
            assert "helper.py" in names
            assert "test_main.py" not in names


if __name__ == "__main__":
    pytest.main([__file__, "-v"])