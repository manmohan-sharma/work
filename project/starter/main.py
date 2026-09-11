"""
Command-line interface for the task manager.

Running ``python main.py`` with no arguments opens an interactive shell, which
is where undo and redo are meaningful: the command history lives for as long
as the session does. Individual subcommands are also available for scripting.
Both routes share the handler methods on :class:`TaskApp`, so there is one
implementation of each operation rather than two.
"""

import shlex
from typing import Any, Callable, Dict, List, Optional

import click

from utils.commands import (
    AddTaskCommand,
    CommandHistory,
    CompleteTaskCommand,
    DeleteTaskCommand,
)
from utils.exporters import EXPORT_CHOICES, ExporterFactory
from utils.file_handler import FileHandler
from utils.sorting import (
    SORT_CHOICES,
    KeywordFilter,
    PriorityFilter,
    StatusFilter,
    TaskQuery,
    get_sort_strategy,
)
from utils.task_manager import VALID_PRIORITIES, TaskManager

SAVE_FILE = "tasks.json"


class TaskApp:
    """Holds the session state shared by the shell and the subcommands."""

    def __init__(self, data_dir: str = "data") -> None:
        self.file_handler = FileHandler(data_dir)
        self.manager = TaskManager.from_dict(self.file_handler.load_data(SAVE_FILE))
        self.history = CommandHistory()

    def save(self) -> None:
        """Persist the current tasks to disk."""
        self.file_handler.save_data(SAVE_FILE, self.manager.to_dict())

    def add(self, description: str, priority: str) -> str:
        """Add a task and return a confirmation message."""
        command = AddTaskCommand(self.manager, description, priority)
        self.history.execute(command)
        return f"Added task {command.task_id}: {description}"

    def complete(self, task_id: int) -> str:
        """Mark a task complete and return a confirmation message."""
        self.history.execute(CompleteTaskCommand(self.manager, task_id))
        return f"Completed task {task_id}"

    def delete(self, task_id: int) -> str:
        """Delete a task and return a confirmation message."""
        self.history.execute(DeleteTaskCommand(self.manager, task_id))
        return f"Deleted task {task_id}"

    def undo(self) -> str:
        """Undo the last command and return a confirmation message."""
        return f"Undid: {self.history.undo()}"

    def redo(self) -> str:
        """Redo the last undone command and return a confirmation message."""
        return f"Redid: {self.history.redo()}"

    def listing(
        self,
        sort: str = "priority",
        status: Optional[str] = None,
        priority: Optional[str] = None,
        keyword: Optional[str] = None,
    ) -> str:
        """Return a rendered table of tasks matching the given filters."""
        query = TaskQuery(get_sort_strategy(sort))
        if status == "done":
            query.add_filter(StatusFilter(True))
        elif status == "pending":
            query.add_filter(StatusFilter(False))
        if priority:
            query.add_filter(PriorityFilter(priority))
        if keyword:
            query.add_filter(KeywordFilter(keyword))

        return render_tasks(query.apply(self.manager.get_all_tasks()))

    def export(self, format_name: str, output: Optional[str] = None) -> str:
        """Export all tasks and return a confirmation message."""
        exporter = ExporterFactory.create(format_name)
        filename = output or f"tasks.{exporter.extension}"
        filepath = self.file_handler.resolve_path(filename)
        exporter.export(self.manager.get_all_tasks(), filepath)
        return f"Exported {len(self.manager.get_all_tasks())} task(s) to {filepath}"


def render_tasks(tasks: List[Dict[str, Any]]) -> str:
    """Render tasks as an aligned table, or a friendly note when empty."""
    if not tasks:
        return "No tasks match."

    lines = [f"{'ID':>3}  {'STATUS':<8}{'PRIORITY':<10}DESCRIPTION"]
    for task in tasks:
        marker = "[done]" if task.get("completed") else "[ ]"
        lines.append(
            f"{task.get('id', '?'):>3}  {marker:<8}"
            f"{str(task.get('priority', '')):<10}{task.get('description', '')}"
        )
    return "\n".join(lines)


SHELL_HELP = """Commands:
  add <description> [priority]   Add a task (priority: low|medium|high)
  list [sort] [filter=value]     List tasks; sort: priority|created|description
                                 filters: status=done|pending, priority=high,
                                 keyword=<text>
  complete <id>                  Mark a task complete
  delete <id>                    Delete a task
  undo / redo                    Reverse or replay the last change
  export <format> [filename]     Export tasks (json|csv|markdown)
  help                           Show this message
  quit                           Save and exit"""


