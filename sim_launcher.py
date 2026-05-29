#!/usr/bin/env python3
"""
sim_launcher.py — OS Simulation Project Management CLI.

Unified command-line interface for testing, serving, and launching
the OS Simulation & Experimentation environment.

Usage:
    python sim_launcher.py test          Run all unit tests with coverage report
    python sim_launcher.py test --html   Run tests and generate HTML coverage report
    python sim_launcher.py backend       Start the FastAPI backend server
    python sim_launcher.py frontend      Start the React dashboard dev server
    python sim_launcher.py start         Start both backend and frontend together
    python sim_launcher.py docs          Serve the MkDocs documentation site
    python sim_launcher.py docs --build  Build static docs into site/
    python sim_launcher.py check         Quick health check (tests + lint)
    python sim_launcher.py all           Run tests, then start backend + frontend
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
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
# Cross-platform venv detection: Windows uses Scripts/, Linux/macOS uses bin/
if sys.platform == "win32":
    VENV_PYTHON = ROOT_DIR / ".venv" / "Scripts" / "python.exe"
else:
    VENV_PYTHON = ROOT_DIR / ".venv" / "bin" / "python"

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


def _banner(title: str) -> None:
    """Print a visible section banner."""
    width = 70
    print()
    print("=" * width)
    print(f"  {title}")
    print("=" * width)
    print()


# ── Commands ──────────────────────────────────────────────────────────────────

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
  python sim_launcher.py test            Run tests with core module coverage
  python sim_launcher.py test --html     Generate HTML coverage report
  python sim_launcher.py test --full     Full project coverage (all modules)
  python sim_launcher.py start           Launch backend + frontend
  python sim_launcher.py docs            Serve docs site with live-reload
  python sim_launcher.py docs --build    Build static docs into site/
  python sim_launcher.py all             Test first, then launch if passing
  python sim_launcher.py check           Quick pass/fail test check
        """,
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

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

    if args.command is None:
        parser.print_help()
        sys.exit(0)

    if args.command == "test":
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
