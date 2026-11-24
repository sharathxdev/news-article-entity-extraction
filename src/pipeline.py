"""Run the news article cleaning, analysis and evaluation pipeline."""

import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def run_command(arguments):
    """Run a command from the project root and stop if it fails."""
    subprocess.run(
        arguments,
        cwd=PROJECT_ROOT,
        check=True,
    )


def run_module(module, *arguments):
    """Run a Python module using the current project interpreter."""
    command = [
        sys.executable,
        "-m",
        module,
        *arguments,
    ]

    print(f"\n===== RUNNING {module} =====", flush=True)
    run_command(command)


def main():
    parser = argparse.ArgumentParser(
        description="Run the news article entity extraction project."
    )

    parser.add_argument(
        "--load-neo4j",
        action="store_true",
        help="Load the graph into Neo4j and execute its query.",
    )

    parser.add_argument(
        "--person",
        default="Maria Gomez",
        help="Person used for the organization lookup.",
    )

    args = parser.parse_args()

    print("===== NEWS ARTICLE ENTITY EXTRACTION PIPELINE =====")

    run_module("src.data_cleaning")
    run_module("src.weekly_analysis")
    run_module("src.entity_evaluation")
    run_module("src.graph.graph_builder")

    print("\n===== RUNNING PROJECT TESTS =====", flush=True)

    run_command([
        sys.executable,
        "-m",
        "pytest",
        "-q",
    ])

    if args.load_neo4j:
        run_module(
            "src.graph.neo4j_loader",
            "--person",
            args.person,
        )
    else:
        print(
            "\nNeo4j loading skipped. "
            "Use --load-neo4j to load and query the database."
        )

    print("\n===== PIPELINE COMPLETED =====")


if __name__ == "__main__":
    main()
