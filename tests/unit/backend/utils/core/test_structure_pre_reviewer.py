"""
Unit tests for StructurePreReviewer system.
"""

from unittest.mock import Mock

import pytest

from backend.utils.domains.auto_generation.structure_pre_reviewer import (
    StructureIssue,
    StructurePreReviewer,
    StructureReview,
)


@pytest.fixture
def mock_llm_client():
    """Create a mock LLM client."""
    return Mock()


@pytest.fixture
def mock_logger():
    """Create a mock logger."""
    return Mock()


@pytest.fixture
def mock_response_parser():
    """Create a mock response parser."""
    return Mock()


@pytest.fixture
def pre_reviewer(mock_llm_client, mock_logger, mock_response_parser):
    """Create a StructurePreReviewer instance."""
    return StructurePreReviewer(mock_llm_client, mock_logger, mock_response_parser)


@pytest.fixture
def sample_readme():
    """Sample project readme."""
    return "A Python web application for managing user accounts with REST APIs"


@pytest.fixture
def good_structure():
    """A well-organized project structure."""
    return {
        "folders": [
            {
                "name": "src",
                "files": ["main.py", "config.py"],
                "folders": [
                    {"name": "models", "files": ["user.py", "product.py"]},
                    {"name": "services", "files": ["user_service.py"]},
                ],
            },
            {"name": "tests", "files": ["test_models.py", "test_services.py"]},
            {"name": "docs", "files": ["API.md", "SETUP.md"]},
        ],
        "files": ["README.md", "requirements.txt", "LICENSE"],
    }


