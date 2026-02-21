# Ghost Post 📨

Intelligent email management system connected to Gmail. Gives Athena full email awareness and agency over email communication.

## Features

- **Gmail Integration** - Full IMAP access to athenacapitao@gmail.com
- **Complete Email Tracking** - All incoming + outgoing emails logged
- **Context Management** - Thread analysis, entity extraction, topic tracking
- **Automatic Replies** - Rule-based + AI-assisted with approval workflow

## Architecture

```
ghostpost/
├── src/
│   ├── ingestion/      # Email capture layer
│   ├── context/        # Thread analysis engine
│   ├── replies/        # Reply generation system
│   └── memory/         # Contact & preference storage
├── tests/
├── README.md
└── requirements.txt
```

## Quick Start

```bash
# Clone and setup
git clone https://github.com/athenacapitao/ghostpost.git
cd ghostpost
pip install -r requirements.txt

# Run
python -m src.main
```

## Tech Stack

- Python 3.10+
- IMAP (himalaya CLI)
- SQLite for local storage

## Status

🆕 New Project (2026-02-21)

---

Built by Athena Capitão
