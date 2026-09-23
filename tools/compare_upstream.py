# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Crystal Warden Supply Chain Labs LLC
"""What changed in research since the product adopted it, per inventory rule; a report, never a build step.

For every locked product path with a research source, the source blob at --revision is compared with
the adopted blob in the lock, and the product copy with the adopted blob, so each path reads as
unchanged, changed or deleted upstream, and edited or not in the product. Research paths under a
shipped source prefix that no lock entry traces to are listed as upstream additions. Research is
read through git plumbing on a local clone only; nothing is written anywhere.

    python -m tools.compare_upstream --research <path to a local research git clone> --revision <commit or ref> [--rule <rule id>] [--json]
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from tools.product_inventory import REPO_ROOT, load_lock, load_rules


def validate_research_repository(research_directory: Path, revision_identifier: str) -> bool:
    """Verifies that the research directory exists and the revision resolves."""
    if not research_directory.is_dir():
        return False
    process_result = subprocess.run(
        ["git", "-C", str(research_directory), "rev-parse", "--verify", "--quiet", revision_identifier],
        capture_output=True,
        text=True,
    )
    return process_result.returncode == 0


def compute_product_blob(product_repository_root: Path, product_path_string: str) -> str | None:
    """Computes the git blob identifier of a product file using git hash-object."""
    product_file_path = product_repository_root / product_path_string
    if not product_file_path.is_file():
        return None
    process_result = subprocess.run(
        ["git", "-C", str(product_repository_root), "hash-object", str(product_file_path)],
        capture_output=True,
        text=True,
    )
    if process_result.returncode != 0:
        return None
    return process_result.stdout.strip()


def query_research_blob(research_directory: Path, revision_identifier: str, source_path_string: str) -> str | None:
    """Queries the research repository for the blob identifier of source path at revision."""
    process_result = subprocess.run(
        [
            "git",
            "-C",
            str(research_directory),
            "rev-parse",
            "--verify",
            "--quiet",
            f"{revision_identifier}:{source_path_string}",
        ],
        capture_output=True,
        text=True,
    )
    if process_result.returncode != 0:
        return None
    return process_result.stdout.strip()


def query_research_additions(
    research_directory: Path,
    revision_identifier: str,
    source_prefix_string: str,
    all_lock_source_paths: set[str],
) -> list[str]:
    """Lists research paths under source prefix at revision that are absent from the lock."""
    process_result = subprocess.run(
        [
            "git",
            "-C",
            str(research_directory),
            "ls-tree",
            "-r",
            "--name-only",
            revision_identifier,
            "--",
            source_prefix_string,
        ],
        capture_output=True,
        text=True,
    )
    if process_result.returncode != 0:
        return []
    path_lines = [line.strip() for line in process_result.stdout.splitlines() if line.strip()]
    return sorted(path for path in path_lines if path not in all_lock_source_paths)


def compare_upstream(
    research_directory: Path,
    revision_identifier: str,
    product_repository_root: Path = REPO_ROOT,
    rule_identifier: str | None = None,
) -> dict[str, Any]:
    """Compares the product manifest lock entries and rules against the research repository."""
    manifest_path = product_repository_root / "tools" / "inventory.toml"
    lock_path = product_repository_root / "tools" / "inventory.lock"

    rules_list = load_rules(manifest_path)
    lock_entries = load_lock(lock_path)

    if rule_identifier is not None:
        matching_rules = [rule for rule in rules_list if rule.identifier == rule_identifier]
        if not matching_rules:
            raise ValueError(f"Rule identifier not found in manifest: {rule_identifier}")

    all_lock_source_paths = {
        entry["source_path"] for entry in lock_entries.values() if entry.get("source_path")
    }

    rule_results: dict[str, Any] = {}

    for rule_object in rules_list:
        if rule_identifier is not None and rule_object.identifier != rule_identifier:
            continue

        rule_id = rule_object.identifier
        entries_for_rule: list[dict[str, Any]] = []

        unchanged_count = 0
        changed_count = 0
        deleted_count = 0
        product_edited_count = 0

        for product_path, entry_dictionary in lock_entries.items():
            if entry_dictionary.get("rule") != rule_id:
                continue
            source_path = entry_dictionary.get("source_path", "")
            if not source_path:
                continue

            adopted_blob = entry_dictionary.get("source_blob", "")
            revision_blob = query_research_blob(research_directory, revision_identifier, source_path)
            product_blob = compute_product_blob(product_repository_root, product_path)

            product_edited = product_blob != adopted_blob
            if product_edited:
                product_edited_count += 1

            if revision_blob is None:
                status_label = "deleted upstream"
                deleted_count += 1
            elif revision_blob == adopted_blob:
                status_label = "unchanged upstream"
                unchanged_count += 1
            else:
                status_label = "changed upstream"
                changed_count += 1

            entries_for_rule.append(
                {
                    "path": product_path,
                    "source_path": source_path,
                    "source_blob": adopted_blob,
                    "revision_blob": revision_blob,
                    "status": status_label,
                    "product_edited": product_edited,
                }
            )

        addition_paths: list[str] = []
        if rule_object.kind == "ship" and rule_object.source_prefix:
            addition_paths = query_research_additions(
                research_directory,
                revision_identifier,
                rule_object.source_prefix,
                all_lock_source_paths,
            )

        rule_results[rule_id] = {
            "kind": rule_object.kind,
            "counts": {
                "total_lock_entries": len(entries_for_rule),
                "unchanged_upstream": unchanged_count,
                "changed_upstream": changed_count,
                "deleted_upstream": deleted_count,
                "product_edited": product_edited_count,
                "additions": len(addition_paths),
            },
            "entries": entries_for_rule,
            "additions": addition_paths,
        }

    return {"rules": rule_results}


def format_human_readable_report(report_dictionary: dict[str, Any]) -> str:
    """Formats the comparison dictionary into a human readable text report."""
    output_lines: list[str] = []
    rules_dictionary = report_dictionary.get("rules", {})

    for rule_id, rule_data in rules_dictionary.items():
        kind = rule_data["kind"]
        counts = rule_data["counts"]
        # A rule with nothing traced and nothing added has nothing to report; hold rules are such
        # rules by construction, and listing them would bury the changes among empty headings.
        if counts["total_lock_entries"] == 0 and counts["additions"] == 0:
            continue
        output_lines.append(f"Rule: {rule_id} ({kind})")
        output_lines.append(
            f"  Counts: {counts['total_lock_entries']} locked entries "
            f"({counts['unchanged_upstream']} unchanged upstream, "
            f"{counts['changed_upstream']} changed upstream, "
            f"{counts['deleted_upstream']} deleted upstream, "
            f"{counts['product_edited']} product edited), "
            f"{counts['additions']} upstream additions"
        )

        changed_or_deleted_entries = [
            entry for entry in rule_data["entries"] if entry["status"] != "unchanged upstream"
        ]
        if changed_or_deleted_entries:
            output_lines.append("  Changed/Deleted entries:")
            for entry in changed_or_deleted_entries:
                output_lines.append(
                    f"    [{entry['status']}] {entry['path']} "
                    f"(source: {entry['source_path']}, product edited: {entry['product_edited']})"
                )

        additions = rule_data["additions"]
        if additions:
            output_lines.append("  Upstream additions:")
            for addition_path in additions:
                output_lines.append(f"    + {addition_path}")

        output_lines.append("")

    return "\n".join(output_lines).rstrip()


def main(argument_list: list[str] | None = None) -> int:
    """Runs the main report generation workflow and returns exit code 0 or 2."""
    argument_parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    argument_parser.add_argument(
        "--research",
        required=True,
        help="path to a local research git clone",
    )
    argument_parser.add_argument(
        "--revision",
        required=True,
        help="commit or ref in the research git clone",
    )
    argument_parser.add_argument(
        "--rule",
        default=None,
        help="optional rule identifier to filter the report",
    )
    argument_parser.add_argument(
        "--json",
        action="store_true",
        help="output report as a JSON object",
    )
    argument_parser.add_argument(
        "--repo",
        default=str(REPO_ROOT),
        help="path to the product repository root",
    )

    parsed_arguments = argument_parser.parse_args(argument_list)

    research_directory = Path(parsed_arguments.research).resolve()
    product_directory = Path(parsed_arguments.repo).resolve()
    revision_identifier = parsed_arguments.revision

    if not validate_research_repository(research_directory, revision_identifier):
        sys.stderr.write("Error: --research is not a git repository or --revision does not resolve.\n")
        return 2

    try:
        comparison_report = compare_upstream(
            research_directory=research_directory,
            revision_identifier=revision_identifier,
            product_repository_root=product_directory,
            rule_identifier=parsed_arguments.rule,
        )
    except Exception as error:
        sys.stderr.write(f"Error: {error}\n")
        return 2

    if parsed_arguments.json:
        print(json.dumps(comparison_report, indent=2))
    else:
        print(format_human_readable_report(comparison_report))

    return 0


if __name__ == "__main__":
    sys.exit(main())
