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
