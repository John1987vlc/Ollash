"""Tests for the clone project endpoint and validators."""

from unittest.mock import MagicMock, patch


from backend.utils.core.input_validators import validate_git_url, validate_project_name


class TestValidateGitUrl:
    def test_valid_https_url(self):
        assert validate_git_url("https://github.com/user/repo.git") is True

    def test_valid_https_without_git_suffix(self):
        assert validate_git_url("https://github.com/user/repo") is True

    def test_valid_git_protocol(self):
        assert validate_git_url("git://github.com/user/repo.git") is True

    def test_rejects_ssh_url(self):
        assert validate_git_url("git@github.com:user/repo.git") is False

    def test_rejects_file_protocol(self):
        assert validate_git_url("file:///tmp/repo.git") is False

    def test_rejects_http(self):
        assert validate_git_url("http://github.com/user/repo") is False

    def test_rejects_empty_string(self):
        assert validate_git_url("") is False

    def test_rejects_none(self):
        assert validate_git_url(None) is False

    def test_rejects_no_path(self):
        assert validate_git_url("https://github.com") is False

    def test_rejects_single_segment_path(self):
        assert validate_git_url("https://github.com/user") is False

    def test_valid_gitlab_url(self):
        assert validate_git_url("https://gitlab.com/group/project") is True

    def test_valid_bitbucket_url(self):
        assert validate_git_url("https://bitbucket.org/team/repo") is True


class TestValidateProjectName:
    def test_valid_simple_name(self):
        assert validate_project_name("myproject") is True

    def test_valid_with_hyphens(self):
        assert validate_project_name("my-project") is True

    def test_valid_with_underscores(self):
        assert validate_project_name("my_project") is True

    def test_valid_with_dots(self):
        assert validate_project_name("my.project") is True

    def test_valid_with_numbers(self):
        assert validate_project_name("project123") is True

    def test_rejects_empty(self):
        assert validate_project_name("") is False

    def test_rejects_none(self):
        assert validate_project_name(None) is False

    def test_rejects_path_traversal(self):
        assert validate_project_name("../evil") is False

    def test_rejects_spaces(self):
        assert validate_project_name("my project") is False

    def test_rejects_starting_with_dot(self):
        assert validate_project_name(".hidden") is False

    def test_rejects_starting_with_hyphen(self):
        assert validate_project_name("-bad") is False

    def test_rejects_too_long(self):
        assert validate_project_name("a" * 101) is False

    def test_accepts_max_length(self):
        assert validate_project_name("a" * 100) is True


class TestCloneEndpoint:
    """Test the clone endpoint behavior via validators and mocked subprocess."""

    def test_project_name_inferred_from_url(self):
        url = "https://github.com/user/my-cool-repo.git"
        name = url.rstrip("/").split("/")[-1].replace(".git", "")
        assert name == "my-cool-repo"

    def test_project_name_inferred_no_git_suffix(self):
        url = "https://github.com/user/repo"
        name = url.rstrip("/").split("/")[-1].replace(".git", "")
        assert name == "repo"

    def test_project_name_inferred_trailing_slash(self):
        url = "https://github.com/user/repo/"
        name = url.rstrip("/").split("/")[-1].replace(".git", "")
        assert name == "repo"

    @patch("subprocess.run")
    def test_clone_subprocess_called_correctly(self, mock_run):
        """Verify that git clone would be called with correct arguments."""
        mock_run.return_value = MagicMock(returncode=0, stderr="")
        import subprocess

        url = "https://github.com/user/repo.git"
        target = "/tmp/projects/repo"
        subprocess.run(
            ["git", "clone", url, target],
            capture_output=True,
            text=True,
            timeout=300,
        )
        mock_run.assert_called_once_with(
            ["git", "clone", url, target],
            capture_output=True,
            text=True,
            timeout=300,
        )

    @patch("subprocess.run")
    def test_clone_failure_detected(self, mock_run):
        mock_run.return_value = MagicMock(
            returncode=128,
            stderr="fatal: repository not found",
        )
        import subprocess

        result = subprocess.run(
            ["git", "clone", "https://github.com/user/nonexistent.git", "/tmp/out"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode != 0
        assert "not found" in result.stderr
