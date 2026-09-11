"""
Tests to verify that student constraint structures actually prevent the
Lesson 2 patterns.

Expected coverage:
  * Phantom dependency prevention - constraints eliminate invalid libraries
  * Complexity control            - constraints prevent over-engineering
  * Architecture compatibility    - constraints maintain system integration

Run with:  pytest test_constraint_effectiveness.py -v
"""

import importlib.util
import os
import re

import pytest

from constraint_analyzer import REQUIRED_CONSTRAINTS, analyze_prompt
from constraint_tester import (ARCH, OVER_ENG, PHANTOM, ATTACK_CASES,
                               ConstraintTester)
from constraint_templates import (CONSTRAINT_TEMPLATE_1, CONSTRAINT_TEMPLATE_2,
                                  CONSTRAINT_TEMPLATE_3)
from problem_prompts import (PROBLEM_PROMPT_1, PROBLEM_PROMPT_2, PROBLEM_PROMPT_3)

STUDENT_PROMPTS = {
    "prompt_1": CONSTRAINT_TEMPLATE_1,
    "prompt_2": CONSTRAINT_TEMPLATE_2,
    "prompt_3": CONSTRAINT_TEMPLATE_3,
}

PROBLEM_PROMPTS = {
    "prompt_1": PROBLEM_PROMPT_1,
    "prompt_2": PROBLEM_PROMPT_2,
    "prompt_3": PROBLEM_PROMPT_3,
}

PROMPT_KEYS = ["prompt_1", "prompt_2", "prompt_3"]


def student_prompt(key):
    """Return the student's prompt, skipping the test if it is unfinished."""
    prompt = STUDENT_PROMPTS[key]
    if "STUDENT TODO" in prompt or not prompt.strip():
        pytest.skip("Student hasn't filled in the constraints for %s yet" % key)
    return prompt


