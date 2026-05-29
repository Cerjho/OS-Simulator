#!/usr/bin/env python3
"""
sim_launcher.py — OS Simulation Project Management CLI.

Unified command-line interface for testing, serving, and launching
the OS Simulation & Experimentation environment.

Usage:
    python sim_launcher.py setup             First-time setup wizard
    python sim_launcher.py setup --yes       Non-interactive setup (accept defaults)
    python sim_launcher.py setup --reset     Re-run setup even if already completed
    python sim_launcher.py test              Run all unit tests with coverage report
    python sim_launcher.py test --html       Run tests and generate HTML coverage report
    python sim_launcher.py backend           Start the FastAPI backend server
    python sim_launcher.py frontend          Start the React dashboard dev server
    python sim_launcher.py start             Start both backend and frontend together
    python sim_launcher.py docs              Serve the MkDocs documentation site
    python sim_launcher.py docs --build      Build static docs into site/
    python sim_launcher.py check             Quick health check (tests + lint)
    python sim_launcher.py all               Run tests, then start backend + frontend
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Force UTF-8 encoding for stdout/stderr to support emojis on Windows
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except AttributeError:
        pass

# ── Constants ─────────────────────────────────────────────────────────────────

ROOT_DIR = Path(__file__).resolve().parent
DASHBOARD_DIR = ROOT_DIR / "dashboard"
SENTINEL_FILE = ROOT_DIR / ".os_sim_initialized"
SETUP_VERSION = 1  # Bump this to trigger re-setup prompts on upgrades

# Cross-platform venv detection: Windows uses Scripts/, Linux/macOS uses bin/
if sys.platform == "win32":
    VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
    VENV_PIP = ROOT_DIR / ".venv" / "Scripts" / "pip.exe"
else:
    VENV_PYTHON = ROOT_DIR / ".venv" / "bin" / "python"
    VENV_PIP = ROOT_DIR / ".venv" / "bin" / "pip"

# Use venv python if available, otherwise system python
PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

# Core algorithm modules to track for 100% coverage
CORE_MODULES = [
    "modules.process.scheduler",
    "modules.memory.paging",
    "modules.memory.allocator",
    "modules.memory.tlb",
    "modules.io.disk",
    "modules.sync.deadlock",
    "modules.sync.mutex",
    "modules.sync.semaphore",
]

# All modules for full project coverage
ALL_MODULES = ["modules", "core"]

# ── ANSI Colors (fallback when Rich is unavailable) ──────────────────────────

_SUPPORTS_COLOR = hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    """Wrap text in ANSI color codes if terminal supports it."""
    if not _SUPPORTS_COLOR:
        return text
    return f"\033[{code}m{text}\033[0m"


def _dim(text: str) -> str:
    return _c("2", text)


def _bold(text: str) -> str:
    return _c("1", text)


def _cyan(text: str) -> str:
    return _c("96", text)


def _green(text: str) -> str:
    return _c("92", text)


def _yellow(text: str) -> str:
    return _c("93", text)


def _red(text: str) -> str:
    return _c("91", text)


def _magenta(text: str) -> str:
    return _c("95", text)


def _banner(title: str) -> None:
    """Print a visible section banner."""
    width = 70
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)
    print()


# ═══════════════════════════════════════════════════════════════════════════════
#  FIRST-TIME SETUP WIZARD
# ═══════════════════════════════════════════════════════════════════════════════

# ── Simulation config choices (mirrors core/config.py validation constants) ──

SCHEDULER_ALGORITHMS = {
    "round_robin": "Round Robin — Fair time-sliced scheduling (default)",
    "fcfs":        "FCFS — First Come, First Served (simplest, no preemption)",
    "sjf":         "SJF — Shortest Job First (optimal avg. waiting time)",
    "srtf":        "SRTF — Shortest Remaining Time First (preemptive SJF)",
    "priority":    "Priority — Higher priority runs first",
    "mlfq":        "MLFQ — Multi-Level Feedback Queue (adaptive)",
}

PAGE_ALGORITHMS = {
    "lru":     "LRU — Least Recently Used (most common, default)",
    "fifo":    "FIFO — First In, First Out (simple queue)",
    "optimal": "Optimal — Best possible (theoretical, uses future knowledge)",
    "clock":   "Clock — Second-chance approximation of LRU",
}

DISK_ALGORITHMS = {
    "c-scan": "C-SCAN — Circular SCAN (uniform wait times, default)",
    "fcfs":   "FCFS — First Come, First Served",
    "sstf":   "SSTF — Shortest Seek Time First",
    "scan":   "SCAN — Elevator algorithm",
    "look":   "LOOK — Like SCAN but reverses at last request",
    "c-look": "C-LOOK — Circular LOOK",
}

FS_TYPES = {
    "fat":   "FAT — File Allocation Table (simple, linked)",
    "inode": "inode — Unix-style indexed allocation",
}

RECOVERY_STRATEGIES = {
    "terminate_youngest":  "Terminate Youngest — Kill the most recently created process",
    "terminate_lowest":    "Terminate Lowest — Kill the lowest-priority process",
    "resource_preempt":    "Resource Preempt — Forcibly reclaim resources",
}


def _prompt(question: str, choices: dict[str, str], default: str, auto_yes: bool) -> str:
    """
    Interactive multiple-choice prompt. Returns the chosen key.
    If auto_yes is True, returns default without asking.
    """
    if auto_yes:
        print(f"  {_dim('→')} {question}: {_cyan(default)} {_dim('(auto)')}")
        return default

    print(f"\n  {_bold(question)}")
    keys = list(choices.keys())
    for i, (key, desc) in enumerate(choices.items(), 1):
        marker = _green("●") if key == default else " "
        label = f"  {marker} {_bold(str(i))}. {desc}"
        if key == default:
            label += f"  {_dim('[default]')}"
        print(label)

    while True:
        raw = input(f"  Choice [1-{len(keys)}, default={keys.index(default)+1}]: ").strip()
        if raw == "":
            return default
        try:
            idx = int(raw) - 1
            if 0 <= idx < len(keys):
                return keys[idx]
        except ValueError:
            if raw in keys:
                return raw
        print(f"  {_red('Invalid choice.')} Enter a number 1–{len(keys)}.")


def _prompt_int(question: str, default: int, min_val: int, max_val: int, auto_yes: bool) -> int:
    """Interactive integer prompt with validation."""
    if auto_yes:
        print(f"  {_dim('→')} {question}: {_cyan(str(default))} {_dim('(auto)')}")
        return default

    while True:
        raw = input(f"  {question} [{min_val}–{max_val}, default={default}]: ").strip()
        if raw == "":
            return default
        try:
            val = int(raw)
            if min_val <= val <= max_val:
                return val
            print(f"  {_red('Out of range.')} Enter a value between {min_val} and {max_val}.")
        except ValueError:
            print(f"  {_red('Not a number.')} Enter an integer.")


def _prompt_bool(question: str, default: bool, auto_yes: bool) -> bool:
    """Interactive yes/no prompt."""
    if auto_yes:
        print(f"  {_dim('→')} {question}: {_cyan('Yes' if default else 'No')} {_dim('(auto)')}")
        return default

    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"  {question} [{hint}]: ").strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False
        print(f"  {_red('Invalid.')} Enter y or n.")


def _prompt_confirm(question: str, default: bool = True) -> bool:
    """Simple yes/no confirmation (never auto-skipped)."""
    hint = "Y/n" if default else "y/N"
    while True:
        raw = input(f"{question} [{hint}]: ").strip().lower()
        if raw == "":
            return default
        if raw in ("y", "yes"):
            return True
        if raw in ("n", "no"):
            return False


# ── Step 1: Welcome Banner ──────────────────────────────────────────────────

def _setup_welcome() -> None:
    """Display the animated welcome banner and project overview."""
    art = r"""
   ____  _____    _____ _                 __      __
  / __ \/ ___/   / ___/(_)___ ___  __  __/ /___ _/ /_____  _____
 / / / /\__ \    \__ \/ / __ `__ \/ / / / / __ `/ __/ __ \/ ___/
