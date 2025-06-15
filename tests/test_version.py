import subprocess
import unittest
from unittest.mock import MagicMock, patch
import warnings

from amqtt.version import get_git_changeset, get_version


class TestVersionFunctions(unittest.TestCase):
    @patch("amqtt.version.warnings.warn")
    def test_get_version(self, mock_warn):
        """Test get_version returns amqtt.__version__ and raises a deprecation warning."""
        with patch("amqtt.__version__", "1.2.3"):
            version = get_version()
            assert version == "1.2.3"
            mock_warn.assert_called_once_with(
                "amqtt.version.get_version() is deprecated, use amqtt.__version__ instead",
                stacklevel=3,
            )

    def test_get_version_no_warning(self):
        """Test get_version does not trigger a warning when explicitly suppressed."""
        with patch("amqtt.__version__", "1.2.3"), warnings.catch_warnings(record=True) as captured_warnings:
            warnings.simplefilter("ignore")
            version = get_version()
            assert version == "1.2.3"
            assert len(captured_warnings) == 0  # No warnings should be captured

    @patch("amqtt.version.Path")
    @patch("amqtt.version.shutil.which")
    @patch("amqtt.version.subprocess.Popen")
    def test_get_git_changeset(self, mock_popen, mock_which, mock_path):
        """Test get_git_changeset returns the correct timestamp or None on failure."""
        # Mock the repo directory
        mock_repo_dir = MagicMock()
        mock_repo_dir.is_dir.return_value = True
        mock_path.return_value.resolve.return_value.parent.parent = mock_repo_dir

        # Mock git executable check
        mock_which.return_value = True

        # Mock subprocess.Popen for git log with context manager behavior
        mock_process = MagicMock()
        mock_process.communicate.return_value = ("1638352940", "")
        mock_process.returncode = 0
        mock_popen.return_value.__enter__.return_value = mock_process

        # Call the function
        changeset = get_git_changeset()

        # Verify the results
        assert changeset == "20211201100220"  # Matches timestamp conversion
        mock_which.assert_called_once_with("git")
        mock_popen.assert_called_once_with(
            ["git", "log", "--pretty=format:%ct", "--quiet", "-1", "HEAD"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=mock_repo_dir,
            universal_newlines=True,
        )

        # Test invalid directory
        mock_repo_dir.is_dir.return_value = False
        changeset = get_git_changeset()
        assert changeset is None

        # Test missing git
        mock_repo_dir.is_dir.return_value = True
        mock_which.return_value = False
        changeset = get_git_changeset()
        assert changeset is None

        # Test git command failure
        mock_which.return_value = True
        mock_process.returncode = 1
        mock_process.communicate.return_value = ("", "Some error")
        changeset = get_git_changeset()
        assert changeset is None
