# GhostPost - Test Feature PRD

**Created:** 2026-02-22
**Project:** GhostPost
**Status:** Test

---

## Problem Statement

Need a simple test to verify the autonomous workflow works.

---

## Solution Overview

Create a simple test script that outputs a JSON response.

### Key Features
1. Python script that prints JSON: {"status": "ok", "message": "GhostPost is working"}

---

## Implementation

### Files to Create
- `src/test_endpoint.py` - Test script that prints JSON

### Run Command
```bash
python src/test_endpoint.py
```

### Expected Output
```json
{"status": "ok", "message": "GhostPost is working"}
```

---

## Success

Script runs and outputs expected JSON.