/ /_/ /___/ /   ___/ / / / / / / / /_/ / / /_/ / /_/ /_/ / /
\____//____/   /____/_/_/ /_/ /_/\__,_/_/\__,_/\__/\____/_/
    """
    print(_cyan(art))
    print(_bold("  Welcome to the OS Simulation & Experimentation Environment"))
    print(_dim("  ─────────────────────────────────────────────────────────"))
    print()
    print("  This project simulates a complete operating system kernel with:")
    print(f"    {_green('•')} Process scheduling   (Round Robin, SJF, MLFQ, Priority, …)")
    print(f"    {_green('•')} Virtual memory        (Paging, TLB, Page Replacement)")
    print(f"    {_green('•')} Disk I/O scheduling  (SCAN, C-SCAN, SSTF, LOOK, …)")
    print(f"    {_green('•')} Synchronization      (Mutexes, Semaphores, Deadlock Detection)")
    print(f"    {_green('•')} File system           (FAT / inode simulation)")
    print(f"    {_green('•')} Real-time dashboard  (React + WebSocket live visualization)")
    print()
    print(_dim("  Let's get your environment set up. This will take about 1–2 minutes."))
    print()


# ── Step 2: Environment Validation ──────────────────────────────────────────

def _check_command(name: str, cmd: list[str], min_version: str | None = None) -> tuple[bool, str]:
    """
    Check if a command is available and optionally meets a minimum version.
    Returns (ok, version_string_or_error).
    """
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=10,
            shell=(sys.platform == "win32"),
        )
        version_str = result.stdout.strip().split("\n")[0] if result.stdout else "unknown"
        return True, version_str
    except FileNotFoundError:
        return False, f"{name} not found on PATH"
    except subprocess.TimeoutExpired:
        return False, f"{name} command timed out"
    except Exception as e:
        return False, str(e)


def _setup_validate_environment() -> dict[str, bool]:
    """Validate Python, Node.js, and npm availability."""
    print(_bold("  ② Checking environment…"))
    print()

    results: dict[str, bool] = {}

    # Python version
    py_ver = sys.version.split()[0]
    py_major, py_minor = sys.version_info[:2]
    if py_major >= 3 and py_minor >= 10:
        print(f"    {_green('✔')} Python {py_ver}")
        results["python"] = True
    else:
        print(f"    {_red('✘')} Python {py_ver} — requires 3.10+")
        results["python"] = False

    # Node.js
    ok, info = _check_command("node", ["node", "--version"])
    if ok:
        print(f"    {_green('✔')} Node.js {info}")
        results["node"] = True
    else:
        print(f"    {_yellow('⚠')} Node.js not found — frontend dashboard will be unavailable")
        print(f"      {_dim(info)}")
        results["node"] = False

    # npm
    ok, info = _check_command("npm", ["npm", "--version"])
    if ok:
        print(f"    {_green('✔')} npm {info}")
        results["npm"] = True
    else:
        print(f"    {_yellow('⚠')} npm not found — cannot install frontend dependencies")
        print(f"      {_dim(info)}")
        results["npm"] = False

    print()
    return results


# ── Step 3: Virtual Environment ─────────────────────────────────────────────

def _setup_venv(auto_yes: bool) -> bool:
    """Create a virtual environment if one doesn't exist."""
    print(_bold("  ③ Virtual environment…"))
    print()

    venv_dir = ROOT_DIR / ".venv"

    if venv_dir.exists() and VENV_PYTHON.exists():
        print(f"    {_green('✔')} Virtual environment already exists at .venv/")
        print()
        return True

    if venv_dir.exists() and not VENV_PYTHON.exists():
        print(f"    {_yellow('⚠')} .venv/ exists but Python executable is missing. Recreating…")
        shutil.rmtree(venv_dir, ignore_errors=True)

    print(f"    {_dim('→')} Creating virtual environment…")
    try:
        subprocess.run(
            [sys.executable, "-m", "venv", str(venv_dir)],
            check=True, capture_output=True, text=True,
        )
        print(f"    {_green('✔')} Virtual environment created at .venv/")
        # Update the global PYTHON to point at the fresh venv
        global PYTHON
        PYTHON = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable
        print()
        return True
    except subprocess.CalledProcessError as e:
        print(f"    {_red('✘')} Failed to create venv: {e.stderr.strip()}")
        print()
        return False


