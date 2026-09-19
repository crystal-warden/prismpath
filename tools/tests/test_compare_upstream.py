# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Crystal Warden Supply Chain Labs LLC
"""Tests for the compare upstream maintenance report tool."""

import subprocess
from pathlib import Path

from tools.compare_upstream import compare_upstream, main


def run_git_command(arguments: list[str], working_directory: Path) -> str:
    """Executes a git command in the specified working directory and returns output."""
    process_result = subprocess.run(
        ["git", "-C", str(working_directory)] + arguments,
        capture_output=True,
        text=True,
        check=True,
    )
    return process_result.stdout.strip()


def setup_git_repository(repository_directory: Path) -> None:
    """Initializes a git repository with standard user configuration."""
    repository_directory.mkdir(parents=True, exist_ok=True)
    subprocess.run(["git", "init"], cwd=repository_directory, check=True, capture_output=True)
    run_git_command(["config", "user.name", "Test User"], repository_directory)
    run_git_command(["config", "user.email", "test@example.com"], repository_directory)


def test_compare_upstream_classifications(tmp_path: Path) -> None:
    """Verifies lock entry classifications and upstream additions detection."""
    research_directory = tmp_path / "research_repo"
    product_directory = tmp_path / "product_repo"

    setup_git_repository(research_directory)
    setup_git_repository(product_directory)

    (research_directory / "prismpath").mkdir(parents=True, exist_ok=True)
    (research_directory / "prismpath" / "unchanged.py").write_text("print('unchanged')", encoding="utf-8")
    (research_directory / "prismpath" / "changed.py").write_text("print('original')", encoding="utf-8")
    (research_directory / "prismpath" / "deleted.py").write_text("print('deleted')", encoding="utf-8")
    (research_directory / "prismpath" / "product_edited.py").write_text("print('product_edited')", encoding="utf-8")

    run_git_command(["add", "."], research_directory)
    run_git_command(["commit", "-m", "Initial research commit"], research_directory)
    adopted_revision = run_git_command(["rev-parse", "HEAD"], research_directory)

    unchanged_blob = run_git_command(["rev-parse", f"{adopted_revision}:prismpath/unchanged.py"], research_directory)
    changed_blob = run_git_command(["rev-parse", f"{adopted_revision}:prismpath/changed.py"], research_directory)
    deleted_blob = run_git_command(["rev-parse", f"{adopted_revision}:prismpath/deleted.py"], research_directory)
    product_edited_blob = run_git_command(["rev-parse", f"{adopted_revision}:prismpath/product_edited.py"], research_directory)

    (research_directory / "prismpath" / "changed.py").write_text("print('modified upstream')", encoding="utf-8")
    (research_directory / "prismpath" / "deleted.py").unlink()
    (research_directory / "prismpath" / "addition.py").write_text("print('new addition')", encoding="utf-8")

    run_git_command(["add", "."], research_directory)
    run_git_command(["commit", "-m", "Upstream update commit"], research_directory)
    updated_revision = run_git_command(["rev-parse", "HEAD"], research_directory)

    (product_directory / "tools").mkdir(parents=True, exist_ok=True)
    (product_directory / "prismpath").mkdir(parents=True, exist_ok=True)

    manifest_content = (
        "[meta]\n"
        f"adopted_revision = \"{adopted_revision}\"\n\n"
        "[[rule]]\n"
        "id = \"engine\"\n"
        "kind = \"ship\"\n"
        "purpose = \"engine\"\n"
        "owner = \"research\"\n"
        "prefix = \"prismpath/\"\n"
        "source_prefix = \"prismpath/\"\n"
        "reason = \"the python engine\"\n"
    )
    (product_directory / "tools" / "manifest.toml").write_text(manifest_content, encoding="utf-8")

    lock_content = (
        "path\trule\tsource_path\tsource_blob\n"
        f"prismpath/unchanged.py\tengine\tprismpath/unchanged.py\t{unchanged_blob}\n"
        f"prismpath/changed.py\tengine\tprismpath/changed.py\t{changed_blob}\n"
        f"prismpath/deleted.py\tengine\tprismpath/deleted.py\t{deleted_blob}\n"
        f"prismpath/product_edited.py\tengine\tprismpath/product_edited.py\t{product_edited_blob}\n"
    )
    (product_directory / "tools" / "manifest.lock").write_text(lock_content, encoding="utf-8")

    (product_directory / "prismpath" / "unchanged.py").write_text("print('unchanged')", encoding="utf-8")
    (product_directory / "prismpath" / "changed.py").write_text("print('original')", encoding="utf-8")
    (product_directory / "prismpath" / "deleted.py").write_text("print('deleted')", encoding="utf-8")
    (product_directory / "prismpath" / "product_edited.py").write_text("print('LOCAL MODIFICATION')", encoding="utf-8")

    run_git_command(["add", "."], product_directory)
    run_git_command(["commit", "-m", "Initial product commit"], product_directory)

    comparison_report = compare_upstream(
        research_directory=research_directory,
        revision_identifier=updated_revision,
        product_repository_root=product_directory,
    )

    rules_result = comparison_report["rules"]
    assert "engine" in rules_result

    engine_rule_data = rules_result["engine"]
    entries_map = {entry["path"]: entry for entry in engine_rule_data["entries"]}

    assert entries_map["prismpath/unchanged.py"]["status"] == "unchanged upstream"
    assert not entries_map["prismpath/unchanged.py"]["product_edited"]

    assert entries_map["prismpath/changed.py"]["status"] == "changed upstream"
    assert not entries_map["prismpath/changed.py"]["product_edited"]

    assert entries_map["prismpath/deleted.py"]["status"] == "deleted upstream"
    assert not entries_map["prismpath/deleted.py"]["product_edited"]

    assert entries_map["prismpath/product_edited.py"]["status"] == "unchanged upstream"
    assert entries_map["prismpath/product_edited.py"]["product_edited"]

    assert "prismpath/addition.py" in engine_rule_data["additions"]

    main_return_code = main(
        [
            "--research",
            str(research_directory),
            "--revision",
            updated_revision,
            "--repo",
            str(product_directory),
            "--json",
        ]
    )
    assert main_return_code == 0

    bad_revision_return_code = main(
        [
            "--research",
            str(research_directory),
            "--revision",
            "invalid_commit_hash_12345",
            "--repo",
            str(product_directory),
        ]
    )
    assert bad_revision_return_code == 2

    bad_research_return_code = main(
        [
            "--research",
            str(tmp_path / "nonexistent_repo"),
            "--revision",
            updated_revision,
            "--repo",
            str(product_directory),
        ]
    )
    assert bad_research_return_code == 2
