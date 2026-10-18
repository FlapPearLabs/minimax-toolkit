# MiniMax Toolkit (`minimax` CLI)

> **Zero-Dependency Multi-Account Manager & Automated Check-in Engine for MiniMax Code**  
> Developed & Maintained by [FlapPearLabs](https://github.com/FlapPearLabs)

---

## ⚡ Features

- 🔄 **Multi-Account Profile Management**: Support for multiple account profiles (`minimax login <alias>`, `minimax switch <alias>`).
- 🕒 **Automated Headless Check-in**: Native macOS `launchd` / Linux `systemd` / Windows Task Scheduler daily automated check-in.
- 🔑 **OAuth2 Self-Healing (Rolling Refresh)**: Automatic token rotation without expiring, eliminating frequent QR-code logins.
- 📊 **Quota & Usage Auditing**: Instant status inspection of daily sign-in streak, scene progress, and points balance.
- 🛡️ **Zero-Dependency Core**: Pure Python 3 standard library implementation, no bulky Electron UI overhead.

---

## 📁 Repository Structure

```text
minimax-toolkit/
├── bin/
│   └── minimax              # Primary unified CLI entrypoint
├── launchd/
│   └── com.minimax.dailycheckin.plist
├── systemd/
│   └── minimax-checkin.service
├── install.py               # Cross-platform installer
├── uninstall.py             # Safe uninstaller
├── tests/                   # High-fidelity test suite
└── README.md
```

---

## 📄 License

MIT © [FlapPearLabs](https://github.com/FlapPearLabs)