# ── Step 4: Python Dependencies ─────────────────────────────────────────────

def _setup_python_deps(auto_yes: bool) -> bool:
    """Install Python dependencies from requirements.txt."""
    print(_bold("  ④ Python dependencies…"))
    print()

    req_file = ROOT_DIR / "requirements.txt"
    if not req_file.exists():
        print(f"    {_yellow('⚠')} requirements.txt not found — skipping")
        print()
        return True

    pip_cmd = str(VENV_PIP) if VENV_PIP.exists() else f"{PYTHON} -m pip"
    if VENV_PIP.exists():
        cmd = [str(VENV_PIP), "install", "-r", str(req_file), "--quiet"]
    else:
        cmd = [PYTHON, "-m", "pip", "install", "-r", str(req_file), "--quiet"]

    print(f"    {_dim('→')} Installing packages from requirements.txt…")
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(ROOT_DIR))
        if result.returncode == 0:
            # Count packages
            lines = [l.strip() for l in req_file.read_text().splitlines() if l.strip() and not l.startswith("#")]
            print(f"    {_green('✔')} {len(lines)} packages installed successfully")
        else:
            print(f"    {_red('✘')} pip install failed:")
            for line in result.stderr.strip().split("\n")[-5:]:
                print(f"      {_dim(line)}")
            print()
            return False
    except Exception as e:
        print(f"    {_red('✘')} Error: {e}")
        print()
        return False

    print()
    return True


