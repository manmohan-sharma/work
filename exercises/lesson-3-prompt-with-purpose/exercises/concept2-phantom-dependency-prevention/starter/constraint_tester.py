"""
Test whether your enhanced prompts actually prevent the Lesson 2 patterns.

The analyzer checks that constraint tags are *present*. This tester checks that
they *work*: each prompt is challenged with the concrete proposals an
unconstrained model would make, and each proposal is scored as

    BLOCKED  a constraint names this specific thing or its category
    WEAK     only a catch-all rule covers it, so a model may argue past it
    ALLOWED  nothing in the prompt prevents it

    python constraint_tester.py            # test your enhanced templates
    python constraint_tester.py baseline   # compare against the problem prompts

"""

import importlib.util
import os
import re
import sys
from typing import Dict, List

PHANTOM = "phantom_dependency"
OVER_ENG = "over_engineering"
ARCH = "architecture_mismatch"

# Proposals to challenge each prompt with, drawn from the risk lists in
# problem_prompts.py. "specific" signals mean a constraint names the thing or
# its category outright; "generic" signals are catch-all rules that only cover
# it by implication.
ATTACK_CASES = {
    "prompt_1": [
        {"proposal": "pip install csv_turbo for a 10x faster reader",
         "category": PHANTOM,
         "specific": ["verify on pypi"],
         "generic": ["requirements.txt"]},
        {"proposal": "Switch the reader to polars for zero-copy parsing",
         "category": PHANTOM,
         "specific": ["polars"],
         "generic": ["requirements.txt"]},
        {"proposal": "Use dask.dataframe to parallelize the parse",
         "category": PHANTOM,
         "specific": ["dask", "distributed comput"],
         "generic": ["requirements.txt"]},
        {"proposal": "Pass engine='pyarrow' to read_csv",
         "category": PHANTOM,
         "specific": ["pyarrow"],
         "generic": ["requirements.txt"]},
        {"proposal": "Compile the parse loop with Cython",
         "category": PHANTOM,
         "specific": ["cython", "c extension"],
         "generic": ["build toolchain", "requirements.txt"]},
        {"proposal": "Run the job on Spark for horizontal scale",
         "category": OVER_ENG,
         "specific": ["spark", "distributed comput"],
         "generic": ["single machine", "single-machine"]},
        {"proposal": "Add a Redis cache for parsed chunks",
         "category": OVER_ENG,
         "specific": ["caching layer", "intermediate database", "additional database",
                      "database solutions for temporary"],
         "generic": ["cloud service"]},
        {"proposal": "Refactor into a ChunkProcessor hierarchy with an abstract BaseReader",
         "category": OVER_ENG,
         "specific": ["no new classes", "no inheritance", "complex inheritance"],
         "generic": ["new functions"]},
        {"proposal": "Add a Celery queue so chunks are processed as jobs",
         "category": OVER_ENG,
         "specific": ["celery", "no queue"],
         "generic": ["distributed comput", "single machine", "single-machine"]},
        {"proposal": "Split file processing into its own microservice",
         "category": ARCH,
         "specific": ["microservice"],
         "generic": ["distributed comput", "single machine", "single-machine",
                     "existing function", "existing processing function"]},
    ],
    "prompt_2": [
        {"proposal": "Install loguru for nicer log formatting",
         "category": PHANTOM,
         "specific": ["loguru"],
         "generic": ["beyond standard library", "beyond the standard library",
                     "no new dependencies", "no new imports"]},
        {"proposal": "Add structlog so logs are structured",
         "category": PHANTOM,
         "specific": ["structlog", "structured"],
         "generic": ["beyond standard library", "beyond the standard library",
                     "no new dependencies"]},
        {"proposal": "Ship logs to Datadog for cross-service correlation",
         "category": PHANTOM,
         "specific": ["log correlation", "aggregation", "external service"],
         "generic": ["no new dependencies"]},
        {"proposal": "Wrap the function in a @log_execution decorator",
         "category": OVER_ENG,
         "specific": ["decorator"],
         "generic": ["no new functions"]},
        {"proposal": "Introduce a LoggerStrategy ABC so log sinks are swappable",
         "category": OVER_ENG,
         "specific": ["abstract base class", "strategy pattern"],
         "generic": ["no new functions"]},
        {"proposal": "Add logging.yaml with per-environment handlers",
         "category": OVER_ENG,
         "specific": ["configuration management", "logging configuration"],
         "generic": ["no new functions, classes, modules"]},
        {"proposal": "Emit logs via QueueHandler to protect checkout latency",
         "category": OVER_ENG,
         "specific": ["queued log", "no async", "asynchronous"],
         "generic": ["performance characteristics", "ms per call", "sub-1ms"]},
        {"proposal": "Add Prometheus counters for discount calls",
         "category": OVER_ENG,
         "specific": ["metrics"],
         "generic": ["no new dependencies"]},
        {"proposal": "Change the signature to accept an optional logger argument",
         "category": ARCH,
         "specific": ["function signature", "signature:"],
         "generic": ["no changes to calling code", "calling code"]},
    ],
    "prompt_3": [
        {"proposal": "Use the notification_master npm package",
         "category": PHANTOM,
         "specific": ["notification_master"],
         "generic": ["package.json", "external notification service", "third-party"]},
        {"proposal": "Use push_notification_pro for delivery",
         "category": PHANTOM,
         "specific": ["push_notification_pro"],
         "generic": ["package.json", "external notification service", "third-party"]},
        {"proposal": "Integrate the OneSignal SDK",
         "category": PHANTOM,
         "specific": ["onesignal"],
         "generic": ["package.json", "external notification service", "third-party"]},
        {"proposal": "Integrate Firebase Cloud Messaging",
         "category": PHANTOM,
         "specific": ["firebase", "fcm"],
         "generic": ["package.json", "native rebuild", "external notification service"]},
        {"proposal": "Use AWS SNS mobile push",
         "category": PHANTOM,
         "specific": ["sns"],
         "generic": ["package.json", "external notification service", "third-party"]},
        {"proposal": "Add Braze for engagement analytics",
         "category": PHANTOM,
         "specific": ["braze"],
         "generic": ["package.json", "analytics"]},
        {"proposal": "Use Socket.io for in-app message delivery",
         "category": OVER_ENG,
         "specific": ["socket.io", "websocket"],
         "generic": ["package.json"]},
        {"proposal": "Publish notification events to a Kafka topic",
         "category": OVER_ENG,
         "specific": ["kafka"],
         "generic": ["message queue"]},
        {"proposal": "Fan out delivery through Redis Streams",
         "category": OVER_ENG,
         "specific": ["redis"],
         "generic": ["message queue"]},
        {"proposal": "Extract notifications into a separate microservice",
         "category": OVER_ENG,
         "specific": ["microservice"],
         "generic": ["existing express", "current api", "existing api"]},
        {"proposal": "Model delivery status with event sourcing and CQRS",
         "category": OVER_ENG,
         "specific": ["event sourcing", "cqrs", "event-driven"],
         "generic": ["state machine"]},
        {"proposal": "Train a model to optimize per-user send times",
         "category": OVER_ENG,
         "specific": ["ml-driven", "ml-based", "machine learning", "send-time"],
         "generic": ["analytics"]},
        {"proposal": "Add a separate Postgres instance for preferences",
         "category": ARCH,
         "specific": ["no new datastore", "additional database", "no additional databases"],
         "generic": ["existing user", "mongodb", "existing primary database"]},
        {"proposal": "Add device-token auth for notification registration",
         "category": ARCH,
         "specific": ["per-device token", "second auth path"],
         "generic": ["existing jwt", "jwt authentication", "authentication and session",
                     "existing user authentication"]},
    ],
}

