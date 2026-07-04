"""
Pydantic data models shared across all agents.
"""

from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel, Field


class TestStep(BaseModel):
    action: str = Field(description="User action or system event (e.g. 'click Login button')")
    expected: Optional[str] = Field(default=None, description="Expected result after action")


class TestRequirement(BaseModel):
    req_id: str = Field(description="Requirement ID, e.g. FR-FA-02")
    feature: str = Field(description="Feature/module name, e.g. 'Form Authentication'")
    url_path: str = Field(description="Relative URL path, e.g. /login")
    description: str = Field(description="Short description of what is being tested")
    preconditions: List[str] = Field(default_factory=list)
    steps: List[TestStep] = Field(default_factory=list)
    expected_outcome: str = Field(description="Overall expected outcome of the test")
    is_negative: bool = Field(default=False, description="True for negative/error scenarios")
    is_edge_case: bool = Field(default=False, description="True for edge case scenarios")
    tags: List[str] = Field(default_factory=list)


class RequirementsBundle(BaseModel):
    source_document: str
    total_requirements: int
    requirements: List[TestRequirement]


class ValidationIssue(BaseModel):
    issue_type: str = Field(
        description="One of: hallucination, missing_coverage, missing_edge_case, code_quality"
    )
    severity: str = Field(description="high | medium | low")
    req_id: Optional[str] = Field(default=None, description="Related requirement ID if applicable")
    test_file: Optional[str] = Field(default=None, description="Affected test file")
    description: str = Field(description="Clear description of the issue")
    fix_instruction: str = Field(description="Specific instruction to fix this issue")


class ValidationReport(BaseModel):
    iteration: int
    passed: bool = Field(description="True if no high/medium severity issues remain")
    total_issues: int
    issues: List[ValidationIssue]
    coverage_percentage: float = Field(description="Percentage of requirements with at least one test")
    summary: str = Field(description="Human-readable summary of findings")
