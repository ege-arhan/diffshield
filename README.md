# 🛡️ diffshield

> **Zero-overhead semantic diff firewall for AI coding agents.**  
> Catch silent code deletions, stripped error handlers, and dropped assertions before they reach git.

[![CI](https://github.com/ege-arhan/diffshield/actions/workflows/ci.yml/badge.svg)](https://github.com/ege-arhan/diffshield/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg?style=flat-square)](LICENSE)
[![Python: 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg?style=flat-square)](https://python.org)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-0-success.svg?style=flat-square)](diffshield.py)

---

### The Problem

AI coding agents (Cursor, Claude Code, Aider, Copilot) frequently hallucinate refactors by:
1. **Silently deleting helper functions** or edge-case routines.
2. **Stripping `try/except` error handling** to make code "look cleaner".
3. **Dropping `assert` statements in tests** to make failing tests pass falsely.
4. **Removing security guard clauses** (`if not token: raise ...`).

Cloud reviewers (CodeRabbit) catch this too late at PR review. `diffshield` runs **locally in milliseconds** via deterministic AST analysis before commit.

---

### Installation

Install via `pip` or `pipx`:

```bash
# Isolated CLI via pipx (recommended)
pipx install diffshield

# Or via standard pip
pip install diffshield

# From local checkout
pip install .
```

---

### Features

- ⚡ **Zero Dependencies:** Pure Python standard library (`ast`). Instant execution (<10ms).
- 🔍 **Semantic Deletion Detection:**
  - `[DROP_FUNC]`: Detects deleted functions and methods (including scoped class methods).
  - `[DROP_CLASS]`: Detects removed classes.
  - `[STRIP_ERROR_HANDLER]`: Catches stripped `try/except` blocks.
  - `[STRIP_FINALLY]`: Detects stripped `finally` cleanup blocks.
  - `[STRIP_GUARD]`: Flags removed guard clauses (`if ...: return/raise`).
  - `[STRIP_CONTEXT_MANAGER]`: Flags stripped context managers (`with` / `async with` locks, transactions, file handles).
  - `[STRIP_DECORATOR]`: Detects stripped security or route decorators (`@auth.required`, `@router.get`, `@dataclass`).
  - `[HOLLOW_FUNC]`: Detects hollowed-out functions (bodies replaced with `pass`, `...`, docstring-only, or `raise NotImplementedError`).
  - `[STRIP_ASSERTION]`: Detects deleted test assertions (`assert` and `self.assert*`).
- 🪝 **Pre-commit & CI Native:** Exits with `1` on contract violations to block bad agent commits. Exits `2` cleanly if executed outside a git repository.

---

### Usage & Demo

```bash
# Audit current working tree modifications (unstaged changes)
diffshield

# Audit staged changes before commit
diffshield --staged

# Compare against a specific git ref or branch
diffshield --base origin/main

# Machine-readable JSON output for agent orchestration/tooling
diffshield --json

# Warn without non-zero exit code (advisory mode)
diffshield --allow-deletions

# Quiet mode (silent on clean diff)
diffshield -q
```

#### Demo Output

```text
🚨 diffshield: SEMANTIC DIFF VIOLATION DETECTED!
The agent modification dropped critical logic or contracts:
  • [STRIP_ERROR_HANDLER] api/routes.py: stripped 2 try/except block(s)
  • [STRIP_GUARD] auth/session.py: removed 1 guard clause(s)
  • [STRIP_ASSERTION] tests/test_auth.py: dropped 3 test assertion(s)

Action: Refusing commit. Review changes or run with --allow-deletions if intentional.
```

---

### Pre-commit Integration

Add `diffshield` to your `.pre-commit-config.yaml`:

```yaml
repos:
  - repo: https://github.com/ege-arhan/diffshield
    rev: v1.0.0
    hooks:
      - id: diffshield
```

Or install as a native git hook without pre-commit framework:

```bash
echo '#!/bin/sh\nexec diffshield --staged' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

---

### License

MIT © [Ege Arhan](https://github.com/ege-arhan)
