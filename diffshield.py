#!/usr/bin/env python3
"""
diffshield - Zero-overhead semantic diff firewall for AI coding agents.
Inspects git diffs via AST to catch silent code deletions, stripped error handlers,
and dropped test assertions.
"""

import ast
import json
import os
import subprocess
import sys
from typing import Dict, List, Set

# ponytail: stdlib-only python AST parser first. Add tree-sitter/oxc when multi-language support is requested.

class ASTInspector:
    @staticmethod
    def extract_entities(source: str) -> Dict[str, any]:
        """Extract functions, classes, try/except blocks, and test assertions from source."""
        data = {
            "functions": set(),
            "classes": set(),
            "try_blocks": 0,
            "assertions": 0,
            "guard_clauses": 0
        }
        if not source.strip():
            return data
            
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return data

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                data["functions"].add(node.name)
            elif isinstance(node, ast.ClassDef):
                data["classes"].add(node.name)
            elif isinstance(node, ast.Try):
                data["try_blocks"] += 1
            elif isinstance(node, ast.Assert):
                data["assertions"] += 1
            elif isinstance(node, ast.If):
                # Detect guard clauses: if <cond>: raise / return
                for stmt in node.body:
                    if isinstance(stmt, (ast.Raise, ast.Return)):
                        data["guard_clauses"] += 1
                        break
        return data

def compare_entities(old_meta: Dict[str, any], new_meta: Dict[str, any], path: str = "") -> List[str]:
    """Compare entity sets and counters to identify semantic deletions."""
    violations = []
    prefix = f"{path}: " if path else ""

    # 1. Dropped functions
    dropped_funcs = old_meta["functions"] - new_meta["functions"]
    if dropped_funcs:
        violations.append(f"[DROP_FUNC] {prefix}deleted functions -> {', '.join(sorted(dropped_funcs))}")

    # 2. Dropped classes
    dropped_classes = old_meta["classes"] - new_meta["classes"]
    if dropped_classes:
        violations.append(f"[DROP_CLASS] {prefix}deleted classes -> {', '.join(sorted(dropped_classes))}")

    # 3. Stripped error handling (try/catch blocks)
    if old_meta["try_blocks"] > new_meta["try_blocks"]:
        diff_cnt = old_meta["try_blocks"] - new_meta["try_blocks"]
        violations.append(f"[STRIP_ERROR_HANDLER] {prefix}stripped {diff_cnt} try/except block(s)")

    # 4. Stripped test assertions
    is_test = ("test" in path.lower()) if path else True
    if is_test and old_meta["assertions"] > new_meta["assertions"]:
        diff_cnt = old_meta["assertions"] - new_meta["assertions"]
        violations.append(f"[STRIP_ASSERTION] {prefix}dropped {diff_cnt} test assertion(s)")

    # 5. Stripped guard clauses (if cond: return/raise)
    if old_meta["guard_clauses"] > new_meta["guard_clauses"]:
        diff_cnt = old_meta["guard_clauses"] - new_meta["guard_clauses"]
        violations.append(f"[STRIP_GUARD] {prefix}removed {diff_cnt} guard clause(s)")

    return violations

def get_git_file_content(commit_ref: str, path: str) -> str:
    """Get file content from git at a given ref (e.g. HEAD)."""
    try:
        out = subprocess.check_output(["git", "show", f"{commit_ref}:{path}"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError:
        return ""

def get_changed_files(base_ref: str = "HEAD") -> List[str]:
    """Get list of modified and unstaged/staged files against base_ref."""
    try:
        out = subprocess.check_output(["git", "diff", "--name-only", base_ref], stderr=subprocess.DEVNULL)
        files = [f.strip() for f in out.decode().splitlines() if f.strip().endswith(".py")]
        return sorted(list(set(files)))
    except subprocess.CalledProcessError:
        return []

def audit_diff(base_ref: str = "HEAD") -> List[str]:
    """Audit diff against base_ref for dangerous semantic deletions."""
    files = get_changed_files(base_ref=base_ref)
    violations = []

    for path in files:
        if not os.path.isfile(path):
            continue
        old_src = get_git_file_content(base_ref, path)
        if not old_src:
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                new_src = f.read()
        except OSError:
            continue

        old_meta = ASTInspector.extract_entities(old_src)
        new_meta = ASTInspector.extract_entities(new_src)
        violations.extend(compare_entities(old_meta, new_meta, path=path))

    return violations

def main():
    if len(sys.argv) > 1 and sys.argv[1] in ("version", "--version"):
        print("diffshield v0.1.2")
        return

    # ponytail: naive sys.argv parsing. Upgrade to argparse when subcommands or complex flags are added.
    json_mode = "--json" in sys.argv
    quiet_mode = "--quiet" in sys.argv or "-q" in sys.argv
    allow_deletions = "--allow-deletions" in sys.argv

    base_ref = "HEAD"
    for i, arg in enumerate(sys.argv):
        if arg == "--base" and i + 1 < len(sys.argv):
            base_ref = sys.argv[i + 1]
        elif arg.startswith("--base="):
            base_ref = arg.split("=", 1)[1]

    violations = audit_diff(base_ref=base_ref)

    if json_mode:
        payload = {
            "clean": len(violations) == 0,
            "violations": violations,
            "count": len(violations),
            "allowed": allow_deletions and len(violations) > 0
        }
        print(json.dumps(payload, indent=2))
        sys.exit(0 if (not violations or allow_deletions) else 1)

    if not violations:
        if not quiet_mode:
            print("🛡️  diffshield: No semantic deletions or contract breaks detected. Clean diff.")
        sys.exit(0)

    if allow_deletions:
        if not quiet_mode:
            print("⚠️  diffshield: Semantic deletions detected, but permitted via --allow-deletions:")
            for v in violations:
                print(f"  • {v}")
        sys.exit(0)

    if not quiet_mode:
        print("🚨 diffshield: SEMANTIC DIFF VIOLATION DETECTED!")
        print("The agent modification dropped critical logic or contracts:")
        for v in violations:
            print(f"  • {v}")
        print("\nAction: Refusing commit. Review changes or run with --allow-deletions if intentional.")
    sys.exit(1)

if __name__ == "__main__":
    main()
