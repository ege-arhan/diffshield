# 🛡️ diffshield

> **Zero-overhead semantic diff firewall for AI coding agents.**  
> Catch silent code deletions, stripped error handlers, and dropped assertions before they reach git.

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

### Features

- ⚡ **Zero Dependencies:** Pure Python standard library (`ast`). Instant execution (<10ms).
- 🔍 **Semantic Deletion Detection:**
  - `[DROP_FUNC]`: Detects deleted functions and methods.
  - `[DROP_CLASS]`: Detects removed classes.
  - `[STRIP_ERROR_HANDLER]`: Catches stripped `try/except` blocks.
  - `[STRIP_GUARD]`: Flags removed guard clauses (`if ...: return/raise`).
  - `[STRIP_CONTEXT_MANAGER]`: Flags stripped context managers (`with` / `async with` locks, transactions, file handles).
  - `[STRIP_DECORATOR]`: Detects stripped security or route decorators (`@auth.required`, `@router.get`, `@dataclass`).
  - `[STRIP_ASSERTION]`: Detects deleted test assertions.
- 🪝 **Pre-commit & CI Native:** Exits with `1` on contract violations to block bad agent commits.

---

### Quick Start

```bash
# Run audit on current uncommitted changes
python3 diffshield.py

# Run audit on staged changes only (pre-commit)
python3 diffshield.py --staged

# Install as git pre-commit hook
echo '#!/bin/sh\nexec python3 diffshield.py --staged' > .git/hooks/pre-commit
chmod +x .git/hooks/pre-commit
```

### Example Output

```text
🚨 diffshield: SEMANTIC DIFF VIOLATION DETECTED!
The agent modification dropped critical logic or contracts:
  • [STRIP_ERROR_HANDLER] api/routes.py: stripped 2 try/except block(s)
  • [STRIP_GUARD] auth/session.py: removed 1 guard clause(s)
  • [STRIP_ASSERTION] tests/test_auth.py: dropped 3 test assertion(s)

Action: Refusing commit. Review changes or run with --allow-deletions if intentional.
```

---

### License

MIT © [Ege Arhan](https://github.com/ege-arhan)
