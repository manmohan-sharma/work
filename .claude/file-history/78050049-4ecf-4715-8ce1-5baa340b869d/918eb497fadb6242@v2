"""
Validates that cli_interface_v2 is a genuine improvement over cli_interface_v1
*without* changing observable behavior.

Two kinds of check live here:

  TestBehaviorPreserved - the safety net. v2 must produce byte-identical
      output to v1 for every input, including edge cases test_cli_interface.py
      does not cover. If these fail, the refactoring broke something.

  TestQualityImproved   - the point of the exercise. Objective, measurable
      quality gains. If these fail, the refactoring was cosmetic.
"""
import ast
import contextlib
import inspect
import io
from pathlib import Path

import pytest

import cli_interface_v1
import cli_interface_v2

V1_PATH = Path(__file__).parent / "cli_interface_v1.py"
V2_PATH = Path(__file__).parent / "cli_interface_v2.py"

# Inputs spanning both methods, including cases the original suite skips:
# empty data, absent 'mode' key, unrecognized mode, over-long label, empty message.
REPORT_CASES = [
    {'mode': 'summary', 'data': {'Food': 150.50, 'Transport': 200.00}, 'total': 350.50},
    {'mode': 'monthly', 'data': {'2024-01': 500.00, '2024-02': 450.00}, 'total': 950.00},
    {'mode': 'summary', 'data': {}, 'total': 0.0},
    {'mode': 'bogus', 'data': {}, 'total': 0.0},
    {},
    {'mode': 'summary', 'data': {'VeryLongCategoryNameIndeed': 1234567.891},
     'total': 1234567.891},
]

ERROR_CASES = [
    FileNotFoundError("File 'expenses.csv' not found"),
    ValueError("Invalid amount format"),
    Exception("Something went wrong"),
    ValueError("value out of range"),
    Exception("profile not found"),   # 'file' matches inside "profile"
    Exception(""),
    # Ambiguous: matches BOTH keyword sets, so the heading depends entirely on
    # which category is tested first. These are the cases that pin the ordering.
    ValueError("Invalid value in file 'expenses.csv'"),
    Exception("File contains an invalid value"),
]


def render(module, method_name, argument):
    """Capture everything `module.CLIInterface().<method>(argument)` prints."""
    buffer = io.StringIO()
    cli = module.CLIInterface()
    with contextlib.redirect_stdout(buffer):
        getattr(cli, method_name)(argument)
    return buffer.getvalue()


def methods_of(module):
    """Return the CLIInterface methods defined in `module`, by name."""
    return {
        name: func
        for name, func in inspect.getmembers(module.CLIInterface, inspect.isfunction)
        if not name.startswith('__')
    }


def parse_class(path):
    """Return the ast.ClassDef for CLIInterface in the file at `path`."""
    tree = ast.parse(path.read_text())
    return next(node for node in ast.walk(tree) if isinstance(node, ast.ClassDef))


def method_nodes(path):
    """Return the ast.FunctionDef nodes for CLIInterface methods in `path`."""
    return [node for node in parse_class(path).body
            if isinstance(node, ast.FunctionDef)]


def complexity(node):
    """Approximate cyclomatic complexity: 1 + number of decision points."""
    decision_points = (ast.If, ast.For, ast.While, ast.BoolOp,
                       ast.ExceptHandler, ast.comprehension, ast.IfExp)
    return 1 + sum(isinstance(child, decision_points) for child in ast.walk(node))


class TestBehaviorPreserved:
    """v2 must be indistinguishable from v1 at the output boundary."""

    @pytest.mark.parametrize("report_data", REPORT_CASES,
                             ids=lambda case: str(case.get('mode', 'no-mode')))
    def test_report_output_identical_to_v1(self, report_data):
        """Every report renders byte-for-byte the same as v1."""
        assert (render(cli_interface_v2, 'display_report', report_data)
                == render(cli_interface_v1, 'display_report', report_data))

    @pytest.mark.parametrize("error", ERROR_CASES,
                             ids=lambda err: type(err).__name__ + ':' + str(err)[:20])
    def test_error_output_identical_to_v1(self, error):
        """Every error renders byte-for-byte the same as v1.

        Covers the ordering trap: 'value out of range' and 'profile not found'
        both match more than one keyword set, so a reordered category table
        would change their headings.
        """
        assert (render(cli_interface_v2, 'display_error', error)
                == render(cli_interface_v1, 'display_error', error))

    def test_public_api_unchanged(self):
        """v2 exposes the same public methods with the same signatures."""
        v1_public = {n for n in methods_of(cli_interface_v1) if not n.startswith('_')}
        v2_public = {n for n in methods_of(cli_interface_v2) if not n.startswith('_')}
        assert v2_public == v1_public

        for name in v1_public:
            v1_params = list(inspect.signature(
                methods_of(cli_interface_v1)[name]).parameters)
            v2_params = list(inspect.signature(
                methods_of(cli_interface_v2)[name]).parameters)
            assert v1_params == v2_params, f"{name}() parameters changed"


