#!/usr/bin/env python3
"""
diffshield - Zero-overhead semantic diff firewall for AI coding agents.
Inspects git diffs via AST to catch silent code deletions, stripped error handlers,
and dropped test assertions.
"""

import ast
import json
import subprocess
import sys
from typing import Dict, List, Set

# ponytail: stdlib-only python AST parser first. Add tree-sitter/oxc when multi-language support is requested.

def _get_decorator_name(node: ast.AST) -> str:
    """Extract decorator name identifier or dotted path."""
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node).split("(")[0].strip()
        except Exception:
            pass
    while isinstance(node, ast.Call):
        node = node.func
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return "decorator"

def _is_stub_body(body: List[ast.stmt]) -> bool:
    """Detect if function body is just pass, docstring, ellipsis, or NotImplementedError."""
    for stmt in body:
        if isinstance(stmt, ast.Pass):
            continue
        if isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant):
            if isinstance(stmt.value.value, str) or stmt.value.value is Ellipsis:
                continue
        if isinstance(stmt, ast.Raise):
            exc = stmt.exc
            name = None
            if isinstance(exc, ast.Name):
                name = exc.id
            elif isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
                name = exc.func.id
            if name == "NotImplementedError":
                continue
        return False
    return True

class _EntityVisitor(ast.NodeVisitor):
    def __init__(self):
        self.scope: List[str] = []
        self.data = {
            "functions": set(),
            "classes": set(),
            "decorators": set(),
            "try_blocks": 0,
            "assertions": 0,
            "guard_clauses": 0,
            "with_blocks": 0,
            "stub_funcs": set()
        }

    def _qualname(self, name: str) -> str:
        return ".".join(self.scope + [name]) if self.scope else name

    def visit_ClassDef(self, node: ast.ClassDef):
        qname = self._qualname(node.name)
        self.data["classes"].add(qname)
        for dec in node.decorator_list:
            self.data["decorators"].add((qname, f"@{_get_decorator_name(dec)}"))
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def _handle_func(self, node):
        qname = self._qualname(node.name)
        self.data["functions"].add(qname)
        for dec in node.decorator_list:
            self.data["decorators"].add((qname, f"@{_get_decorator_name(dec)}"))
        if _is_stub_body(node.body):
            self.data["stub_funcs"].add(qname)
        self.scope.append(node.name)
        self.generic_visit(node)
        self.scope.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef):
        self._handle_func(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef):
        self._handle_func(node)

    def visit_Try(self, node: ast.Try):
        self.data["try_blocks"] += 1
        self.generic_visit(node)

    def visit_TryStar(self, node):
        self.data["try_blocks"] += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With):
        self.data["with_blocks"] += 1
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith):
        self.data["with_blocks"] += 1
        self.generic_visit(node)

    def visit_Assert(self, node: ast.Assert):
        self.data["assertions"] += 1
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        # ponytail: prefix matching for unittest/mock assertions. Upgrade to symbol resolution if custom assertion helpers need strict tracking.
        name = ""
        if isinstance(node.func, ast.Attribute):
            name = node.func.attr
        elif isinstance(node.func, ast.Name):
            name = node.func.id
        if name.startswith("assert") and name != "assert":
            self.data["assertions"] += 1
        self.generic_visit(node)

    def visit_If(self, node: ast.If):
        for stmt in node.body:
            if isinstance(stmt, (ast.Raise, ast.Return)):
                self.data["guard_clauses"] += 1
                break
        self.generic_visit(node)

