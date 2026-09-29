# Computer Use for Windows

> **High-performance, native Windows desktop automation skill and CLI for AI agents (OpenCode, OpenAI Codex, Antigravity, Claude Code).**

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: Windows](https://img.shields.io/badge/Platform-Windows%2010%20%7C%2011-0078D6.svg)](https://microsoft.com)
[![Python: 3.10+](https://img.shields.io/badge/Python-3.10%2B-brightgreen.svg)](https://python.org)

An analog of OpenAI Codex / Anthropic Computer Use engineered specifically for Windows. Features sub-second direct UI interrogation, authentic Google 4-color glowing border overlay, 60 FPS animated cursor halo, DPI-aware GDI perception with coordinate grids, and Unicode/clipboard typing.

---

## ⚡ Highlights

* **Google-Colored Visual Overlay**: Real-time 6px glowing perimeter frame (Blue, Red, Yellow, Green), floating status pill badge (`⚡ AI is controlling your computer`), and 60 FPS animated multi-color cursor halo. 100% click-through, non-blocking layered Win32 window (`WS_EX_TRANSPARENT`).
* **Sub-Second Desktop Interrogation (`SysListView32`)**: Queries Windows Explorer desktop control directly in memory (`VirtualAllocEx` + `LVM_GETITEMTEXTW` / `LVM_GETITEMPOSITION`) to resolve icon names and coordinates in **< 20 ms** and launch applications in **< 0.4 s**.
* **Pixel-Accurate GDI Perception**: GDI `BitBlt` capture with Per-Monitor DPI awareness (`SetProcessDpiAwareness(2)`) for exact 1:1 physical pixel matching across multi-monitor setups.
* **Coordinate Grid System (`--grid`)**: Automatic 100px coordinate grid with labeled coordinate numbers along all borders for multimodal LLM visual grounding.
* **Unicode & Instant Clipboard Injection**: Windows `SendInput` for keys and mouse; instant clipboard paste (`paste`) for fast, error-free typing of multilingual text (Russian, English, emoji, code) without layout switching artifacts.
* **Batch Multi-Action Pipelines (`batch`)**: Sequences clicks, keystrokes, window focus, and screenshots in a single JSON payload with automatic visual overlay lifecycle.
* **Safety First**: Moving the mouse cursor to `(0, 0)` triggers an instant safety abort; Esc hotkey dismisses overlay.

---

## 🛠️ Architecture

```
computer-use/
├── SKILL.md                 # Agent instructions (OpenCode, Codex, Antigravity, Claude)
├── README.md                # Documentation & Quickstart
├── requirements.txt         # Dependencies (Pillow, pywin32)
├── LICENSE                  # MIT License
└── scripts/
    ├── computer.py          # Unified CLI entrypoint with batch runner & JSON output
    ├── screen.py            # DPI-aware GDI BitBlt capture, coordinate grid, target markers
    ├── mouse.py             # SendInput mouse moves, clicks, drag & drop, wheel scroll
    ├── keyboard.py          # SendInput Unicode typing, hotkeys, special keys
    ├── window.py            # Desktop window manager (OpenInputDesktop, HWND focus)
    ├── clipboard.py         # Win32 Unicode clipboard reader and writer
    ├── desktop.py           # SysListView32 fast desktop icon resolver
    └── overlay.py           # Layered click-through Google border & cursor halo overlay
```

---

## 🚀 Quick Start

### 1. Installation

```bash
git clone https://github.com/t1m0nch1k/computer-use-windows.git
cd computer-use-windows
pip install -r requirements.txt
```

### 2. Basic CLI Commands

```bash
# Capture full screen with 100px coordinate grid
python scripts/computer.py screenshot --grid screen.png

# Fast-launch desktop icon in < 0.4s (activates Google overlay automatically)
python scripts/computer.py launch-icon "Cristalix"

# Click at coordinates (physical pixels)
python scripts/computer.py click 500 300

# Type text or paste instantly via clipboard
python scripts/computer.py paste "https://github.com"
python scripts/computer.py type "Hello from AI Agent"

# Press hotkey combinations
python scripts/computer.py hotkey win r
python scripts/computer.py hotkey ctrl shift esc

# List open windows with HWNDs and bounding boxes
python scripts/computer.py windows --json

# Bring window to foreground
python scripts/computer.py focus "Firefox"
```

### 3. Visual Overlay

```bash
# Start Google glowing border + cursor halo for 10 seconds
python scripts/computer.py overlay start --duration 10.0

# Stop overlay
python scripts/computer.py overlay stop
```

### 4. Batch Automation Pipeline

```bash
python scripts/computer.py batch '[
  {"action": "focus", "window": "Firefox"},
  {"action": "wait", "seconds": 0.3},
  {"action": "click", "x": 500, "y": 75},
  {"action": "paste", "text": "https://news.ycombinator.com"},
  {"action": "press", "key": "enter"},
  {"action": "wait", "seconds": 2.0},
  {"action": "screenshot", "grid": true, "path": "screen.png"}
]' --json
```

---

## 🤖 Agent Integrations

### OpenCode (`opencode.ai`)

Place or symlink the folder in OpenCode's skills directory:
```bash
# Global installation for OpenCode
mkdir -p ~/.config/opencode/skills
cp -r computer-use ~/.config/opencode/skills/
```

Verify with:
```bash
opencode debug skill
```

You can also use:
* **Slash command**: Type `/computer <action>`
* **Specialized agent**: `opencode --agent desktop`

### OpenAI Codex & Antigravity

Symlink or copy to the respective skills directory:
```bash
# Codex
cp -r computer-use ~/.codex/skills/

# Antigravity
cp -r computer-use ~/.gemini/config/skills/
```

---

## 📋 Requirements

* Windows 10 or Windows 11 (x64)
* Python 3.10+
* `Pillow>=10.0.0`
* `pywin32>=306`

---

## 📄 License

MIT License. See [LICENSE](LICENSE) for details.
