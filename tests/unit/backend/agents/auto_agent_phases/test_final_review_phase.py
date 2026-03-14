"""Unit tests for FinalReviewPhase — git decision gate and push helpers."""

import pytest
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------


def _make_context():
    """Return a minimal PhaseContext mock."""
    ctx = MagicMock()
    ctx.logger = MagicMock()
    ctx.event_publisher = MagicMock()
    ctx.event_publisher.publish = MagicMock()
    ctx.file_completeness_checker = MagicMock()
    ctx.project_reviewer = MagicMock()
    ctx.file_manager = MagicMock()
    ctx.project_reviewer.review.return_value = "# Review content"
    ctx.file_completeness_checker.get_validation_summary.return_value = {}
    return ctx


def _make_phase():
    from backend.agents.auto_agent_phases.final_review_phase import FinalReviewPhase

    return FinalReviewPhase(context=_make_context())


# ---------------------------------------------------------------------------
# _push_to_existing_repo
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPushToExistingRepo:
    """Tests for FinalReviewPhase._push_to_existing_repo."""

    def test_inserts_token_into_https_url(self):
        """Authenticated URL is constructed and passed to git remote add."""
        phase = _make_phase()
        git = MagicMock()
        git.repo_path = "/fake/repo"
        git._run_git.return_value = {"success": True, "output": "ok", "error": ""}

        phase._push_to_existing_repo(
            git,
            git_repo_url="https://github.com/org/repo.git",
            token="ghp_test",
            git_branch="main",
        )

        # First call must be "remote add origin <authenticated_url>"
        first_call_args = git._run_git.call_args_list[0][0]
        assert first_call_args[0] == "remote"
        assert first_call_args[1] == "add"
        assert first_call_args[2] == "origin"
        assert "ghp_test@github.com" in first_call_args[3]

    def test_returns_direct_push_method(self):
        """Return dict must include method='direct_push'."""
        phase = _make_phase()
        git = MagicMock()
        git._run_git.return_value = {"success": True, "output": "pushed", "error": ""}

        result = phase._push_to_existing_repo(
            git,
            git_repo_url="https://github.com/org/repo.git",
            token="ghp_test",
        )

        assert result["method"] == "direct_push"
        assert result["success"] is True

    def test_falls_back_to_master_when_main_fails(self):
        """When push to main fails, falls back to master."""
        phase = _make_phase()
        git = MagicMock()
        # First push (main) fails, second push (master) succeeds
        git._run_git.side_effect = [
            {"success": False, "output": "", "error": "branch not found"},  # remote add
            {"success": False, "output": "", "error": "main not found"},  # push main
            {"success": True, "output": "pushed", "error": ""},  # push master
        ]

        result = phase._push_to_existing_repo(
            git,
            git_repo_url="https://github.com/org/repo.git",
            token="ghp_test",
            git_branch="main",
        )

        assert result["success"] is True
        # Verify both branch names were tried
        push_calls = [c[0] for c in git._run_git.call_args_list]
        branch_args = [c for c in push_calls if "push" in c]
        assert any("main" in c for c in branch_args)
        assert any("master" in c for c in branch_args)


# ---------------------------------------------------------------------------
# _push_to_remote dispatch logic
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPushToRemoteDispatch:
    """Tests that _push_to_remote dispatches correctly based on git_repo_url."""

    def test_with_git_repo_url_calls_push_to_existing_repo(self):
        """When git_repo_url is provided, _push_to_existing_repo is used."""
        phase = _make_phase()
        phase._push_to_existing_repo = MagicMock(return_value={"success": True, "method": "direct_push"})

        git = MagicMock()
        result = phase._push_to_remote(
            git,
            repo_name="repo",
            token="tok",
            git_repo_url="https://github.com/org/repo.git",
            git_branch="main",
        )

        phase._push_to_existing_repo.assert_called_once_with(git, "https://github.com/org/repo.git", "tok", "main")
        assert result["method"] == "direct_push"

    @patch("subprocess.run")
    def test_without_git_repo_url_tries_gh_cli(self, mock_subprocess):
        """When no git_repo_url, gh repo create is attempted."""
        mock_subprocess.return_value = MagicMock(returncode=0, stdout="created", stderr="")
        phase = _make_phase()
        git = MagicMock()
        git.repo_path = "/fake"

        result = phase._push_to_remote(
            git,
            repo_name="new-repo",
            token="tok",
            git_repo_url="",
        )

        assert mock_subprocess.called
        cmd = mock_subprocess.call_args[0][0]
        assert "gh repo create" in cmd
        assert result["method"] == "gh_cli"

    @patch("subprocess.run")
    def test_without_url_falls_back_to_manual_push_on_gh_failure(self, mock_subprocess):
        """When gh CLI fails, falls back to manual git push."""
        mock_subprocess.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        phase = _make_phase()
        git = MagicMock()
        git.repo_path = "/fake"
        git._run_git.return_value = {"success": True, "output": "pushed", "error": ""}

        result = phase._push_to_remote(
            git,
            repo_name="new-repo",
            token="tok",
            organization="acme",
            git_repo_url="",
            git_branch="main",
        )

        # remote add + push must be called
        git._run_git.assert_called()
        assert result["method"] == "git_push"


