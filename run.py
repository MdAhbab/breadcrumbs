#!/usr/bin/env python3
"""
Start Breadcrumbs.

    python3 run.py

One command, everything up, one Ctrl-C to stop it all.

A note on what "everything" means, because it is fewer moving parts than it
looks. There are two processes, not four:

    the API      FastAPI on :8000. The permissioned ledger and the detector
                 both live *inside* it. The chain is built in memory when the
                 process starts, the chaincode runs as ordinary function calls,
                 and the model trains during the same startup. There is no
                 separate blockchain node to launch and no model server to
                 point at — that is a property of the design, not a shortcut,
                 and it is why the whole thing fits on a free CPU tier.

    the web app  Vite on :5173. It holds no data of its own. Every figure it
                 shows is a response from the API.

The ports are fixed on purpose. The web app defaults to http://localhost:8000
and the API's CORS list names http://localhost:5173, so moving one without the
other breaks the pair. Use --api-port / --web-port to move both together.

Stdlib only, so it runs with whatever `python3` you have. It finds the project's
own virtual environment for the API.

Not to be confused with `Breadcrumbs Project/model/run.py`, which is the research
entry point: training, evaluation, benchmarks and the ledger demo. This file
starts the product; that one reproduces the paper. Run it as a module:

    cd "Breadcrumbs Project" && python -m model.run --help
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROJECT = ROOT / "Breadcrumbs Project"
BACKEND = PROJECT / "backend"
FRONTEND = PROJECT / "frontend"
VENV_PYTHON = PROJECT / ".venv" / "bin" / "python"
CORPUS = PROJECT / "data" / "corpus"

# Colours, but only when a person is watching. Piping this into a file or a log
# collector should not fill it with escape codes.
TTY = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def paint(text: str, code: str) -> str:
    return f"\033[{code}m{text}\033[0m" if TTY else text


DIM = "2"
BOLD = "1"
BRASS = "33"
GREEN = "32"
RED = "31"
BLUE = "36"


def say(message: str = "") -> None:
    print(message, flush=True)


def fail(message: str, fix: str = "") -> None:
    say()
    say(paint("  ✕ " + message, RED))
    if fix:
        say(paint("    " + fix, DIM))
    say()
    sys.exit(1)


# --------------------------------------------------------------------------
# checks
# --------------------------------------------------------------------------
def preflight(want_frontend: bool) -> None:
    """
    Fail early and say exactly what to type.

    Every check here failed on somebody at some point. A missing virtual
    environment and a missing corpus produce completely different symptoms
    several minutes apart, so both are caught before anything starts.
    """
    if not PROJECT.is_dir():
        fail(
            f"cannot find {PROJECT.name}/ next to this script",
            "run.py belongs in the repository root, beside 'Breadcrumbs Project'.",
        )

    if not VENV_PYTHON.is_file():
        fail(
            "no virtual environment at Breadcrumbs Project/.venv",
            "python3.11 -m venv '.venv' && .venv/bin/pip install -r backend/requirements.txt"
            "\n    (run both from inside 'Breadcrumbs Project')",
        )

    probe = subprocess.run(
        [str(VENV_PYTHON), "-c", "import fastapi, uvicorn, sqlalchemy, jose, torch"],
        capture_output=True, text=True,
    )
    if probe.returncode != 0:
        missing = probe.stderr.strip().splitlines()[-1] if probe.stderr else "a dependency"
        fail(
            f"the virtual environment is incomplete — {missing}",
            "cd 'Breadcrumbs Project' && .venv/bin/pip install -r backend/requirements.txt",
        )

    if want_frontend:
        if shutil.which("npm") is None:
            fail("npm is not on PATH", "install Node 18 or newer, then run again.")
        if not (FRONTEND / "node_modules").is_dir():
            say(paint("  installing web dependencies (first run only)…", DIM))
            result = subprocess.run(["npm", "install"], cwd=FRONTEND)
            if result.returncode != 0:
                fail("npm install failed", "run it yourself in Breadcrumbs Project/frontend")


def ensure_corpus(auto: bool) -> bool:
    """
    Make sure there are documents to build a world from.

    The corpus is generated, not committed — it is reproducible from seed 7, so
    keeping 15 MB of it in git would be storing something a command can rebuild
    in five seconds. Without it the API still starts and still tells the truth:
    it serves an empty ledger and says why. That is better than inventing
    documents, but it is not what anyone wants to demonstrate.
    """
    if (CORPUS / "manifest.json").is_file():
        return True

    say(paint("  no corpus at Breadcrumbs Project/data/corpus", BRASS))
    if not auto:
        say(paint("    the API will start and serve an empty ledger.", DIM))
        say(paint("    generate it with: python -m data.cli --seed 7 --scale small "
                  "--out data/corpus", DIM))
        return False

    say(paint("    generating it (about 5 seconds, seed 7)…", DIM))
    result = subprocess.run(
        [str(VENV_PYTHON), "-m", "data.cli", "--seed", "7", "--scale", "small",
         "--out", "data/corpus"],
        cwd=PROJECT,
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        say(paint("    could not generate it:", RED))
        say(paint("    " + (result.stderr.strip().splitlines() or ["unknown error"])[-1], DIM))
        return False
    say(paint("    done.", GREEN))
    return True


# --------------------------------------------------------------------------
# port and process management
# --------------------------------------------------------------------------
def is_port_in_use(port: int) -> bool:
    """Check if a TCP port is currently open and accepting connections on localhost."""
    for family, host in ((socket.AF_INET, "127.0.0.1"), (socket.AF_INET6, "::1")):
        try:
            with socket.socket(family, socket.SOCK_STREAM) as s:
                s.settimeout(0.3)
                if s.connect_ex((host, port)) == 0:
                    return True
        except OSError:
            pass
    return False


def get_pids_listening_on(port: int) -> list[int]:
    """Find PIDs listening on a specific TCP port using lsof."""
    try:
        res = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            capture_output=True, text=True, check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            pids = []
            for line in res.stdout.strip().splitlines():
                line = line.strip()
                if line.isdigit():
                    pid = int(line)
                    if pid != os.getpid():
                        pids.append(pid)
            return pids
    except Exception:
        pass
    return []


def kill_process_tree(pid: int, sig: int) -> None:
    """Kill a process, its parent supervisor if running run.py, and its process group."""
    # If the parent is an old supervisor running run.py, terminate it as well
    try:
        res = subprocess.run(
            ["ps", "-o", "ppid=,command=", "-p", str(pid)],
            capture_output=True, text=True, check=False,
        )
        if res.returncode == 0 and res.stdout.strip():
            parts = res.stdout.strip().split(None, 1)
            if len(parts) >= 1 and parts[0].isdigit():
                ppid = int(parts[0])
                cmd = parts[1] if len(parts) > 1 else ""
                if ppid > 1 and ppid != os.getpid() and "run.py" in cmd:
                    try:
                        os.kill(ppid, sig)
                    except (ProcessLookupError, PermissionError, OSError):
                        pass
    except Exception:
        pass

    # Terminate process group if separate session
    try:
        pgid = os.getpgid(pid)
        my_pgid = os.getpgid(os.getpid())
        if pgid not in (0, 1, my_pgid):
            os.killpg(pgid, sig)
    except (ProcessLookupError, PermissionError, OSError):
        pass

    # Terminate the target process itself
    try:
        os.kill(pid, sig)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def free_port(port: int, label: str = "") -> None:
    """
    Ensure a port is free before starting a service.
    If another server is already running, terminate it cleanly.
    """
    pids = get_pids_listening_on(port)
    if not pids and not is_port_in_use(port):
        return

    name = f" ({label})" if label else ""
    pid_str = f"PID {', '.join(map(str, pids))}" if pids else "unknown PID"
    say(paint(f"  stopping existing server on port {port}{name} [{pid_str}]…", BRASS))

    for pid in pids:
        kill_process_tree(pid, signal.SIGTERM)

    # Give processes up to 3 seconds to exit gracefully
    deadline = time.time() + 3.0
    while time.time() < deadline:
        active = get_pids_listening_on(port)
        if not active and not is_port_in_use(port):
            say(paint(f"  ✓ freed port {port}", GREEN))
            return
        time.sleep(0.2)

    # Force kill if still holding the port
    active = get_pids_listening_on(port)
    for pid in active:
        kill_process_tree(pid, signal.SIGKILL)

    time.sleep(0.3)
    if not is_port_in_use(port) and not get_pids_listening_on(port):
        say(paint(f"  ✓ freed port {port}", GREEN))
    else:
        say(paint(f"  ! warning: port {port} may still be in use", RED))


# --------------------------------------------------------------------------
# processes
# --------------------------------------------------------------------------
class Service:
    """One child process, with its output labelled and its shutdown handled."""

    def __init__(self, name: str, colour: str, command: list[str], cwd: Path,
                 env: dict[str, str] | None = None):
        self.name = name
        self.colour = colour
        self.command = command
        self.cwd = cwd
        self.env = {**os.environ, **(env or {})}
        self.process: subprocess.Popen[str] | None = None

    def start(self) -> None:
        self.process = subprocess.Popen(
            self.command,
            cwd=self.cwd,
            env=self.env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            # Its own process group, so Ctrl-C reaches this script first and the
            # children are stopped deliberately rather than racing it.
            start_new_session=True,
        )
        threading.Thread(target=self._pump, daemon=True).start()

    def _pump(self) -> None:
        assert self.process and self.process.stdout
        tag = paint(f"{self.name:>4} ", self.colour)
        for line in self.process.stdout:
            line = line.rstrip()
            if line:
                print(tag + paint("│ ", DIM) + line, flush=True)

    @property
    def alive(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def stop(self) -> None:
        if not self.alive:
            return
        assert self.process
        try:
            os.killpg(os.getpgid(self.process.pid), signal.SIGTERM)
        except (ProcessLookupError, PermissionError):
            self.process.terminate()
        try:
            self.process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(os.getpgid(self.process.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                self.process.kill()


def wait_for_world(api_port: int, service: Service, timeout: float = 240.0) -> dict | None:
    """
    Wait for the ledger to be built, and report progress while it is.

    The API answers from the first moment and reports its own build state, so
    this polls rather than guessing. That is worth doing here: a cold start is
    around forty seconds of genuine work — several hundred documents committed,
    a trusted-dealer ceremony, three accumulator epochs, two verifiable-delay
    proofs and four gate decisions — and forty silent seconds looks like a hang.
    """
    url = f"http://127.0.0.1:{api_port}/api/health"
    deadline = time.time() + timeout
    spinner = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
    frame = 0
    last_detail = ""

    while time.time() < deadline:
        if not service.alive:
            return None
        try:
            with urllib.request.urlopen(url, timeout=4) as response:
                body = json.load(response)
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            body = None

        if body:
            world = body.get("world", {})
            state = world.get("state")
            if state == "ready":
                if TTY:
                    print("\r" + " " * 78 + "\r", end="", flush=True)
                return body
            if state == "failed":
                if TTY:
                    print("\r" + " " * 78 + "\r", end="", flush=True)
                say(paint("  ✕ the world could not be built:", RED))
                say(paint("    " + str(world.get("error")), DIM))
                return None
            elapsed = world.get("elapsed_seconds", 0)
            typical = world.get("typical_seconds", 45)
            left = max(0, int(typical - elapsed))
            last_detail = f"building the ledger — about {left}s left"

        if TTY:
            print(
                f"\r  {paint(spinner[frame % len(spinner)], BRASS)} "
                f"{paint(last_detail or 'starting the API…', DIM)}   ",
                end="", flush=True,
            )
        frame += 1
        time.sleep(0.4 if TTY else 2.0)

    if TTY:
        print("\r" + " " * 78 + "\r", end="", flush=True)
    say(paint("  ✕ the API did not finish building in time", RED))
    return None


def wait_for_web(web_port: int, service: Service, timeout: float = 90.0) -> bool:
    """
    Wait for Vite to answer, asking for it by the same name the browser uses.

    This asked for 127.0.0.1 once, and that is the one address Vite is not on.
    Told to serve "localhost", Node resolves the name and binds the single
    address it gets back — on any recent macOS that is ::1, so the dev server
    listens on [::1]:5173 and nothing at all is on 127.0.0.1. The browser
    resolves the same name and is served perfectly; this check was refused every
    time, ran out its ninety seconds, and took the API down with it. The app
    died in the middle of a working session because the supervisor could not
    find something that was never lost. Ask for the name and the resolver hands
    over both families, which http.client then tries in turn.
    """
    deadline = time.time() + timeout
    url = f"http://localhost:{web_port}/"
    while time.time() < deadline:
        if not service.alive:
            return False
        try:
            with urllib.request.urlopen(url, timeout=3):
                return True
        except urllib.error.HTTPError:
            # It replied. A dev server answering 404 is still a dev server.
            return True
        except (urllib.error.URLError, OSError):
            time.sleep(0.5)
    return False


# --------------------------------------------------------------------------
# the summary
# --------------------------------------------------------------------------
def report(health: dict, api_port: int, web_port: int, with_web: bool) -> None:
    world = health.get("world", {})
    result = world.get("result") or {}
    provenance = health.get("provenance", {})
    channels = health.get("channels", [])

    say()
    say(paint("  Breadcrumbs is up.", BOLD))
    say()

    if with_web:
        say(f"    {paint('open this', BOLD)}   http://localhost:{web_port}")
    say(f"    {paint('the API', DIM)}     http://localhost:{api_port}/api/health")
    say(f"    {paint('API docs', DIM)}    http://localhost:{api_port}/docs")
    say()

    if provenance.get("corpus") == "present":
        say(paint("    the world", DIM))
        say(f"      {result.get('records', '?')} documents from the corpus, "
            f"seed {provenance.get('seed')}")
        say(f"      {result.get('seals', '?')} sealed periods · {result.get('anchor', '')}")
        for channel in channels:
            mark = paint("✓", GREEN) if channel.get("integrity_ok") else paint("✕", RED)
            say(f"      {mark} {channel['channel']}: {channel['height']} blocks")
        excluded = provenance.get("excluded_by_schema") or 0
        if excluded:
            say(paint(f"      {excluded} corpus documents were refused by the "
                      "chaincode schema", DIM))
    else:
        say(paint("    the ledger is empty — there is no corpus on disk", BRASS))
        say(paint("      python3 run.py --generate-corpus", DIM))

    say()
    say(paint("    sign in as anyone. no password is asked for.", DIM))
    say(paint("      factory · buyer · auditor · consortium · regulator", DIM))
    say()
    say(paint("    Ctrl-C stops everything.", DIM))
    say()


# --------------------------------------------------------------------------
def main() -> int:
    parser = argparse.ArgumentParser(
        description="Start the Breadcrumbs API and web app together.",
    )
    parser.add_argument("--api-port", type=int, default=8000)
    parser.add_argument("--web-port", type=int, default=5173)
    parser.add_argument("--no-frontend", action="store_true",
                        help="run the API alone")
    parser.add_argument("--generate-corpus", action="store_true",
                        help="build data/corpus first if it is missing")
    parser.add_argument("--reload", action="store_true",
                        help="restart the API when its source changes. Costs a "
                             "full world rebuild on every save.")
    args = parser.parse_args()

    with_web = not args.no_frontend

    say()
    say(paint("  Breadcrumbs", BOLD) + paint("  ·  starting", DIM))
    say()

    preflight(with_web)
    ensure_corpus(args.generate_corpus)

    # Stop any previous servers holding the ports
    free_port(args.api_port, "API")
    if with_web:
        free_port(args.web_port, "web")

    api_command = [
        str(VENV_PYTHON), "-m", "uvicorn", "app.main:app",
        "--host", "127.0.0.1", "--port", str(args.api_port),
    ]
    if args.reload:
        api_command.append("--reload")

    # The API only accepts browser requests from origins on its CORS list, and
    # that list is a setting rather than a wildcard. Passing the web origin in
    # here is what makes --web-port work: without it, moving the web app to
    # another port produced a page that loaded and then failed every fetch with
    # a CORS error, which looks like a broken API rather than a wrong flag.
    web_origin = f"http://localhost:{args.web_port}"
    api_env = {
        "BREADCRUMBS_CORS_ORIGINS": json.dumps(
            [web_origin, f"http://127.0.0.1:{args.web_port}"]
        )
    }

    services: list[Service] = [
        Service("api", BRASS, api_command, BACKEND, api_env)
    ]
    if with_web:
        services.append(
            Service(
                "web", BLUE,
                ["npm", "run", "dev", "--", "--port", str(args.web_port), "--strictPort"],
                FRONTEND,
                # The web app reads this at build time; setting it here keeps the
                # two ports together when either is moved.
                {"VITE_API_URL": f"http://localhost:{args.api_port}"},
            )
        )

    stopping = threading.Event()

    def shutdown(*_: object) -> None:
        if stopping.is_set():
            return
        stopping.set()
        say()
        say(paint("  stopping…", DIM))
        for service in reversed(services):
            service.stop()
        say(paint("  stopped.", DIM))
        say()

    signal.signal(signal.SIGINT, lambda *a: (shutdown(), sys.exit(0)))
    signal.signal(signal.SIGTERM, lambda *a: (shutdown(), sys.exit(0)))

    for service in services:
        service.start()

    api = services[0]
    health = wait_for_world(args.api_port, api)
    if health is None:
        shutdown()
        return 1

    if with_web and not wait_for_web(args.web_port, services[1], timeout=90):
        if services[1].alive:
            # The process is still up, so this is the check failing rather than
            # the app. Never stop a running product over an unanswered probe —
            # that is what made a healthy session end by itself.
            say(paint("  ! the web app has not answered yet, but it is still "
                      "running", BRASS))
            say(paint(f"    try http://localhost:{args.web_port} — and see the "
                      "'web' lines above if it is blank", DIM))
        else:
            say(paint("  ✕ the web app did not come up — see the 'web' lines "
                      "above", RED))
            shutdown()
            return 1

    report(health, args.api_port, args.web_port, with_web)

    # Hold the terminal open and mind the children. If either one dies on its
    # own, take the other down rather than leaving half a product running.
    try:
        while not stopping.is_set():
            for service in services:
                if not service.alive:
                    say()
                    say(paint(f"  ✕ {service.name} exited", RED))
                    shutdown()
                    return 1
            time.sleep(0.6)
    except KeyboardInterrupt:
        shutdown()
    return 0


if __name__ == "__main__":
    sys.exit(main())