# Phrases that turn a list of libraries into a closed allowlist.
CLOSURE_PHRASES = [
    "nothing else", "not already in", "as frozen", "only", "no package that is not",
]

BLOCKED, WEAK, ALLOWED = "BLOCKED", "WEAK", "ALLOWED"


class ConstraintTester:
    """Challenge a prompt with proposals and report what gets through."""

    def extract_section(self, prompt: str, tag: str) -> str:
        match = re.search("<%s>(.*?)</%s>" % (tag, tag), prompt, re.DOTALL)
        return match.group(1).strip() if match else ""

    def test_case(self, prompt: str, case: Dict) -> Dict:
        """Score one proposal against the prompt's constraints."""
        text = prompt.lower()

        for signal in case["specific"]:
            if signal in text:
                return {"verdict": BLOCKED, "matched": signal, **case}
        for signal in case["generic"]:
            if signal in text:
                return {"verdict": WEAK, "matched": signal, **case}
        return {"verdict": ALLOWED, "matched": None, **case}

    def test_prompt(self, prompt_key: str, prompt: str) -> Dict:
        """Run every proposal for this prompt and summarize."""
        results = [self.test_case(prompt, case) for case in ATTACK_CASES[prompt_key]]

        by_category = {}
        for category in (PHANTOM, OVER_ENG, ARCH):
            subset = [r for r in results if r["category"] == category]
            if subset:
                by_category[category] = {
                    "blocked": sum(1 for r in subset if r["verdict"] == BLOCKED),
                    "weak": sum(1 for r in subset if r["verdict"] == WEAK),
                    "allowed": sum(1 for r in subset if r["verdict"] == ALLOWED),
                    "total": len(subset),
                }

        constraints = self.extract_section(prompt, "constraints")
        return {
            "results": results,
            "by_category": by_category,
            "blocked": sum(1 for r in results if r["verdict"] == BLOCKED),
            "weak": sum(1 for r in results if r["verdict"] == WEAK),
            "allowed": sum(1 for r in results if r["verdict"] == ALLOWED),
            "total": len(results),
            "closed_allowlist": any(p in constraints.lower() for p in CLOSURE_PHRASES),
            "measurable_limits": len(re.findall(r"\b\d+\s*(?:lines|ms|mb|kb|gb|functions|statements|cores)\b",
                                                constraints.lower())),
        }

    def display(self, title: str, report: Dict):
        print(title)
        print("-" * len(title))
        score = report["blocked"] / report["total"] if report["total"] else 0
        print("Prevention score: %d/%d proposals blocked outright (%.0f%%)"
              % (report["blocked"], report["total"], score * 100))
        print("  BLOCKED %d   WEAK %d   ALLOWED %d"
              % (report["blocked"], report["weak"], report["allowed"]))

        print("\nBy pattern:")
        labels = {PHANTOM: "Phantom dependency", OVER_ENG: "Over-engineering",
                  ARCH: "Architecture mismatch"}
        for category, stats in report["by_category"].items():
            print("  %-22s %d/%d blocked, %d weak, %d allowed"
                  % (labels[category], stats["blocked"], stats["total"],
                     stats["weak"], stats["allowed"]))

        print("\nClosed allowlist: %s" % ("yes" if report["closed_allowlist"]
              else "NO - a list of allowed libraries without a closing rule reads as a suggestion"))
        print("Measurable limits: %d numeric bounds found in constraints"
              % report["measurable_limits"])

        leaks = [r for r in report["results"] if r["verdict"] != BLOCKED]
        if leaks:
            print("\nNot fully blocked:")
            for r in leaks:
                if r["verdict"] == WEAK:
                    print("  ~ %s" % r["proposal"])
                    print("      only caught by catch-all: \"%s\"" % r["matched"])
                else:
                    print("  X %s" % r["proposal"])
                    print("      nothing in the prompt prevents this")
        else:
            print("\nAll challenged proposals are blocked by a named constraint.")

        print("\n" + "=" * 80 + "\n")