# ── Step 5: Node Dependencies ───────────────────────────────────────────────

def _setup_node_deps(env: dict[str, bool], auto_yes: bool) -> bool:
    """Install Node.js dependencies for the dashboard."""
    print(_bold("  ⑤ Frontend dependencies…"))
    print()

    if not env.get("node") or not env.get("npm"):
        print(f"    {_yellow('⚠')} Skipping — Node.js/npm not available")
        print(f"      {_dim('The backend will work fine; dashboard requires Node.js 18+')}")
        print()
        return True

    if not DASHBOARD_DIR.exists():
        print(f"    {_yellow('⚠')} dashboard/ directory not found — skipping")
        print()
        return True

    if (DASHBOARD_DIR / "node_modules").exists():
        print(f"    {_green('✔')} node_modules already installed")
        print()
        return True

    print(f"    {_dim('→')} Running npm install in dashboard/…")
    try:
        result = subprocess.run(
            ["npm", "install"], cwd=str(DASHBOARD_DIR),
            shell=True, capture_output=True, text=True,
        )
        if result.returncode == 0:
            print(f"    {_green('✔')} Frontend dependencies installed")
        else:
            print(f"    {_red('✘')} npm install failed:")
            for line in result.stderr.strip().split("\n")[-5:]:
                print(f"      {_dim(line)}")
            print()
            return False
    except Exception as e:
        print(f"    {_red('✘')} Error: {e}")
        print()
        return False

    print()
    return True


# ── Step 6: Interactive Simulation Configuration ────────────────────────────

