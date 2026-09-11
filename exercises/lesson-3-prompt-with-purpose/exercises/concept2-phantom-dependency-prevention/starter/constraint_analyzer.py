"""
Identify which constraint tags a prompt is missing.

Step 2.2 of the exercise: run this against the problematic prompts to see the
constraint gaps, then run it again after filling in constraint_templates.py to
confirm the gaps are closed.

    python constraint_analyzer.py            # analyze the problem prompts
    python constraint_analyzer.py templates  # analyze your enhanced templates
"""

import importlib.util
import os
import re
import sys

from problem_prompts import (
    CONSTRAINT_PROBLEMS,
    PROBLEM_PROMPT_1,
    PROBLEM_PROMPT_2,
    PROBLEM_PROMPT_3,
)

# The constraint tags each prompt needs, and why. Derived from the phantom
# dependency and over-engineering risks catalogued in problem_prompts.py.
REQUIRED_CONSTRAINTS = {
    "prompt_1": {
        "allowed_libraries": "Blocks phantom packages (csv_turbo, pandas_accelerator)",
        "forbidden_approaches": "Blocks distributed frameworks and C extensions",
        "complexity_limits": "Keeps the fix to chunked reading, not a new system",
        "existing_environment": "States the real Python/pandas versions available",
    },
    "prompt_2": {
        "complexity_limits": "Caps a 2-line logging change at 2 lines",
        "scope_boundaries": "Confines edits to the one function",
        "forbidden_approaches": "Blocks decorators, strategy patterns, log frameworks",
        "preservation_requirements": "Locks the signature and business logic",
    },
    "prompt_3": {
        "platform_constraints": "Pins React Native / Node versions and platform limits",
        "existing_services": "Names the auth, database, and API already in place",
        "forbidden_approaches": "Blocks Kafka, Socket.io, Firebase, microservices",
        "integration_requirements": "Forces compatibility with current auth and API",
    },
}

# Tags that count as generic: present, but not specific enough to prevent a pattern.
GENERIC_TAGS = {"constraints"}

PLACEHOLDER_PATTERN = re.compile(r"\[STUDENT TODO[^\]]*\]")


def extract_tags(prompt):
    """Return the set of XML tag names used in a prompt."""
    return set(re.findall(r"<([a-z_]+)>", prompt))


def find_placeholders(prompt):
    """Return any unfilled [STUDENT TODO] markers left in a prompt."""
    return PLACEHOLDER_PATTERN.findall(prompt)


def analyze_prompt(prompt_key, prompt_text):
    """Compare one prompt against the constraint tags it should carry."""
    required = REQUIRED_CONSTRAINTS[prompt_key]
    present_tags = extract_tags(prompt_text)

    satisfied = []
    missing = []
    for tag, rationale in required.items():
        if tag in present_tags:
            satisfied.append((tag, rationale))
        else:
            missing.append((tag, rationale))

    has_generic_only = bool(present_tags & GENERIC_TAGS) and not satisfied

    return {
        "satisfied": satisfied,
        "missing": missing,
        "placeholders": find_placeholders(prompt_text),
        "generic_constraints_only": has_generic_only,
        "coverage": len(satisfied) / len(required),
    }


def report(prompt_key, title, prompt_text, show_risks=True):
    """Print the constraint gap analysis for a single prompt."""
    result = analyze_prompt(prompt_key, prompt_text)

    print(f"{title}")
    print("-" * len(title))
    print(f"Constraint coverage: {result['coverage']:.0%} "
          f"({len(result['satisfied'])}/{len(result['satisfied']) + len(result['missing'])} required tags)")

    if result["generic_constraints_only"]:
        print("\n⚠️  Has a bare <constraints> block with no typed constraint tags inside.")
        print("    A generic constraint does not name what is forbidden, so it prevents nothing.")

    if result["satisfied"]:
        print("\n✅ CONSTRAINTS PRESENT:")
        for tag, rationale in result["satisfied"]:
            print(f"   • <{tag}> — {rationale}")

    if result["missing"]:
        print("\n❌ CONSTRAINTS MISSING:")
        for tag, rationale in result["missing"]:
            print(f"   • <{tag}> — needed to: {rationale}")

    if result["placeholders"]:
        print(f"\n📝 UNFILLED PLACEHOLDERS: {len(result['placeholders'])}")
        for placeholder in result["placeholders"]:
            print(f"   • {placeholder}")

    if show_risks and result["missing"]:
        problems = CONSTRAINT_PROBLEMS[prompt_key]
        print("\n👻 EXPOSED TO PHANTOM DEPENDENCIES:")
        for risk in problems["phantom_dependency_risks"][:3]:
            print(f"   • {risk}")
        print("\n🏗️  EXPOSED TO OVER-ENGINEERING:")
        for risk in problems["over_engineering_risks"][:3]:
            print(f"   • {risk}")

    print("\n" + "=" * 80 + "\n")
    return result