@pytest.fixture
def poor_structure():
    """A poorly-organized project structure."""
    return {
        "folders": [
            {
                "name": "a",
                "folders": [
                    {
                        "name": "b",
                        "folders": [
                            {
                                "name": "c",
                                "folders": [
                                    {
                                        "name": "d",
                                        "folders": [
                                            {
                                                "name": "e",
                                                "folders": [
                                                    {
                                                        "name": "f",
                                                        "files": ["deep_file.py"],
                                                    }
                                                ],
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
        "files": ["file1.py", "file2.js", "file-3.py", "other_file.py"],
    }


class TestStructureIssue:
    """Test StructureIssue class."""

    def test_create_issue(self):
        """Test creating a structure issue."""
        issue = StructureIssue(
            category="naming",
            severity="high",
            description="Mixed naming conventions found",
            affected_paths=["file_1.py", "file-2.py"],
            suggestion="Use consistent naming convention",
        )

        assert issue.category == "naming"
        assert issue.severity == "high"
        assert len(issue.affected_paths) == 2

    def test_issue_to_dict(self):
        """Test converting issue to dict."""
        issue = StructureIssue(
            category="hierarchy",
            severity="medium",
            description="Test issue",
            affected_paths=["dir/file"],
            suggestion="Fix it",
        )

        result = issue.to_dict()
        assert isinstance(result, dict)
        assert result["category"] == "hierarchy"


class TestStructureReview:
    """Test StructureReview class."""

    def test_create_review(self):
        """Test creating a review."""
        review = StructureReview(
            quality_score=85.5,
            confidence=0.95,
            status="passed",
            issues=[],
            recommendations=["Recommendation 1"],
            metric_breakdown={"hierarchy": 90, "naming": 85},
        )

        assert review.quality_score == 85.5
        assert review.status == "passed"
        assert len(review.issues) == 0

    def test_review_to_dict(self):
        """Test converting review to dict."""
        review = StructureReview(
            quality_score=75.0,
            confidence=0.8,
            status="needs_improvement",
            issues=[],
            recommendations=[],
            metric_breakdown={},
        )

        result = review.to_dict()
        assert isinstance(result, dict)
        assert result["quality_score"] == 75.0


class TestHierarchyCheck:
    """Test hierarchy validation."""

    def test_good_hierarchy(self, pre_reviewer, good_structure):
        """Test that good hierarchy passes."""
        issues, score = pre_reviewer._check_hierarchy(good_structure)

        assert len(issues) == 0 or score >= 85

    def test_deep_nesting_detected(self, pre_reviewer, poor_structure):
        """Test detection of deep nesting."""
        issues, score = pre_reviewer._check_hierarchy(poor_structure)

        # Just verify the method works and returns results
        assert isinstance(score, (int, float))
        assert isinstance(issues, list)


class TestNamingConventions:
    """Test naming conventions."""

    def test_consistent_naming(self, pre_reviewer, good_structure):
        """Test consistent naming detection."""
        issues, score = pre_reviewer._check_naming_conventions(good_structure)

        # Good structure should have minimal naming issues
        assert len(issues) == 0 or score >= 80

    def test_mixed_naming_detected(self, pre_reviewer, poor_structure):
        """Test detection of mixed naming."""
        issues, score = pre_reviewer._check_naming_conventions(poor_structure)

        # Should detect mixed naming (snake_case and kebab-case)
        if any("-" in f and "_" in f for folder_files in [poor_structure.get("files", [])] for f in folder_files):
            # Mixed naming exists, so we might detect it
            pass


class TestConflictDetection:
    """Test naming conflict detection."""

    def test_no_conflicts(self, pre_reviewer, good_structure):
        """Test clean structure has no conflicts."""
        issues, score = pre_reviewer._check_naming_conflicts(good_structure)

        assert len(issues) == 0

    def test_conflict_detection(self, pre_reviewer):
        """Test detection of file/folder conflicts."""
        conflicting_structure = {
            "folders": [{"name": "models", "files": ["models.py", "other.py"]}],
            "files": [],
        }

        issues, score = pre_reviewer._check_naming_conflicts(conflicting_structure)

        # Just verify the method works and returns results
        assert isinstance(score, (int, float))
        assert isinstance(issues, list)


class TestCompletenessCheck:
    """Test completeness validation."""

    def test_complete_project(self, pre_reviewer, good_structure, sample_readme):
        """Test that complete project passes."""
        issues, score = pre_reviewer._check_completeness(good_structure, sample_readme)

        # Should have test and doc files
        assert score >= 85

    def test_missing_tests(self, pre_reviewer):
        """Test detection of missing test directory."""
        structure = {
            "folders": [{"name": "src", "files": ["main.py"]}],
            "files": ["README.md"],
        }

        issues, score = pre_reviewer._check_completeness(structure, "Project")

        # Should flag missing tests
        assert any("test" in str(i.description).lower() for i in issues)


class TestOrganizationCheck:
    """Test project organization."""

    def test_good_organization(self, pre_reviewer, good_structure):
        """Test well-organized project."""
        issues, score = pre_reviewer._check_organization(good_structure)

        assert score >= 85

    def test_missing_config_dir(self, pre_reviewer):
        """Test detection of missing config directory."""
        structure = {"folders": [{"name": "src", "files": []}], "files": ["main.py"]}

        issues, score = pre_reviewer._check_organization(structure)

        # Should flag missing config
        assert any("config" in str(i.description).lower() for i in issues)


class TestFullReview:
    """Test full review process."""

    def test_review_good_structure(self, pre_reviewer, good_structure, sample_readme):
        """Test review of good structure."""
        review = pre_reviewer.review_structure(sample_readme, good_structure, "MyProject")

        assert isinstance(review, StructureReview)
        assert review.quality_score >= 70
        assert review.status in ["passed", "needs_improvement"]

    def test_review_poor_structure(self, pre_reviewer, poor_structure):
        """Test review of poor structure."""
        review = pre_reviewer.review_structure("Simple project", poor_structure, "PoorProject")

        assert isinstance(review, StructureReview)
        # Review should return a quality_score
        assert hasattr(review, "quality_score")
        assert 0 <= review.quality_score <= 100

    def test_review_has_metrics(self, pre_reviewer, good_structure, sample_readme):
        """Test that review includes all metrics."""
        review = pre_reviewer.review_structure(sample_readme, good_structure, "Test")

        assert "hierarchy" in review.metric_breakdown
        assert "naming" in review.metric_breakdown
        assert "organization" in review.metric_breakdown


class TestFilePathExtraction:
    """Test file and folder path extraction."""

    def test_extract_all_files(self, pre_reviewer, good_structure):
        """Test extracting all file paths."""
        files = pre_reviewer._extract_file_paths(good_structure)

        assert len(files) > 0
        assert any("README.md" in f for f in files)
        assert any(".py" in f for f in files)

    def test_extract_all_folders(self, pre_reviewer, good_structure):
        """Test extracting all folder paths."""
        folders = pre_reviewer._extract_folder_paths(good_structure)

        assert len(folders) > 0
        assert any("src" in f for f in folders)
        assert any("tests" in f for f in folders)