def _setup_configure_simulation(auto_yes: bool) -> bool:
    """Interactive questionnaire to build/update simulation.yaml."""
    print(_bold("  ⑥ Simulation configuration…"))
    print()

    config_path = ROOT_DIR / "simulation.yaml"
    using_defaults = False

    if not auto_yes:
        if config_path.exists():
            print(f"    {_dim('Found existing simulation.yaml')}")
            if not _prompt_bool("    Reconfigure simulation settings?", default=False, auto_yes=False):
                print(f"    {_green('✔')} Keeping existing configuration")
                print()
                return True

        # Offer quick-defaults shortcut
        if _prompt_bool("    Use default configuration? (recommended for first time)", default=True, auto_yes=False):
            using_defaults = True
            auto_yes = True  # Treat rest of config as auto
    else:
        using_defaults = True

    if not using_defaults:
        print()
        print(f"    {_cyan('Configure your OS simulation parameters:')}")
        print(f"    {_dim('Press Enter to accept the default for each option.')}")

    # Backup existing config
    if config_path.exists():
        backup = config_path.with_suffix(".yaml.bak")
        shutil.copy2(config_path, backup)
        if not using_defaults:
            print(f"    {_dim(f'Backed up existing config to {backup.name}')}")

    # ── Gather choices ──
    sched_algo = _prompt("Scheduler algorithm", SCHEDULER_ALGORITHMS, "round_robin", auto_yes)
    time_quantum = _prompt_int("Time quantum (ticks)", 4, 1, 100, auto_yes)
    preemptive = _prompt_bool("Preemptive scheduling?", True, auto_yes)

    mem_algo = _prompt("Page replacement algorithm", PAGE_ALGORITHMS, "lru", auto_yes)
    total_frames = _prompt_int("Total memory frames", 64, 8, 1024, auto_yes)
    page_size_kb = _prompt_int("Page size (KB)", 4, 1, 64, auto_yes)
    tlb_size = _prompt_int("TLB size (entries)", 16, 4, 256, auto_yes)

    disk_algo = _prompt("Disk scheduling algorithm", DISK_ALGORITHMS, "c-scan", auto_yes)
    cylinders = _prompt_int("Disk cylinders", 200, 10, 10000, auto_yes)

    fs_type = _prompt("Filesystem type", FS_TYPES, "fat", auto_yes)

    recovery = _prompt("Deadlock recovery strategy", RECOVERY_STRATEGIES, "terminate_youngest", auto_yes)

    initial_load = _prompt_int("Initial process count", 5, 1, 50, auto_yes)

    # ── Write YAML ──
    yaml_content = f"""clock:
  auto_start: false
  max_ticks: 10000
  tick_rate_ms: 100
cpu:
  context_switch_cost: 2
  cores: 1
deadlock:
  detection_interval: 10
  recovery_strategy: {recovery}
disk:
  cylinders: {cylinders}
  initial_head: 53
  scheduling: {disk_algo}
  seek_time_per_track: 1
filesystem:
  block_size_kb: {page_size_kb}
  total_blocks: 512
  type: {fs_type}
logging:
  level: INFO
  log_path: logs/simulation.log
  log_to_file: true
memory:
  algorithm: {mem_algo}
  page_size_kb: {page_size_kb}
  swap_enabled: true
  tlb_size: {tlb_size}
  total_frames: {total_frames}
processes:
  auto_spawn: true
  initial_load: {initial_load}
  spawn_interval_ticks: 20
scheduler:
  aging_interval: 50
  algorithm: {sched_algo}
  preemptive: {"true" if preemptive else "false"}
  time_quantum: {time_quantum}
"""

    try:
        config_path.write_text(yaml_content)
        print()
        print(f"    {_green('✔')} simulation.yaml written")

        # Validate using our own config loader
        try:
            sys.path.insert(0, str(ROOT_DIR))
            from core.config import load_config
            cfg = load_config(str(config_path))
            errors = cfg.validate()
            if errors:
                print(f"    {_yellow('⚠')} Config validation warnings:")
                for err in errors:
                    print(f"      {_dim(err)}")
            else:
                print(f"    {_green('✔')} Configuration validated successfully")
        except Exception as e:
            print(f"    {_yellow('⚠')} Could not validate config: {e}")

    except Exception as e:
        print(f"    {_red('✘')} Failed to write config: {e}")
        print()
        return False

    print()
    return True


# ── Step 7: Health Check ────────────────────────────────────────────────────

def _setup_health_check(auto_yes: bool) -> bool:
    """Run a quick test suite to verify everything works."""
    print(_bold("  ⑦ Running health check…"))
    print()

    # Refresh PYTHON in case venv was just created
    python = str(VENV_PYTHON) if VENV_PYTHON.exists() else sys.executable

    cmd = [python, "-m", "pytest", "tests/", "-q", "--tb=line", "--no-header"]
    cmd_str = " ".join(cmd)
    print(f"    {_dim(f'$ {cmd_str}')}")
    print()

    try:
        result = subprocess.run(cmd, cwd=str(ROOT_DIR), capture_output=True, text=True, timeout=120)

        # Show last few lines of output (summary)
        output_lines = result.stdout.strip().split("\n") if result.stdout else []
        for line in output_lines[-6:]:
            print(f"    {line}")

        if result.returncode == 0:
            print()
            print(f"    {_green('✔')} All tests passed!")
        else:
            print()
            print(f"    {_yellow('⚠')} Some tests failed (exit code {result.returncode})")
            print(f"      {_dim('This is non-blocking — you can investigate later with: python sim_launcher.py test')}")
    except subprocess.TimeoutExpired:
        print(f"    {_yellow('⚠')} Tests timed out after 120s — skipping")
    except Exception as e:
        print(f"    {_yellow('⚠')} Could not run tests: {e}")

    print()
    return True