def analyze_problem_prompts():
    """Step 2.2: identify the constraint gaps in the unconstrained prompts."""
    prompts = [
        ("prompt_1", "Problem 1: File Processing Optimization", PROBLEM_PROMPT_1),
        ("prompt_2", "Problem 2: Simple Logging Addition", PROBLEM_PROMPT_2),
        ("prompt_3", "Problem 3: Notification System", PROBLEM_PROMPT_3),
    ]

    print("=== CONSTRAINT GAP ANALYSIS: PROBLEM PROMPTS ===\n")
    return {key: report(key, title, text) for key, title, text in prompts}


def analyze_templates():
    """Re-run the analysis against your filled-in constraint templates."""
    from constraint_templates import (
        CONSTRAINT_TEMPLATE_1,
        CONSTRAINT_TEMPLATE_2,
        CONSTRAINT_TEMPLATE_3,
    )

    prompts = [
        ("prompt_1", "Template 1: File Processing Constraints", CONSTRAINT_TEMPLATE_1),
        ("prompt_2", "Template 2: Simple Logging Constraints", CONSTRAINT_TEMPLATE_2),
        ("prompt_3", "Template 3: Notification System Constraints", CONSTRAINT_TEMPLATE_3),
    ]

    print("=== CONSTRAINT GAP ANALYSIS: YOUR ENHANCED TEMPLATES ===\n")
    return {key: report(key, title, text, show_risks=False)
            for key, title, text in prompts}



def load_solution_prompts():
    """Load the reference solution prompts from ../solution."""
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        "solution", "enhanced_prompts.py")
    spec = importlib.util.spec_from_file_location("enhanced_prompts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [("prompt_1", "Solution 1: File Processing", module.ENHANCED_SOLUTION_1),
            ("prompt_2", "Solution 2: Discount Logging", module.ENHANCED_SOLUTION_2),
            ("prompt_3", "Solution 3: Notification System", module.ENHANCED_SOLUTION_3)]


def analyze_solution():
    """Step 4: run the same gap analysis over the reference solution."""
    print("=== CONSTRAINT GAP ANALYSIS: REFERENCE SOLUTION ===\n")
    return {key: report(key, title, text, show_risks=False)
            for key, title, text in load_solution_prompts()}


def print_summary(results):
    """Print a one-line verdict per prompt."""
    print("=== SUMMARY ===\n")
    for key, result in results.items():
        missing = [tag for tag, _ in result["missing"]]
        todos = len(result["placeholders"])
        if not missing and not todos:
            verdict = "✅ all required constraints present and filled in"
        elif not missing:
            verdict = f"⚠️  all tags present but {todos} placeholder(s) unfilled"
        else:
            verdict = f"❌ missing: {', '.join('<' + t + '>' for t in missing)}"
        print(f"{key.replace('_', ' ').title():<10} {result['coverage']:>4.0%}  {verdict}")
    print()


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "problems"

    if target == "templates":
        print_summary(analyze_templates())
    elif target == "solution":
        print_summary(analyze_solution())
    else:
        print_summary(analyze_problem_prompts())
        print("Next: fill the [STUDENT TODO] blocks in constraint_templates.py,")
        print("then run `python constraint_analyzer.py templates` to verify the gaps are closed.")
