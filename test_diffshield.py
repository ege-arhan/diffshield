#!/usr/bin/env python3
"""Single runnable assert-based check for diffshield AST logic."""

import subprocess
from diffshield import ASTInspector, compare_entities

def test_ast_inspector():
    src_clean = """
@auth.required
@rate_limit(10)
def authenticate(token: str):
    if not token:
        raise ValueError("token required")
    try:
        data = decode(token)
        return data
    except Exception as e:
        log.error(e)
        return None

@dataclass
class Session:
    pass

def managed_work():
    with open("data.txt") as f:
        return f.read()

def test_something():
    assert 1 == 1
    assert 2 == 2
"""
    entities = ASTInspector.extract_entities(src_clean)
    assert "authenticate" in entities["functions"], "fail func detection"
    assert "test_something" in entities["functions"], "fail func detection"
    assert "Session" in entities["classes"], "fail class detection"
    assert entities["try_blocks"] == 1, "fail try block detection"
    assert entities["assertions"] == 2, "fail assertion detection"
    assert entities["guard_clauses"] == 1, "fail guard clause detection"
    assert entities["with_blocks"] == 1, "fail with block detection"
    assert ("authenticate", "@auth.required") in entities["decorators"]
    assert ("Session", "@dataclass") in entities["decorators"]

    # Agent deletes error handling, assertion, and decorators
    src_tampered = """
def authenticate(token: str):
    return decode(token)

class Session:
    pass

def managed_work():
    return None

def test_something():
    pass
"""
    tampered_entities = ASTInspector.extract_entities(src_tampered)
    assert tampered_entities["try_blocks"] == 0, "try block should be 0"
    assert tampered_entities["assertions"] == 0, "assertions should be 0"
    assert tampered_entities["guard_clauses"] == 0, "guard clauses should be 0"
    assert len(tampered_entities["decorators"]) == 0, "decorators should be 0"

    violations = compare_entities(entities, tampered_entities, path="tests/test_tampered.py")
    assert any("[STRIP_ERROR_HANDLER]" in v for v in violations), "should detect stripped try block"
    assert any("[STRIP_GUARD]" in v for v in violations), "should detect stripped guard clause"
    assert any("[STRIP_ASSERTION]" in v for v in violations), "should detect dropped assertion"
    assert any("[STRIP_DECORATOR]" in v for v in violations), "should detect stripped decorator"
    assert any("[STRIP_CONTEXT_MANAGER]" in v for v in violations), "should detect stripped context manager"
    assert any("@auth.required from authenticate" in v for v in violations)
    assert any("@dataclass from Session" in v for v in violations)

    import os
    here = os.path.dirname(os.path.abspath(__file__))
    res = subprocess.run(["python3", os.path.join(here, "diffshield.py"), "--json"], capture_output=True, text=True, cwd=here)
    assert "clean" in res.stdout, "--json should output json object"

    res_q = subprocess.run(["python3", os.path.join(here, "diffshield.py"), "--quiet"], capture_output=True, text=True, cwd=here)
    assert res_q.stdout == "", "--quiet should produce no output on clean diff"

    res_v = subprocess.run(["python3", os.path.join(here, "diffshield.py"), "--version"], capture_output=True, text=True, cwd=here)
    assert "0.1.5" in res_v.stdout, "--version should output diffshield v0.1.5"

    res_help = subprocess.run(["python3", os.path.join(here, "diffshield.py"), "--help"], capture_output=True, text=True, cwd=here)
    assert "Usage: diffshield" in res_help.stdout, "--help should output usage help"

    res_base = subprocess.run(["python3", os.path.join(here, "diffshield.py"), "--base", "HEAD", "--json"], capture_output=True, text=True, cwd=here)
    assert "clean" in res_base.stdout, "--base should accept git ref"

    res_staged = subprocess.run(["python3", os.path.join(here, "diffshield.py"), "--staged", "--json"], capture_output=True, text=True, cwd=here)
    assert "clean" in res_staged.stdout, "--staged should accept staged flag"

    print("All internal assertions passed cleanly.")


def test_whole_file_deletion_blocked():
    """Agent deleting a file outright must not pass as a clean diff."""
    import os, tempfile
    here = os.path.dirname(os.path.abspath(__file__))
    with tempfile.TemporaryDirectory() as tmp:
        run = lambda *a: subprocess.run(a, cwd=tmp, capture_output=True, text=True)
        run("git", "init", "-q")
        run("git", "config", "user.email", "t@t.t")
        run("git", "config", "user.name", "t")
        with open(os.path.join(tmp, "auth.py"), "w") as f:
            f.write("def check_token(t):\n    if not t:\n        raise PermissionError\n")
        run("git", "add", "-A")
        run("git", "commit", "-qm", "init")
        os.remove(os.path.join(tmp, "auth.py"))

        res = run("python3", os.path.join(here, "diffshield.py"))
        assert res.returncode == 1, f"deleted file must fail, got {res.returncode}: {res.stdout}"
        assert "[DROP_FUNC]" in res.stdout, "deleted file should report DROP_FUNC"


if __name__ == "__main__":
    test_ast_inspector()
    test_whole_file_deletion_blocked()