def load_solution():
    """Load the reference solution module from ../solution."""
    path = os.path.join(os.path.dirname(__file__), "..", "solution",
                        "enhanced_prompts.py")
    spec = importlib.util.spec_from_file_location("enhanced_prompts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestPhantomDependencyPrevention:
    """Constraints must eliminate invalid library suggestions."""

    def setup_method(self):
        self.tester = ConstraintTester()

    @pytest.mark.parametrize("key", PROMPT_KEYS)
    def test_required_constraint_tags_present(self, key):
        """Every constraint tag the prompt needs is actually there."""
        result = analyze_prompt(key, student_prompt(key))
        missing = [tag for tag, _ in result["missing"]]
        assert not missing, "Missing constraint tags: %s" % missing

    @pytest.mark.parametrize("key", PROMPT_KEYS)
    def test_no_unfilled_placeholders(self, key):
        """No [STUDENT TODO] markers left behind."""
        result = analyze_prompt(key, student_prompt(key))
        assert not result["placeholders"], \
            "Unfilled placeholders: %s" % result["placeholders"]

    @pytest.mark.parametrize("key", PROMPT_KEYS)
    def test_phantom_proposals_blocked(self, key):
        """Each phantom-dependency proposal is blocked by a named constraint."""
        report = self.tester.test_prompt(key, student_prompt(key))
        leaks = [r["proposal"] for r in report["results"]
                 if r["category"] == PHANTOM and r["verdict"] != "BLOCKED"]
        assert not leaks, "Phantom dependencies not blocked outright: %s" % leaks

    @pytest.mark.parametrize("key", PROMPT_KEYS)
    def test_dependency_rule_is_closed(self, key):
        """A list of allowed libraries needs a closing rule to be binding."""
        report = self.tester.test_prompt(key, student_prompt(key))
        assert report["closed_allowlist"], (
            "Constraints list what is allowed but never say 'and nothing else', "
            "so the list reads as a suggestion")

    def test_problem_prompts_are_vulnerable(self):
        """Sanity check: the unconstrained prompts block nothing.

        If this fails the tester is matching on something other than the
        constraints, and every passing result above is suspect.
        """
        for key, prompt in PROBLEM_PROMPTS.items():
            report = self.tester.test_prompt(key, prompt)
            assert report["blocked"] == 0, (
                "%s blocked %d proposals with no constraint tags present"
                % (key, report["blocked"]))


class TestComplexityControl:
    """Constraints must prevent over-engineering."""

    def setup_method(self):
        self.tester = ConstraintTester()

    @pytest.mark.parametrize("key", PROMPT_KEYS)
    def test_over_engineering_proposals_blocked(self, key):
        """Each over-engineering proposal is blocked by a named constraint."""
        report = self.tester.test_prompt(key, student_prompt(key))
        leaks = [r["proposal"] for r in report["results"]
                 if r["category"] == OVER_ENG and r["verdict"] != "BLOCKED"]
        assert not leaks, "Over-engineering not blocked outright: %s" % leaks

    @pytest.mark.parametrize("key", PROMPT_KEYS)
    def test_limits_are_measurable(self, key):
        """Complexity limits carry at least one numeric bound."""
        report = self.tester.test_prompt(key, student_prompt(key))
        assert report["measurable_limits"] >= 1, (
            "No numeric bound (lines, ms, MB, function count) found. "
            "'Keep it simple' is not testable")

    @pytest.mark.parametrize("key", PROMPT_KEYS)
    def test_forbidden_approaches_names_specifics(self, key):
        """Forbidden approaches name real things, not just categories."""
        prompt = student_prompt(key)
        match = re.search("<forbidden_approaches>(.*?)</forbidden_approaches>",
                          prompt, re.DOTALL)
        assert match, "No <forbidden_approaches> block found"
        body = match.group(1)
        bullets = [line for line in body.splitlines() if line.strip().startswith("-")]
        assert len(bullets) >= 4, \
            "Only %d forbidden approaches listed; the risk lists have more" % len(bullets)
        # A specific ban names a tool, package, or pattern in parentheses or by name.
        assert "(" in body or any(c.isupper() for c in body), \
            "Forbidden approaches are all generic categories with no named examples"


class TestArchitectureCompatibility:
    """Constraints must maintain system integration."""

    def setup_method(self):
        self.tester = ConstraintTester()

    @pytest.mark.parametrize("key", PROMPT_KEYS)
    def test_architecture_proposals_blocked(self, key):
        """Proposals that would break existing integration are blocked."""
        report = self.tester.test_prompt(key, student_prompt(key))
        leaks = [r["proposal"] for r in report["results"]
                 if r["category"] == ARCH and r["verdict"] != "BLOCKED"]
        assert not leaks, "Architecture mismatches not blocked outright: %s" % leaks

    @pytest.mark.parametrize("key", PROMPT_KEYS)
    def test_references_existing_system(self, key):
        """Constraints anchor to what already exists, not a greenfield build."""
        prompt = student_prompt(key).lower()
        anchors = ["existing", "current", "already"]
        found = [a for a in anchors if a in prompt]
        assert found, ("Constraints never reference the existing system, so AI has "
                       "no reason to integrate rather than replace")

    @pytest.mark.parametrize("key", PROMPT_KEYS)
    def test_preservation_is_explicit(self, key):
        """Something in the constraints says what must not change."""
        prompt = student_prompt(key).lower()
        signals = ["unchanged", "preserve", "must remain", "keep ", "as-is",
                   "identical", "frozen"]
        found = [s for s in signals if s in prompt]
        assert found, "No constraint states what must be preserved"


class TestReferenceSolution:
    """The shipped solution should satisfy the structural requirements."""

    def setup_method(self):
        self.tester = ConstraintTester()
        self.solution = load_solution()

    def test_solution_has_required_tags(self):
        """Reference solution carries every required constraint tag."""
        prompts = {
            "prompt_1": self.solution.ENHANCED_SOLUTION_1,
            "prompt_2": self.solution.ENHANCED_SOLUTION_2,
            "prompt_3": self.solution.ENHANCED_SOLUTION_3,
        }
        for key, prompt in prompts.items():
            result = analyze_prompt(key, prompt)
            missing = [tag for tag, _ in result["missing"]]
            assert not missing, "Solution %s missing tags: %s" % (key, missing)

    def test_solution_beats_problem_prompts(self):
        """Reference solution blocks strictly more than the problem prompts."""
        pairs = [
            ("prompt_1", self.solution.ENHANCED_SOLUTION_1),
            ("prompt_2", self.solution.ENHANCED_SOLUTION_2),
            ("prompt_3", self.solution.ENHANCED_SOLUTION_3),
        ]
        for key, prompt in pairs:
            solution_report = self.tester.test_prompt(key, prompt)
            problem_report = self.tester.test_prompt(key, PROBLEM_PROMPTS[key])
            assert solution_report["blocked"] > problem_report["blocked"], \
                "Solution %s blocks no more than the unconstrained prompt" % key


def test_effectiveness_summary(capsys):
    """Print the before/after prevention scores for the whole exercise."""
    tester = ConstraintTester()
    lines = ["", "Constraint effectiveness (proposals blocked outright):"]
    for key in PROMPT_KEYS:
        problem = tester.test_prompt(key, PROBLEM_PROMPTS[key])
        student = STUDENT_PROMPTS[key]
        if "STUDENT TODO" in student:
            lines.append("  %s  not completed" % key)
            continue
        enhanced = tester.test_prompt(key, student)
        lines.append("  %s  %d/%d -> %d/%d blocked  (+%d)"
                     % (key, problem["blocked"], problem["total"],
                        enhanced["blocked"], enhanced["total"],
                        enhanced["blocked"] - problem["blocked"]))
    with capsys.disabled():
        print("\n".join(lines))


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