class TestQualityImproved:
    """Objective, measurable gains over v1."""

    def test_no_magic_numbers_in_method_bodies(self):
        """All numeric literals live in named constants, not buried in logic."""
        def numeric_literals(path):
            return [node.value for method in method_nodes(path)
                    for node in ast.walk(method)
                    if isinstance(node, ast.Constant)
                    and isinstance(node.value, (int, float))
                    and not isinstance(node.value, bool)]

        assert numeric_literals(V2_PATH) == [], (
            "v2 still has magic numbers in method bodies: "
            f"{numeric_literals(V2_PATH)}"
        )
        assert len(numeric_literals(V1_PATH)) > 0, "v1 baseline assumption broken"

    def test_constants_are_defined_on_the_class(self):
        """The values v1 hardcoded are now overridable class attributes."""
        expected = {
            'LINE_WIDTH', 'HEAVY_RULE', 'LIGHT_RULE', 'ERROR_RULE', 'INDENT',
            'LABEL_WIDTH', 'AMOUNT_WIDTH', 'AMOUNT_PRECISION',
            'CURRENCY_SYMBOL', 'TOTAL_LABEL',
        }
        missing = expected - set(vars(cli_interface_v2.CLIInterface))
        assert not missing, f"missing constants: {sorted(missing)}"

    def test_constants_actually_drive_the_output(self):
        """Overriding a constant changes the rendering - proving it is not decorative."""
        class NarrowCLI(cli_interface_v2.CLIInterface):
            LINE_WIDTH = 20

        output = render(type("M", (), {'CLIInterface': NarrowCLI}),
                        'display_report', REPORT_CASES[0])
        assert '=' * 20 in output
        assert '=' * 50 not in output

    def test_type_hint_coverage_is_complete(self):
        """Every parameter and every return value is annotated."""
        unannotated = []
        for name, func in methods_of(cli_interface_v2).items():
            signature = inspect.signature(func)
            for param_name, param in signature.parameters.items():
                if param_name != 'self' and param.annotation is inspect.Parameter.empty:
                    unannotated.append(f"{name}({param_name})")
            if signature.return_annotation is inspect.Signature.empty:
                unannotated.append(f"{name}() -> ?")

        assert unannotated == [], f"unannotated: {unannotated}"

    def test_methods_are_focused(self):
        """No method exceeds 20 lines; v1's longest was 33."""
        too_long = {node.name: node.end_lineno - node.lineno + 1
                    for node in method_nodes(V2_PATH)
                    if node.end_lineno - node.lineno + 1 > 20}
        assert too_long == {}, f"methods too long: {too_long}"

    def test_per_method_complexity_reduced(self):
        """Peak per-method complexity is below v1's."""
        v1_peak = max(complexity(node) for node in method_nodes(V1_PATH))
        v2_peak = max(complexity(node) for node in method_nodes(V2_PATH))
        assert v2_peak < v1_peak, f"v1 peak={v1_peak}, v2 peak={v2_peak}"

    def test_duplication_reduced(self):
        """Far fewer repeated source lines than v1."""
        def repeated_lines(path):
            lines = [line.strip() for line in path.read_text().splitlines()
                     if line.strip()]
            return {line for line in lines if lines.count(line) > 1}

        v1_repeats = len(repeated_lines(V1_PATH))
        v2_repeats = len(repeated_lines(V2_PATH))
        assert v2_repeats < v1_repeats / 2, (
            f"duplication not meaningfully reduced: v1={v1_repeats}, v2={v2_repeats}"
        )

    def test_report_modes_are_data_not_branches(self):
        """Adding a report mode is a table entry, not another if/elif arm."""
        titles = cli_interface_v2.CLIInterface.REPORT_TITLES
        assert set(titles) == {'summary', 'monthly'}

        display_report = next(node for node in method_nodes(V2_PATH)
                              if node.name == 'display_report')
        branches = sum(isinstance(node, ast.If) for node in ast.walk(display_report))
        assert branches <= 1, f"display_report still branches per mode ({branches} ifs)"

    def test_every_method_has_a_docstring(self):
        """Including the extracted private helpers."""
        undocumented = [node.name for node in method_nodes(V2_PATH)
                        if ast.get_docstring(node) is None]
        assert undocumented == [], f"missing docstrings: {undocumented}"
