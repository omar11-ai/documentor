"""Pytest configuration for DocuMentor tests."""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture
def temp_dir():
    """Create a temporary directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_python_project(temp_dir):
    """Create a sample Python project structure."""
    # Create project structure
    (temp_dir / "src").mkdir()
    (temp_dir / "src" / "main.py").write_text("""
def main():
    '''Entry point.'''
    print("Hello, World!")

if __name__ == "__main__":
    main()
""")

    (temp_dir / "src" / "utils.py").write_text("""
def helper(x: int) -> int:
    '''Helper function.'''
    return x * 2

class Calculator:
    '''Simple calculator.'''
    def add(self, a: int, b: int) -> int:
        return a + b
""")

    (temp_dir / "tests").mkdir()
    (temp_dir / "tests" / "test_utils.py").write_text("""
def test_helper():
    from src.utils import helper
    assert helper(5) == 10
""")

    (temp_dir / ".git").mkdir()
    (temp_dir / ".gitignore").write_text("__pycache__/\n*.pyc\n")

    return temp_dir


@pytest.fixture
def sample_git_repo(sample_python_project):
    """Initialize git repo with commits."""
    import subprocess
    repo = sample_python_project
    subprocess.run(["git", "init"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, capture_output=True)
    subprocess.run(["git", "add", "."], cwd=repo, capture_output=True)
    subprocess.run(["git", "commit", "-m", "Initial commit"], cwd=repo, capture_output=True)
    return repo