def load_templates():
    from constraint_templates import (CONSTRAINT_TEMPLATE_1, CONSTRAINT_TEMPLATE_2,
                                      CONSTRAINT_TEMPLATE_3)
    return [("prompt_1", "Template 1: File Processing", CONSTRAINT_TEMPLATE_1),
            ("prompt_2", "Template 2: Discount Logging", CONSTRAINT_TEMPLATE_2),
            ("prompt_3", "Template 3: Notification System", CONSTRAINT_TEMPLATE_3)]


def load_problems():
    from problem_prompts import (PROBLEM_PROMPT_1, PROBLEM_PROMPT_2, PROBLEM_PROMPT_3)
    return [("prompt_1", "Problem 1: File Processing", PROBLEM_PROMPT_1),
            ("prompt_2", "Problem 2: Discount Logging", PROBLEM_PROMPT_2),
            ("prompt_3", "Problem 3: Notification System", PROBLEM_PROMPT_3)]


def load_solution():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                        "solution", "enhanced_prompts.py")
    spec = importlib.util.spec_from_file_location("enhanced_prompts", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return [("prompt_1", "Solution 1: File Processing", module.ENHANCED_SOLUTION_1),
            ("prompt_2", "Solution 2: Discount Logging", module.ENHANCED_SOLUTION_2),
            ("prompt_3", "Solution 3: Notification System", module.ENHANCED_SOLUTION_3)]


def print_three_way(baseline, student, solution):
    """Step 4: problem prompt vs your prompt vs the reference solution."""
    print("=== STEP 4 COMPARISON: BLOCKED / WEAK / ALLOWED ===\n")
    header = "%-10s %-22s %-22s %s" % ("", "problem prompt", "your prompt", "reference solution")
    print(header)
    print("-" * len(header))
    for key in ("prompt_1", "prompt_2", "prompt_3"):
        cells = []
        for report in (baseline[key], student[key], solution[key]):
            cells.append("%d/%d blocked, %d weak"
                         % (report["blocked"], report["total"], report["weak"]))
        print("%-10s %-22s %-22s %s"
              % (key.replace("_", " ").title(), cells[0], cells[1], cells[2]))

    print("\nProposals your prompt blocks that the solution does not:")
    any_found = False
    for key in ("prompt_1", "prompt_2", "prompt_3"):
        smap = {r["proposal"]: r["verdict"] for r in solution[key]["results"]}
        for r in student[key]["results"]:
            if r["verdict"] == BLOCKED and smap.get(r["proposal"]) != BLOCKED:
                print("  + [%s] %s (solution: %s)"
                      % (key, r["proposal"], smap.get(r["proposal"])))
                any_found = True
    if not any_found:
        print("  (none)")

    print("\nProposals the solution blocks that your prompt does not:")
    any_found = False
    for key in ("prompt_1", "prompt_2", "prompt_3"):
        tmap = {r["proposal"]: r["verdict"] for r in student[key]["results"]}
        for r in solution[key]["results"]:
            if r["verdict"] == BLOCKED and tmap.get(r["proposal"]) != BLOCKED:
                print("  - [%s] %s (yours: %s)"
                      % (key, r["proposal"], tmap.get(r["proposal"])))
                any_found = True
    if not any_found:
        print("  (none)")
    print()


def run(prompts, heading):
    tester = ConstraintTester()
    print("=== %s ===\n" % heading)
    reports = {}
    for key, title, prompt in prompts:
        report = tester.test_prompt(key, prompt)
        tester.display(title, report)
        reports[key] = report
    return reports


def print_comparison(baseline, enhanced):
    print("=== CONSTRAINT EFFECTIVENESS: BEFORE vs AFTER ===\n")
    print("%-12s %-22s %-22s %s" % ("", "problem prompt", "your prompt", "improvement"))
    for key in enhanced:
        b, e = baseline[key], enhanced[key]
        print("%-12s %-22s %-22s %+d blocked"
              % (key.replace("_", " ").title(),
                 "%d/%d blocked" % (b["blocked"], b["total"]),
                 "%d/%d blocked" % (e["blocked"], e["total"]),
                 e["blocked"] - b["blocked"]))
    print()


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "templates"

    if mode == "baseline":
        run(load_problems(), "CONSTRAINT EFFECTIVENESS: PROBLEM PROMPTS (BASELINE)")
    elif mode == "solution":
        tester = ConstraintTester()
        solution = run(load_solution(), "CONSTRAINT EFFECTIVENESS: REFERENCE SOLUTION")
        student = {k: tester.test_prompt(k, p) for k, _, p in load_templates()}
        baseline = {k: tester.test_prompt(k, p) for k, _, p in load_problems()}
        print_three_way(baseline, student, solution)
    else:
        enhanced = run(load_templates(), "CONSTRAINT EFFECTIVENESS: YOUR ENHANCED PROMPTS")
        baseline = {k: ConstraintTester().test_prompt(k, p)
                    for k, _, p in load_problems()}
        print_comparison(baseline, enhanced)
