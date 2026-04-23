from __future__ import annotations

import json
from pathlib import Path

import typer
from dotenv import load_dotenv
from rich import print
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
)

from src.reflexion_lab.agents import ReActAgent, ReflexionAgent
from src.reflexion_lab.reporting import build_report, save_report
from src.reflexion_lab.utils import load_dataset, save_jsonl

app = typer.Typer(add_completion=False)


@app.command()
def main(
    dataset: str = "hotpot_mini.json",
    out_dir: str = "outputs/real_run",
    reflexion_attempts: int = 3,
) -> None:
    load_dotenv()

    examples = load_dataset(dataset)
    react = ReActAgent()
    reflexion = ReflexionAgent(max_attempts=reflexion_attempts)

    react_records = []
    reflexion_records = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
    ) as progress:
        # --- ReAct ---
        task_react = progress.add_task("[cyan]ReAct Agent", total=len(examples))
        for example in examples:
            try:
                record = react.run(example)
                react_records.append(record)
            except Exception as e:
                print(f"[red]ReAct error on {example.qid}: {e}[/red]")
            progress.advance(task_react)

        # --- Reflexion ---
        task_ref = progress.add_task("[magenta]Reflexion Agent", total=len(examples))
        for example in examples:
            try:
                record = reflexion.run(example)
                reflexion_records.append(record)
            except Exception as e:
                print(f"[red]Reflexion error on {example.qid}: {e}[/red]")
            progress.advance(task_ref)

    all_records = react_records + reflexion_records
    out_path = Path(out_dir)

    save_jsonl(out_path / "react_runs.jsonl", react_records)
    save_jsonl(out_path / "reflexion_runs.jsonl", reflexion_records)

    report = build_report(all_records, dataset_name=Path(dataset).name, mode="real")
    json_path, md_path = save_report(report, out_path)

    print(f"\n[green]✅ Saved[/green] {json_path}")
    print(f"[green]✅ Saved[/green] {md_path}")
    print(f"[green]✅ Total records:[/green] {len(all_records)}")
    print(json.dumps(report.summary, indent=2))


if __name__ == "__main__":
    app()
