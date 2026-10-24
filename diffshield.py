#!/usr/bin/env python3
"""
diffshield - Zero-overhead semantic diff firewall for AI coding agents.
Inspects git diffs via AST to catch silent code deletions, stripped error handlers,
and dropped test assertions.
"""

import ast
import os
import subprocess
import sys
from typing import Dict, List, Set, Tuple

# ponytail: stdlib-only python AST parser first. Add tree-sitter/oxc when multi-language support is requested.

class CodeEntity:
    def __init__(self, name: str, kind: str, line: int):
        self.name = name
        self.kind = kind
        self.line = line

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

def get_git_file_content(commit_ref: str, path: str) -> str:
    """Get file content from git at a given ref (e.g. HEAD)."""
    try:
        out = subprocess.check_output(["git", "show", f"{commit_ref}:{path}"], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError:
        return ""

def get_changed_files() -> List[str]:
    """Get list of modified and unstaged/staged files."""
    try:
        out = subprocess.check_output(["git", "diff", "--name-only", "HEAD"], stderr=subprocess.DEVNULL)
        files = [f.strip() for f in out.decode().splitlines() if f.strip().endswith(".py")]
        # Also check untracked changes vs staged
        out_cached = subprocess.check_output(["git", "diff", "--name-only", "--cached"], stderr=subprocess.DEVNULL)
        for f in out_cached.decode().splitlines():
            if f.strip().endswith(".py") and f.strip() not in files:
                files.append(f.strip())
        return files
    except subprocess.CalledProcessError:
        return []

def audit_diff() -> List[str]:
    """Audit current working directory diff for dangerous semantic deletions."""
    files = get_changed_files()
    violations = []

    for path in files:
        if not os.path.isfile(path):
            continue
        old_src = get_git_file_content("HEAD", path)
        if not old_src:
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                new_src = f.read()
        except OSError:
            continue

        old_meta = ASTInspector.extract_entities(old_src)
        new_meta = ASTInspector.extract_entities(new_src)

        # 1. Dropped functions
        dropped_funcs = old_meta["functions"] - new_meta["functions"]
        if dropped_funcs:
            violations.append(f"[DROP_FUNC] {path}: deleted functions -> {', '.join(sorted(dropped_funcs))}")

        # 2. Dropped classes
        dropped_classes = old_meta["classes"] - new_meta["classes"]
        if dropped_classes:
            violations.append(f"[DROP_CLASS] {path}: deleted classes -> {', '.join(sorted(dropped_classes))}")

        # 3. Stripped error handling (try/catch blocks)
        if old_meta["try_blocks"] > new_meta["try_blocks"]:
            diff_cnt = old_meta["try_blocks"] - new_meta["try_blocks"]
            violations.append(f"[STRIP_ERROR_HANDLER] {path}: stripped {diff_cnt} try/except block(s)")

        # 4. Stripped test assertions
        if "test" in path.lower() and old_meta["assertions"] > new_meta["assertions"]:
            diff_cnt = old_meta["assertions"] - new_meta["assertions"]
            violations.append(f"[STRIP_ASSERTION] {path}: dropped {diff_cnt} test assertion(s)")

        # 5. Stripped guard clauses (if cond: return/raise)
        if old_meta["guard_clauses"] > new_meta["guard_clauses"]:
            diff_cnt = old_meta["guard_clauses"] - new_meta["guard_clauses"]
            violations.append(f"[STRIP_GUARD] {path}: removed {diff_cnt} guard clause(s)")

    return violations

def main():
    if len(sys.argv) > 1 and sys.argv[1] == "version":
        print("diffshield v0.1.0")
        return

    violations = audit_diff()
    if not violations:
        print("🛡️  diffshield: No semantic deletions or contract breaks detected. Clean diff.")
        sys.exit(0)

    print("🚨 diffshield: SEMANTIC DIFF VIOLATION DETECTED!")
    print("The agent modification dropped critical logic or contracts:")
    for v in violations:
        print(f"  • {v}")
    print("\nAction: Refusing commit. Review changes or run with --allow-deletions if intentional.")
    sys.exit(1)

if __name__ == "__main__":
    main()