# ---------------------------------------------------------------------------
# execute() — git decision gate
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestFinalReviewPhaseExecute:
    """Tests for the async execute() method of FinalReviewPhase."""

    def _base_kwargs(self, **overrides):
        base = {
            "file_paths": ["main.py"],
            "git_push": False,
            "git_token": "",
            "repo_name": "",
            "git_repo_url": "",
            "git_branch": "main",
        }
        base.update(overrides)
        return base

    def test_no_git_push_skips_git_operations(self, tmp_path):
        """When git_push=False, no git operations are performed."""
        phase = _make_phase()
        with patch("backend.agents.auto_agent_phases.final_review_phase.GitManager") as mock_git_cls:
            phase.execute(
                project_description="desc",
                project_name="proj",
                project_root=tmp_path,
                readme_content="# README",
                initial_structure={},
                generated_files={"main.py": ""},
                **self._base_kwargs(git_push=False),
            )
            mock_git_cls.assert_not_called()

    def test_git_push_with_url_initializes_repo_and_pushes(self, tmp_path):
        """When git_push=True and git_repo_url is set, git is initialized and pushed."""
        phase = _make_phase()
        phase._push_to_existing_repo = MagicMock(
            return_value={"success": True, "method": "direct_push", "output": "ok", "error": ""}
        )

        with patch("backend.agents.auto_agent_phases.final_review_phase.GitManager") as mock_git_cls:
            mock_git = MagicMock()
            mock_git_cls.return_value = mock_git
            mock_git._run_git.return_value = {"success": True}

            phase.execute(
                project_description="desc",
                project_name="proj",
                project_root=tmp_path,
                readme_content="# README",
                initial_structure={},
                generated_files={"main.py": ""},
                **self._base_kwargs(
                    git_push=True,
                    git_token="ghp_tok",
                    repo_name="my-repo",
                    git_repo_url="https://github.com/org/my-repo.git",
                ),
            )

        mock_git_cls.assert_called_once_with(repo_path=str(tmp_path))
        phase._push_to_existing_repo.assert_called_once()

    def test_git_push_true_repo_name_only_uses_gh_create_path(self, tmp_path):
        """When git_push=True but no git_repo_url, the gh-create path is taken."""
        phase = _make_phase()
        phase._push_to_existing_repo = MagicMock()

        with patch("backend.agents.auto_agent_phases.final_review_phase.GitManager") as mock_git_cls:
            mock_git = MagicMock()
            mock_git_cls.return_value = mock_git
            mock_git._run_git.return_value = {"success": True}

            with patch("subprocess.run") as mock_sub:
                mock_sub.return_value = MagicMock(returncode=0, stdout="created", stderr="")

                phase.execute(
                    project_description="desc",
                    project_name="proj",
                    project_root=tmp_path,
                    readme_content="# README",
                    initial_structure={},
                    generated_files={"main.py": ""},
                    **self._base_kwargs(
                        git_push=True,
                        git_token="tok",
                        repo_name="new-repo",
                        git_repo_url="",
                    ),
                )

        # _push_to_existing_repo must NOT have been called
        phase._push_to_existing_repo.assert_not_called()

    def test_git_push_no_token_only_inits_locally(self, tmp_path):
        """When git_push=True but no token, only a local git init is done."""
        phase = _make_phase()

        with patch("backend.agents.auto_agent_phases.final_review_phase.GitManager") as mock_git_cls:
            mock_git = MagicMock()
            mock_git_cls.return_value = mock_git
            mock_git._run_git.return_value = {"success": True}

            phase.execute(
                project_description="desc",
                project_name="proj",
                project_root=tmp_path,
                readme_content="# README",
                initial_structure={},
                generated_files={"main.py": ""},
                **self._base_kwargs(
                    git_push=True,
                    git_token="",
                    repo_name="no-token-repo",
                ),
            )

        # Remote push methods must not be called
        mock_git._run_git.assert_called()
        push_calls = [c[0] for c in mock_git._run_git.call_args_list]
        # None of the calls should be a "push" command
        assert not any("push" in c for c in push_calls)