# ── Step 8: Summary ─────────────────────────────────────────────────────────

def _setup_summary(env: dict[str, bool]) -> None:
    """Print the final setup summary and quick-start guide."""
    width = 70
    print()
    print("─" * width)
    print(_bold(_green("  ✅  Setup complete!")))
    print("─" * width)
    print()
    print(_bold("  Quick-Start Guide"))
    print()
    print(f"    {_cyan('python sim_launcher.py start')}     Start backend + dashboard")
    print(f"    {_cyan('python sim_launcher.py backend')}   Start backend only")
    if env.get("node"):
        print(f"    {_cyan('python sim_launcher.py frontend')}  Start dashboard only")
    print(f"    {_cyan('python sim_launcher.py test')}      Run tests with coverage")
    print(f"    {_cyan('python sim_launcher.py docs')}      Serve documentation")
    print(f"    {_cyan('python sim_launcher.py check')}     Quick health check")
    print()
    print(f"  {_dim('URLs after starting:')}")
    print(f"    Backend API:  {_cyan('http://localhost:8000')}")
    print(f"    API Docs:     {_cyan('http://localhost:8000/docs')}")
    if env.get("node"):
        print(f"    Dashboard:    {_cyan('http://localhost:5173')}")
    print(f"    Docs:         {_cyan('http://localhost:8080')} {_dim('(when running docs)')}")
    print()
    print(f"  {_dim('To reconfigure: python sim_launcher.py setup --reset')}")
    print()


# ── Sentinel File Management ────────────────────────────────────────────────

def _is_setup_complete() -> bool:
    """Check if first-time setup has been completed."""
    if not SENTINEL_FILE.exists():
        return False
    try:
        data = json.loads(SENTINEL_FILE.read_text())
        return data.get("version", 0) >= SETUP_VERSION
    except (json.JSONDecodeError, KeyError):
        return False


def _mark_setup_complete() -> None:
    """Write the sentinel file to mark setup as done."""
    data = {
        "version": SETUP_VERSION,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": sys.platform,
    }
    SENTINEL_FILE.write_text(json.dumps(data, indent=2) + "\n")


# ── Main Setup Orchestrator ─────────────────────────────────────────────────

def cmd_setup(auto_yes: bool = False, reset: bool = False) -> int:
    """Run the first-time setup wizard."""
    if _is_setup_complete() and not reset:
        print()
        print(f"  {_green('✔')} Setup has already been completed.")
        print(f"    {_dim('To re-run setup: python sim_launcher.py setup --reset')}")
        print()
        return 0

    # ① Welcome
    _setup_welcome()

    # ② Environment
    env = _setup_validate_environment()
    if not env.get("python"):
        print(f"\n  {_red('✘')} Python 3.10+ is required. Please upgrade and try again.")
        return 1

    # ③ Virtual Environment
    venv_ok = _setup_venv(auto_yes)

    # ④ Python Dependencies
    if venv_ok:
        _setup_python_deps(auto_yes)

    # ⑤ Node Dependencies
    _setup_node_deps(env, auto_yes)

    # ⑥ Configuration
    _setup_configure_simulation(auto_yes)

    # ⑦ Health Check
    _setup_health_check(auto_yes)

    # Mark complete
    _mark_setup_complete()

    # ⑧ Summary
    _setup_summary(env)

    return 0


def _maybe_first_run_prompt() -> bool:
    """
    Check if this is a first run and prompt the user.
    Returns True if setup was run (caller should exit), False otherwise.
    """
    if _is_setup_complete():
        return False

    print()
    print(f"  {_magenta('●')} {_bold('First run detected!')} This project hasn\'t been set up yet.")
    print()

    try:
        if _prompt_confirm("  Run first-time setup? ", default=True):
            rc = cmd_setup(auto_yes=False, reset=False)
            sys.exit(rc)
    except (EOFError, KeyboardInterrupt):
        print(f"\n  {_dim('Skipped. Run setup later with:')} python sim_launcher.py setup")

    return False