def _dispatch(app: TaskApp, parts: List[str]) -> str:
    """Route one parsed shell command to a TaskApp handler.

    Raises:
        ValueError: If the command is unknown or its arguments are invalid.
        IndexError: If undo or redo has nothing left to do.
    """
    verb, args = parts[0].lower(), parts[1:]

    if verb == "help":
        return SHELL_HELP
    if verb == "add":
        if not args:
            raise ValueError("Usage: add <description> [priority]")
        # A trailing recognised priority is treated as the priority; anything
        # else is part of the description, so "add buy milk" still works.
        if len(args) > 1 and args[-1].lower() in VALID_PRIORITIES:
            return app.add(" ".join(args[:-1]), args[-1])
        return app.add(" ".join(args), "medium")
    if verb == "list":
        sort = "priority"
        filters: Dict[str, str] = {}
        for arg in args:
            if "=" in arg:
                key, _, value = arg.partition("=")
                filters[key.strip().lower()] = value.strip()
            else:
                sort = arg
        return app.listing(
            sort=sort,
            status=filters.get("status"),
            priority=filters.get("priority"),
            keyword=filters.get("keyword"),
        )
    if verb in {"complete", "delete"}:
        if not args:
            raise ValueError(f"Usage: {verb} <id>")
        try:
            task_id = int(args[0])
        except ValueError:
            raise ValueError(f"Task ID must be a number, got '{args[0]}'")
        return app.complete(task_id) if verb == "complete" else app.delete(task_id)
    if verb == "undo":
        return app.undo()
    if verb == "redo":
        return app.redo()
    if verb == "export":
        if not args:
            raise ValueError(f"Usage: export <{'|'.join(EXPORT_CHOICES)}> [filename]")
        return app.export(args[0], args[1] if len(args) > 1 else None)

    raise ValueError(f"Unknown command '{verb}'. Type 'help' for the command list.")


def run_shell(app: TaskApp) -> None:
    """Run the interactive loop until the user quits or input runs out."""
    click.echo("Task Manager. Type 'help' for commands, 'quit' to save and exit.")
    while True:
        try:
            raw = click.prompt(
                "task>", prompt_suffix=" ", default="", show_default=False
            )
        except (EOFError, click.Abort):
            break

        try:
            parts = shlex.split(raw)
        except ValueError as error:
            click.echo(f"Error: could not parse input ({error})", err=True)
            continue

        if not parts:
            continue
        if parts[0].lower() in {"quit", "exit"}:
            break

        try:
            click.echo(_dispatch(app, parts))
            app.save()
        except (ValueError, IndexError, RuntimeError) as error:
            click.echo(f"Error: {error}", err=True)

    app.save()
    click.echo("Saved. Goodbye.")


@click.group(invoke_without_command=True)
@click.option("--data-dir", default="data", help="Directory for saved tasks.")
@click.pass_context
def cli(ctx: click.Context, data_dir: str) -> None:
    """Manage tasks from the command line.

    Run without a subcommand to open the interactive shell.
    """
    ctx.obj = TaskApp(data_dir)
    if ctx.invoked_subcommand is None:
        run_shell(ctx.obj)


@cli.command()
@click.argument("description")
@click.option(
    "--priority",
    default="medium",
    type=click.Choice(VALID_PRIORITIES),
    help="Task priority.",
)
@click.pass_obj
def add(app: TaskApp, description: str, priority: str) -> None:
    """Add a new task."""
    _run(app, lambda: app.add(description, priority))


@cli.command(name="list")
@click.option("--sort", default="priority", type=click.Choice(SORT_CHOICES))
@click.option("--status", type=click.Choice(["done", "pending"]))
@click.option("--priority", type=click.Choice(VALID_PRIORITIES))
@click.option("--keyword", help="Only show tasks whose description contains this.")
@click.pass_obj
def list_tasks(
    app: TaskApp,
    sort: str,
    status: Optional[str],
    priority: Optional[str],
    keyword: Optional[str],
) -> None:
    """List tasks, optionally filtered and sorted."""
    _run(app, lambda: app.listing(sort, status, priority, keyword), save=False)


@cli.command()
@click.argument("task_id", type=int)
@click.pass_obj
def complete(app: TaskApp, task_id: int) -> None:
    """Mark a task as complete."""
    _run(app, lambda: app.complete(task_id))


@cli.command()
@click.argument("task_id", type=int)
@click.pass_obj
def delete(app: TaskApp, task_id: int) -> None:
    """Delete a task."""
    _run(app, lambda: app.delete(task_id))


@cli.command()
@click.argument("format_name", type=click.Choice(EXPORT_CHOICES))
@click.option("--output", help="Output filename inside the data directory.")
@click.pass_obj
def export(app: TaskApp, format_name: str, output: Optional[str]) -> None:
    """Export tasks to a file."""
    _run(app, lambda: app.export(format_name, output), save=False)


def _run(app: TaskApp, action: Callable[[], str], save: bool = True) -> None:
    """Run a handler, print its message, and report errors as CLI failures."""
    try:
        message = action()
    except (ValueError, IndexError, RuntimeError) as error:
        raise click.ClickException(str(error))
    click.echo(message)
    if save:
        app.save()


if __name__ == "__main__":
    cli()
