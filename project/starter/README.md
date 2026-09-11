# Task Manager CLI

A command-line task manager built on the AI-assisted development project starter.
It extends the starter's basic CRUD operations with sorting and filtering, multi-format
export, and undo/redo, and wraps them in a real command-line interface.

This project was built collaboratively with an AI assistant. The collaboration itself is
documented in [`docs/ai_edit_log.md`](docs/ai_edit_log.md) and
[`docs/final_report.md`](docs/final_report.md).

## Features

Beyond the starter's add / get / complete / delete:

1. **Sorting and filtering** (Strategy pattern) - order tasks by priority, creation
   date, or description, and filter by completion status, priority, or keyword. Filters
   combine with AND.
2. **Multi-format export** (Factory pattern) - write tasks to JSON, CSV, or Markdown.
3. **Undo and redo** (Command pattern) - reverse or replay any add, complete, or delete
   within an interactive session.

Supporting work: input validation on descriptions and priorities, JSON persistence that
survives a corrupt or truncated save file, and an interactive shell in addition to
one-shot subcommands.

## Getting Started

### Prerequisites

- Python 3.9 or higher
- pip

### Setup

1. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python main.py
   ```

## Usage

### Interactive shell

Running with no subcommand opens a shell. Undo and redo are available here, because the
command history lives as long as the session does.

```
$ python main.py
Task Manager. Type 'help' for commands, 'quit' to save and exit.
task> add Write the final report high
Added task 1: Write the final report
task> add Buy milk low
Added task 2: Buy milk
task> list
 ID  STATUS  PRIORITY  DESCRIPTION
  1  [ ]     high      Write the final report
  2  [ ]     low       Buy milk
task> delete 1
Deleted task 1
task> undo
Undid: delete task 1
task> list
 ID  STATUS  PRIORITY  DESCRIPTION
  1  [ ]     high      Write the final report
  2  [ ]     low       Buy milk
task> quit
Saved. Goodbye.
```

Shell commands:

| Command | Description |
|---|---|
| `add <description> [priority]` | Add a task. A trailing `low`/`medium`/`high` is read as the priority. |
| `list [sort] [filter=value]` | List tasks. Sorts: `priority`, `created`, `description`. Filters: `status=done\|pending`, `priority=high`, `keyword=<text>`. |
| `complete <id>` | Mark a task complete. |
| `delete <id>` | Delete a task. |
| `undo` / `redo` | Reverse or replay the last change. |
| `export <format> [filename]` | Export to `json`, `csv`, or `markdown`. |
| `help` | Show the command list. |
| `quit` | Save and exit. |

### Subcommands

The same operations are available as one-shot subcommands, for scripting:

```bash
python main.py add "Write the final report" --priority high
python main.py list
python main.py list --status pending --sort description
python main.py list --priority high --keyword report
python main.py complete 1
python main.py delete 2
python main.py export markdown --output report.md
```

Undo and redo are deliberately not exposed as subcommands: each invocation is a separate
process, so there would be no history to undo.

Tasks are saved to `data/tasks.json`. Use `--data-dir` to point at a different location:

```bash
python main.py --data-dir /tmp/scratch list
```

## Architecture

```
main.py                    CLI: interactive shell and subcommands, sharing one
                           handler layer (TaskApp)
utils/task_manager.py      Core data model, validation, and serialization
utils/sorting.py           Strategy pattern: sort and filter strategies
utils/exporters.py         Factory pattern: JSON, CSV, and Markdown exporters
utils/commands.py          Command pattern: undoable operations plus history
utils/file_handler.py      JSON persistence
```

`TaskManager` knows nothing about sorting, exporting, undo, or the command line. Each of
those is a separate module that depends on the model but not on the others, so any one
of them can be tested or replaced on its own.

### Why these patterns

- **Strategy** for sorting and filtering, because the alternative is an if/elif chain in
  the CLI that grows with every new ordering. Each strategy is independently testable,
  and `TaskQuery` composes them at runtime.
- **Factory** for export, because the caller names a format as a string from user input.
  Adding a format is one class plus one registry entry, with no call sites to edit.
- **Command** for undo/redo, because undo needs each operation to know how to reverse
  itself. Putting that knowledge in `TaskManager` would have meant the model tracking its
  own history, which is a separate concern.

## Development

### Testing

```bash
# Run all tests
pytest

# Run with coverage report
pytest --cov=. --cov-report=html

# Run a specific test file with verbose output
pytest tests/test_commands.py -v
```

The suite has 158 tests at 99% coverage, covering happy paths, edge cases, and error
conditions for every module.

| Test file | Covers |
|---|---|
| `test_task_manager.py` | CRUD, validation, undo support, serialization |
| `test_sorting.py` | Sort and filter strategies, query composition |
| `test_exporters.py` | Export factory and all three output formats |
| `test_commands.py` | Command execute/undo, history stack semantics |
| `test_cli.py` | Subcommands, interactive shell, persistence |
| `test_file_handler.py` | JSON file I/O, path traversal protection |

### Code quality

```bash
# Run all quality checks
black . && isort . && flake8 . && mypy . && pytest
```

Configuration lives in `pyproject.toml` and `.flake8`. `mypy` runs with
`disallow_untyped_defs`, so every function needs annotations.

- **Black**: `black .` - formatter, 88-character lines
- **isort**: `isort .` - import organizer
- **flake8**: `flake8 .` - linter
- **mypy**: `mypy .` - static type checker
- **pytest**: `pytest --cov=. --cov-report=html` - tests and coverage

## Project Structure

```
starter/
|-- main.py                 # CLI entry point
|-- utils/
|   |-- task_manager.py     # Core model, validation, serialization
|   |-- sorting.py          # Strategy: sorting and filtering
|   |-- exporters.py        # Factory: JSON, CSV, Markdown export
|   |-- commands.py         # Command: undo/redo
|   `-- file_handler.py     # JSON persistence
|-- tests/                  # 158 unit tests, 99% coverage
|-- docs/
|   |-- ai_edit_log.md      # AI interaction log
|   |-- final_report.md     # Project report
|   |-- project_plan.md     # Plan and scope decisions
|   |-- design_patterns.md  # Pattern reference
|   `-- project_rubric.md   # Assessment criteria
|-- ai_guidance/            # AI prompting and review guidance
|-- pyproject.toml          # black, isort, mypy, pytest, coverage config
|-- .flake8                 # flake8 config
`-- requirements.txt        # Dependencies
```