# ═══════════════════════════════════════════════════════════════════════════════
#  EXISTING COMMANDS (unchanged)
# ═══════════════════════════════════════════════════════════════════════════════

def cmd_test(html: bool = False, full: bool = False) -> int:
    """Run pytest with coverage on core algorithm modules."""
    _banner("Running Unit Tests with Coverage")

    cov_args = []
    if full:
        for mod in ALL_MODULES:
            cov_args += [f"--cov={mod}"]
    else:
        for mod in CORE_MODULES:
            cov_args += [f"--cov={mod}"]

    report = ["--cov-report=term-missing"]
    if html:
        report.append("--cov-report=html:htmlcov")

    cmd = [PYTHON, "-m", "pytest", "tests/", "-v"] + cov_args + report
    print(f"$ {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))

    if html and result.returncode == 0:
        print(f"\n📊 HTML coverage report: {ROOT_DIR / 'htmlcov' / 'index.html'}")

    return result.returncode


def cmd_backend() -> subprocess.Popen:
    """Start the FastAPI backend server."""
    _banner("Starting Backend Server (FastAPI + Uvicorn)")

    main_py = ROOT_DIR / "api" / "main.py"
    if not main_py.exists():
        print(f"❌ {main_py} not found. Is this the right project root?")
        sys.exit(1)

    cmd = [PYTHON, "-m", "uvicorn", "api.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"]
    print(f"$ {' '.join(cmd)}")
    print("🌐 Backend: http://localhost:8000")
    print("📡 WebSocket: ws://localhost:8000/ws/realtime")
    print("📖 API Docs: http://localhost:8000/docs\n")

    proc = subprocess.Popen(cmd, cwd=str(ROOT_DIR))
    return proc


def cmd_frontend() -> subprocess.Popen:
    """Start the React dashboard dev server."""
    _banner("Starting Frontend Dashboard (React + Vite)")

    if not DASHBOARD_DIR.exists():
        print(f"❌ {DASHBOARD_DIR} not found.")
        sys.exit(1)

    # Check if node_modules exist
    if not (DASHBOARD_DIR / "node_modules").exists():
        print("📦 Installing frontend dependencies...")
        subprocess.run(["npm", "install"], cwd=str(DASHBOARD_DIR), shell=True, check=True)

    cmd = ["npm", "run", "dev"]
    print(f"$ {' '.join(cmd)} (in dashboard/)")
    print("🖥️  Dashboard: http://localhost:5173\n")

    proc = subprocess.Popen(cmd, cwd=str(DASHBOARD_DIR), shell=True)
    return proc


def cmd_check() -> int:
    """Quick health check: run tests only."""
    _banner("Health Check — Quick Test Run")

    cmd = [PYTHON, "-m", "pytest", "tests/", "-q", "--tb=short"]
    print(f"$ {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(ROOT_DIR))

    if result.returncode == 0:
        print("\n✅ All checks passed!")
    else:
        print("\n❌ Some checks failed.")

    return result.returncode


def cmd_start() -> None:
    """Start both backend and frontend together."""
    _banner("Starting Full Stack (Backend + Frontend)")

    backend = cmd_backend()
    time.sleep(2)  # Wait for backend to initialize
    frontend = cmd_frontend()

    print("\n" + "=" * 70)
    print("  🚀 OS Simulator is running!")
    print("     Backend:   http://localhost:8000")
    print("     Dashboard: http://localhost:5173")
    print("     API Docs:  http://localhost:8000/docs")
    print("     Press Ctrl+C to stop all services")
    print("=" * 70 + "\n")

    try:
        # Wait on whichever exits first; if either crashes, we still clean up both
        while backend.poll() is None and frontend.poll() is None:
            time.sleep(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        print("\n\n🛑 Shutting down...")
        for proc in (backend, frontend):
            if proc.poll() is None:
                proc.terminate()
        for proc in (backend, frontend):
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        print("✅ All services stopped.")


def cmd_docs(build: bool = False) -> subprocess.Popen | None:
    """Serve or build the MkDocs documentation site."""
    mkdocs_cfg = ROOT_DIR / "mkdocs.yml"
    if not mkdocs_cfg.exists():
        print(f"❌ {mkdocs_cfg} not found. Cannot serve docs.")
        sys.exit(1)

    if build:
        _banner("Building Documentation Site (MkDocs)")
        cmd = [PYTHON, "-m", "mkdocs", "build", "--clean"]
        print(f"$ {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=str(ROOT_DIR))
        if result.returncode == 0:
            print(f"\n📄 Static site built: {ROOT_DIR / 'site' / 'index.html'}")
        return None
    else:
        _banner("Serving Documentation Site (MkDocs)")
        cmd = [PYTHON, "-m", "mkdocs", "serve", "--dev-addr", "127.0.0.1:8080"]
        print(f"$ {' '.join(cmd)}")
        print("📖 Docs: http://localhost:8080")
        print("   Live-reload enabled — edits to docs/ appear instantly.\n")
        proc = subprocess.Popen(cmd, cwd=str(ROOT_DIR))
        return proc


def cmd_all() -> None:
    """Run tests first, then start the full stack if tests pass."""
    rc = cmd_test()
    if rc != 0:
        print("\n❌ Tests failed. Fix issues before starting servers.")
        sys.exit(rc)

    print("\n✅ All tests passed! Starting servers...\n")
    cmd_start()


# ── CLI Entry Point ───────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="OS Simulation & Experimentation — Project Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python sim_launcher.py setup             First-time setup wizard
  python sim_launcher.py setup --yes       Accept all defaults (non-interactive)
  python sim_launcher.py setup --reset     Re-run setup from scratch
  python sim_launcher.py test              Run tests with core module coverage
  python sim_launcher.py test --html       Generate HTML coverage report
  python sim_launcher.py test --full       Full project coverage (all modules)
  python sim_launcher.py start             Launch backend + frontend
  python sim_launcher.py docs              Serve docs site with live-reload
  python sim_launcher.py docs --build      Build static docs into site/
  python sim_launcher.py all              Test first, then launch if passing
  python sim_launcher.py check             Quick pass/fail test check
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # setup
    setup_parser = subparsers.add_parser("setup", help="Run first-time setup wizard")
    setup_parser.add_argument("--yes", "-y", action="store_true", help="Accept all defaults (non-interactive)")
    setup_parser.add_argument("--reset", action="store_true", help="Re-run setup even if already completed")

    # test
    test_parser = subparsers.add_parser("test", help="Run unit tests with coverage")
    test_parser.add_argument("--html", action="store_true", help="Generate HTML coverage report")
    test_parser.add_argument("--full", action="store_true", help="Cover all modules, not just core algorithms")

    # backend
    subparsers.add_parser("backend", help="Start FastAPI backend server")

    # frontend
    subparsers.add_parser("frontend", help="Start React dashboard dev server")

    # start
    subparsers.add_parser("start", help="Start backend + frontend together")

    # docs
    docs_parser = subparsers.add_parser("docs", help="Serve the MkDocs documentation site")
    docs_parser.add_argument("--build", action="store_true", help="Build static site into site/ instead of serving")

    # check
    subparsers.add_parser("check", help="Quick health check (tests only)")

    # all
    subparsers.add_parser("all", help="Run tests, then start servers")

    args = parser.parse_args()

    # No command given — check for first-run, then show help
    if args.command is None:
        _maybe_first_run_prompt()
        parser.print_help()
        sys.exit(0)

    if args.command == "setup":
        sys.exit(cmd_setup(auto_yes=args.yes, reset=args.reset))
    elif args.command == "test":
        sys.exit(cmd_test(html=args.html, full=args.full))
    elif args.command == "backend":
        proc = cmd_backend()
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
    elif args.command == "frontend":
        proc = cmd_frontend()
        try:
            proc.wait()
        except KeyboardInterrupt:
            proc.terminate()
    elif args.command == "start":
        cmd_start()
    elif args.command == "docs":
        proc = cmd_docs(build=args.build)
        if proc is not None:
            try:
                proc.wait()
            except KeyboardInterrupt:
                proc.terminate()
    elif args.command == "check":
        sys.exit(cmd_check())
    elif args.command == "all":
        cmd_all()


if __name__ == "__main__":
    main()
