#!/usr/bin/env python3
"""Single runnable assert-based check for diffshield AST logic."""

from diffshield import ASTInspector

def test_ast_inspector():
    src_clean = """
def authenticate(token: str):
    if not token:
        raise ValueError("token required")
    try:
        data = decode(token)
        return data
    except Exception as e:
        log.error(e)
        return None

def test_something():
    assert 1 == 1
    assert 2 == 2
"""
    entities = ASTInspector.extract_entities(src_clean)
    assert "authenticate" in entities["functions"], "fail func detection"
    assert "test_something" in entities["functions"], "fail func detection"
    assert entities["try_blocks"] == 1, "fail try block detection"
    assert entities["assertions"] == 2, "fail assertion detection"
    assert entities["guard_clauses"] == 1, "fail guard clause detection"

    # Agent deletes error handling and assertion
    src_tampered = """
def authenticate(token: str):
    return decode(token)

def test_something():
    pass
"""
    tampered_entities = ASTInspector.extract_entities(src_tampered)
    assert tampered_entities["try_blocks"] == 0, "try block should be 0"
    assert tampered_entities["assertions"] == 0, "assertions should be 0"
    assert tampered_entities["guard_clauses"] == 0, "guard clauses should be 0"

    import subprocess
    res = subprocess.run(["python3", "diffshield.py", "--json"], capture_output=True, text=True)
    assert "clean" in res.stdout, "--json should output json object"

    res_q = subprocess.run(["python3", "diffshield.py", "--quiet"], capture_output=True, text=True)
    assert res_q.stdout == "", "--quiet should produce no output on clean diff"

    print("All internal assertions passed cleanly.")

if __name__ == "__main__":
    test_ast_inspector()
