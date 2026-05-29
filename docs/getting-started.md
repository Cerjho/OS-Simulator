# Getting Started

This guide will help you set up the OS Simulator and start running your first simulation.

## Prerequisites

*   **Python 3.11+** — [Download Python](https://www.python.org/downloads/)
*   **Node.js 18+** and **npm** — [Download Node.js](https://nodejs.org/)
*   **Git** — [Download Git](https://git-scm.com/)

## Installation

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd os-sim
    ```

2.  **Set up the Python virtual environment and install dependencies:**

    === "Windows (PowerShell)"

        ```powershell
        python -m venv .venv
        .venv\Scripts\activate
        pip install -r requirements.txt
        ```

    === "Linux / macOS"

        ```bash
        python3 -m venv .venv
        source .venv/bin/activate
        pip install -r requirements.txt
        ```

3.  **Install the React frontend dependencies:**
    ```bash
    cd dashboard
    npm install
    cd ..
    ```

---

## Launching the System

The project includes a unified CLI launcher — **`sim_launcher.py`** — that manages the backend, frontend, documentation site, testing, and health checks from a single entry point.

### Recommended: Launch Everything with One Command

```bash
python sim_launcher.py start
```

This single command:

1.  Starts the **FastAPI backend** on `http://localhost:8000`
2.  Waits for the backend to initialize (≈ 2 seconds)
3.  Starts the **React dashboard** dev server on `http://localhost:5173`
4.  Prints all service URLs once both are running
5.  Press **Ctrl+C** to gracefully shut down both services

After running `start`, open your browser to **[http://localhost:5173](http://localhost:5173)** to access the OS Simulator dashboard.

### Run Tests First, Then Launch

If you want to verify everything is working before launching:

```bash
python sim_launcher.py all
```

This runs the full test suite first. If all tests pass, it automatically starts the backend and frontend. If any test fails, it stops and reports the failures.

---

## All CLI Commands

| Command | Description |
|---------|-------------|
| `python sim_launcher.py start` | Start backend + frontend together |
| `python sim_launcher.py all` | Run tests first, then start servers (only if tests pass) |
| `python sim_launcher.py backend` | Start only the FastAPI backend server |
| `python sim_launcher.py frontend` | Start only the React dashboard dev server |
| `python sim_launcher.py docs` | Serve the MkDocs documentation site with live-reload |
| `python sim_launcher.py docs --build` | Build a static documentation site into `site/` |
| `python sim_launcher.py test` | Run all unit tests with coverage report |
| `python sim_launcher.py test --html` | Run tests and generate an HTML coverage report in `htmlcov/` |
| `python sim_launcher.py test --full` | Run tests with full project coverage (all modules, not just core) |
| `python sim_launcher.py check` | Quick health check — fast pass/fail test run |

Run `python sim_launcher.py --help` for the built-in help text.

---

## Manual Launch (Alternative)

If you prefer to start the services individually in separate terminals:

1.  **Start the Backend:**

    === "Windows (PowerShell)"

        ```powershell
        .venv\Scripts\activate
        uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
        ```

    === "Linux / macOS"

        ```bash
        source .venv/bin/activate
        uvicorn api.main:app --host 127.0.0.1 --port 8000 --reload
        ```

2.  **Start the Frontend** (in a second terminal):
    ```bash
    cd dashboard
    npm run dev
    ```

3.  **Open the Dashboard:**
    Navigate to [http://localhost:5173](http://localhost:5173) in your web browser.

---

## Documentation Site

The project includes a full MkDocs Material documentation site covering architecture, concepts, and user guides.

### Serve locally with live-reload

```bash
python sim_launcher.py docs
```

This starts a local docs server at **[http://localhost:8080](http://localhost:8080)** with live-reload — any edits you make to files in `docs/` are reflected instantly in the browser.

### Build a static site

To generate a static HTML site (e.g., for deployment):

```bash
python sim_launcher.py docs --build
```

The output is written to `site/`. Open `site/index.html` to preview it offline.

---

## Service Endpoints

Once the system is running, these endpoints are available:

| Service | URL | Description |
|---------|-----|-------------|
| Dashboard | [http://localhost:5173](http://localhost:5173) | React-based real-time UI |
| API Docs | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger/OpenAPI documentation |
| Documentation Site | [http://localhost:8080](http://localhost:8080) | MkDocs project documentation (when `docs` command is running) |
| WebSocket | `ws://localhost:8000/ws/realtime` | Real-time simulation state push |
| Backend API | [http://localhost:8000](http://localhost:8000) | FastAPI REST endpoints |

---

## Quick Actions

Once the dashboard is open:

*   **Start/Stop:** Use the control panel to start, pause, or stop the simulation clock.
*   **Change Algorithm:** Go to the Configuration tab to switch between scheduling algorithms (e.g., FCFS to Round Robin) or memory algorithms on the fly.
*   **View Logs:** Check the terminal running the backend for detailed event logs, or inspect the Gantt chart and memory maps in the UI.

For more details on interacting with the UI, see the [Dashboard Guide](user-guide/dashboard.md).

---

## Troubleshooting

### `ModuleNotFoundError` when running the backend

Make sure your virtual environment is activated. On Windows: `.venv\Scripts\activate`. On Linux/macOS: `source .venv/bin/activate`.

### Frontend shows a blank page or connection error

Ensure the backend is running first. The dashboard connects to `localhost:8000` via WebSocket — if the backend is not up, the UI cannot fetch simulation state.

### Port already in use

If port `8000` or `5173` is already occupied, stop the conflicting process or change the port:

*   **Backend:** `uvicorn api.main:app --port 8001`
*   **Frontend:** Edit `dashboard/vite.config.js` to set a different dev server port.

### `npm install` fails in the dashboard directory

Ensure you have Node.js 18+ installed (`node --version`). Delete `dashboard/node_modules` and `dashboard/package-lock.json`, then retry `npm install`.