class ASTInspector:
    @staticmethod
    def extract_entities(source: str) -> Dict[str, any]:
        """Extract functions, classes, try/except blocks, and test assertions from source."""
        data = {
            "functions": set(),
            "classes": set(),
            "decorators": set(),
            "try_blocks": 0,
            "assertions": 0,
            "guard_clauses": 0,
            "with_blocks": 0,
            "stub_funcs": set()
        }
        if not source.strip():
            return data
            
        try:
            tree = ast.parse(source)
        except SyntaxError:
            return data

        visitor = _EntityVisitor()
        visitor.visit(tree)
        return visitor.data

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

    # 6. Stripped decorators from surviving functions or classes
    surviving = (old_meta["functions"] & new_meta["functions"]) | (old_meta["classes"] & new_meta["classes"])
    old_decs = old_meta.get("decorators", set())
    new_decs = new_meta.get("decorators", set())
    dropped_decs = sorted(f"{dec} from {target}" for target, dec in (old_decs - new_decs) if target in surviving)
    if dropped_decs:
        violations.append(f"[STRIP_DECORATOR] {prefix}stripped decorator(s) -> {', '.join(dropped_decs)}")

    # 7. Stripped context managers (with/async with blocks)
    old_with = old_meta.get("with_blocks", 0)
    new_with = new_meta.get("with_blocks", 0)
    if old_with > new_with:
        diff_cnt = old_with - new_with
        violations.append(f"[STRIP_CONTEXT_MANAGER] {prefix}stripped {diff_cnt} context manager (with) block(s)")

    # 8. Hollowed out functions (implemented function replaced with pass/.../NotImplementedError)
    old_stubs = old_meta.get("stub_funcs", set())
    new_stubs = new_meta.get("stub_funcs", set())
    surviving_funcs = old_meta.get("functions", set()) & new_meta.get("functions", set())
    hollowed = sorted(f for f in (new_stubs - old_stubs) if f in surviving_funcs)
    if hollowed:
        violations.append(f"[HOLLOW_FUNC] {prefix}function body replaced with stub/pass -> {', '.join(hollowed)}")

    return violations

def get_git_file_content(commit_ref: str, path: str) -> str:
    """Get file content from git at a given ref (e.g. HEAD) or index if commit_ref is empty."""
    target = f":{path}" if not commit_ref else f"{commit_ref}:{path}"
    try:
        out = subprocess.check_output(["git", "show", target], stderr=subprocess.DEVNULL)
        return out.decode("utf-8", errors="ignore")
    except subprocess.CalledProcessError:
        return ""

def get_changed_files(base_ref: str = "HEAD", staged: bool = False) -> List[str]:
    """Get list of modified and unstaged/staged files against base_ref."""
    cmd = ["git", "diff", "--name-only"]
    if staged:
        cmd.extend(["--cached", base_ref])
    else:
        cmd.append(base_ref)
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL)
        files = [f.strip() for f in out.decode().splitlines() if f.strip().endswith(".py")]
        return sorted(list(set(files)))
    except subprocess.CalledProcessError:
        return []

def audit_diff(base_ref: str = "HEAD", staged: bool = False) -> List[str]:
    """Audit diff against base_ref for dangerous semantic deletions."""
    files = get_changed_files(base_ref=base_ref, staged=staged)
    violations = []

    for path in files:
        old_src = get_git_file_content(base_ref, path)
        if not old_src:
            continue
        if staged:
            new_src = get_git_file_content("", path)
        else:
            try:
                with open(path, "r", encoding="utf-8", errors="ignore") as f:
                    new_src = f.read()
            except OSError:
                # Whole-file deletion is the most common agent action: treat as empty
                # source so every entity counts as dropped instead of skipping it.
                new_src = ""

        old_meta = ASTInspector.extract_entities(old_src)
        new_meta = ASTInspector.extract_entities(new_src)
        violations.extend(compare_entities(old_meta, new_meta, path=path))

    return violations

HELP_TEXT = """Usage: diffshield [OPTIONS]

Zero-overhead semantic diff firewall for AI coding agents.

Options:
  --base <ref>       Git reference to compare against (default: HEAD)
  --staged, --cached Audit staged/indexed changes only (pre-commit hook mode)
  --allow-deletions  Warn on semantic deletions instead of exiting with 1
  --json             Output results as JSON
  -q, --quiet        Suppress output when diff is clean
  -h, --help         Show this help message and exit
  -v, --version      Show diffshield version and exit
"""

def main():
    if any(arg in sys.argv[1:] for arg in ("-h", "--help")):
        print(HELP_TEXT.strip())
        return

    if any(arg in sys.argv[1:] for arg in ("-v", "--version", "version")):
        print("diffshield v0.1.8")
        return

    # ponytail: naive sys.argv parsing. Upgrade to argparse when subcommands or complex flags are added.
    json_mode = "--json" in sys.argv
    quiet_mode = "--quiet" in sys.argv or "-q" in sys.argv
    allow_deletions = "--allow-deletions" in sys.argv
    staged = "--staged" in sys.argv or "--cached" in sys.argv

    base_ref = "HEAD"
    for i, arg in enumerate(sys.argv):
        if arg == "--base" and i + 1 < len(sys.argv):
            base_ref = sys.argv[i + 1]
        elif arg.startswith("--base="):
            base_ref = arg.split("=", 1)[1]

    violations = audit_diff(base_ref=base_ref, staged=staged)

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