## Dependencies

Runtime: **click** (CLI framework). Everything else in the standard library.

Development: pytest, pytest-cov, black, isort, flake8, mypy. See `requirements.txt`.

## Project Instructions

This section contains all the student deliverables for this project.

### Learning Objectives
- **AI Collaboration**: Learn to effectively work with AI assistants to generate, review, and refactor code while maintaining code quality
- **Software Engineering**: Apply design patterns, separation of concerns, and modular architecture
- **Test-Driven Development**: Write and maintain comprehensive unit tests with good coverage
- **Code Quality**: Use linting, formatting, and type checking tools for professional-grade code
- **Documentation**: Document AI interactions and development decisions throughout the process

### AI-Assisted Development Workflow

#### 1. Planning Phase
- Use AI to help break down requirements into smaller, manageable tasks
- Ask for architectural suggestions and design pattern recommendations
- Review the `/ai_guidance/prompting_best_practices.md` for effective prompting techniques
- Use the provided slash commands in `/.claude/commands/` for common tasks

#### 2. Implementation Phase
- Generate initial code with AI assistance using specific, contextual prompts
- Always review and understand AI-generated code before accepting it
- Test AI-generated code thoroughly with various inputs and edge cases
- Refactor for clarity, maintainability, and adherence to project standards

#### 3. Review Phase
- Use AI to help identify potential issues or improvements
- Follow the `/ai_guidance/code_review_checklist.md` for systematic code review
- Ask for code review suggestions and alternative implementations
- Validate that the code follows project conventions and security best practices

#### 4. Documentation Phase
- Document your AI interactions in `/docs/ai_edit_log.md` with specific examples
- Explain your decisions and modifications to AI suggestions
- Complete the final report using `/docs/report_template.md`
- Update this README with new features and learnings

### Assessment Criteria

Your project will be evaluated on:

1. **Functionality**: Does the application work as intended with proper error handling?
2. **Code Quality**: Is the code well-structured, readable, and maintainable?
3. **Testing**: Are there comprehensive unit tests with good coverage (>80%)?
4. **AI Collaboration**: Did you effectively use AI assistance while maintaining code quality?
5. **Documentation**: Are your AI interactions and decisions well-documented?

### Example AI Prompts

- "Help me implement a priority queue for tasks using the strategy pattern"
- "Review this code for potential security vulnerabilities"
- "Suggest improvements to make this code more maintainable"
- "Help me write comprehensive unit tests for this function"

### AI Guidance Resources

- `/ai_guidance/prompting_best_practices.md` - Learn effective AI prompting techniques
- `/ai_guidance/code_review_checklist.md` - Systematic approach to reviewing AI-generated code
- `/.claude/commands/generate-function` - Generate well-structured Python functions
- `/.claude/commands/review-code` - Get comprehensive code reviews
- `/.claude/commands/debug-help` - Debug issues with AI assistance
- `/.claude/commands/refactor-code` - Refactor code with design patterns
- `/docs/design_patterns.md` - Examples of implementing design patterns with AI assistance

### Project Structure

```
starter/
├── main.py                 # Main application entry point
├── utils/                  # Utility modules
│   ├── __init__.py
│   ├── task_manager.py     # Task management functionality
│   └── file_handler.py     # File I/O operations
├── tests/                  # Unit test suite
│   ├── __init__.py
│   ├── test_task_manager.py
│   └── test_file_handler.py
├── docs/                   # Documentation and templates
│   ├── ai_edit_log.md      # AI interaction tracking
│   ├── design_patterns.md  # Design pattern examples
│   └── report_template.md  # Final report template
├── ai_guidance/            # AI prompting best practices
│   ├── prompting_best_practices.md
│   └── code_review_checklist.md
├── .claude/                # Claude-specific configuration
│   ├── CLAUDE.md           # Claude configuration
│   ├── commands/           # Slash commands
│   └── mcp.json           # MCP configuration
├── requirements.txt        # Python dependencies
├── .editorconfig          # Code formatting rules
└── README.md              # This file
```

## Built With

* [Python](https://www.python.org/) - Core programming language
* [pytest](https://docs.pytest.org/) - Testing framework for comprehensive unit tests
* [pytest-cov](https://pytest-cov.readthedocs.io/) - Coverage reporting for tests
* [Black](https://black.readthedocs.io/) - Code formatter for consistent style
* [isort](https://pycqa.github.io/isort/) - Import organizer for clean code structure
* [flake8](https://flake8.pycqa.org/) - Linting tool for code quality
* [mypy](https://mypy.readthedocs.io/) - Static type checker for better code reliability
* [pre-commit](https://pre-commit.com/) - Git hook framework for automated quality checks
* [Claude](https://claude.ai/) - AI assistant for code generation and review

## License

[License](LICENSE.txt)

---

**Remember**: The goal is not just to build a working application, but to learn how to effectively collaborate with AI while maintaining high software engineering standards. Take time to understand the code, ask questions, and document your learning journey!
