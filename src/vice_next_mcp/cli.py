"""Command line entry point for reproducible VICE experiment batches."""

from __future__ import annotations
import argparse, asyncio, argparse, json, os, signal, subprocess, threading, sys
from pathlib import Path
from .batch import BatchRunner
from .live_mcp import LiveMcpRuntime
from .supervisor import Supervisor


def _cases(path: Path) -> list[dict]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(value, dict):
        value = value.get("cases", [value])
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
        raise ValueError("cases JSON must be an array of objects (or {cases:[...]})")
    return value


def batch_main(ns: argparse.Namespace) -> int:
    cases = _cases(Path(ns.cases))
    stop = threading.Event()

    def interrupt(*_):
        stop.set()

    signal.signal(signal.SIGINT, interrupt)

    def execute(case, artifact, port):
        artifact.joinpath("case.json").write_text(
            json.dumps(case, indent=2, sort_keys=True), encoding="utf-8"
        )
        command = case.get("command") or ns.command
        if not command:
            return {"mode": "managed", "port": port}
        if isinstance(command, str):
            shell = True
            argv = command
        else:
            shell = False
            argv = [str(x) for x in command]
        env = os.environ.copy()
        env.update({"VICE_MCP_PORT": str(port), "VICE_MCP_ARTIFACT_DIR": str(artifact)})
        proc = subprocess.Popen(
            argv,
            cwd=case.get("cwd"),
            env=env,
            shell=shell,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        try:
            stdout, stderr = proc.communicate(timeout=ns.timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            raise RuntimeError("command timed out")
        if stop.is_set() and proc.poll() is None:
            proc.terminate()
        artifact.joinpath("stdout.log").write_text(stdout or "", encoding="utf-8")
        artifact.joinpath("stderr.log").write_text(stderr or "", encoding="utf-8")
        if proc.returncode:
            raise RuntimeError(f"command exited {proc.returncode}")
        return {"mode": "command", "returncode": proc.returncode, "port": port}

    result = BatchRunner(ns.artifact_root, workers=ns.workers, base_port=ns.base_port).run(
        cases, execute, fail_fast=ns.fail_fast, cancel=stop
    )
    out = json.dumps(result, indent=2, sort_keys=True)
    print(out)
    return 0 if all(x["status"] == "passed" for x in result["results"]) else 1


def main(argv=None):
    p = argparse.ArgumentParser(prog="vice-next")
    sub = p.add_subparsers(dest="subcommand", required=True)
    b = sub.add_parser("batch", help="run isolated VICE experiment cases")
    b.add_argument("--cases", required=True, help="JSON case matrix")
    b.add_argument("--artifact-root", default="build/vice-next-runs")
    b.add_argument("--workers", type=int, default=int(os.getenv("VICE_MCP_WORKERS", "1")))
    b.add_argument(
        "--base-port", type=int, default=int(os.getenv("VICE_MCP_BASE_PORT", "0")) or None
    )
    b.add_argument("--command", help="command template run for cases without command")
    b.add_argument("--timeout", type=float, default=3600)
    b.add_argument("--fail-fast", action="store_true")
    b.set_defaults(func=batch_main)
    m = sub.add_parser("mcp-stdio", help="serve one supervised VICE instance over JSON-RPC stdio")
    m.add_argument("--executable", required=True)
    m.add_argument(
        "--machine", choices=("x64sc", "x128", "xvic", "xplus4", "xpet"), default="x64sc"
    )
    m.add_argument("--artifact-root", default="build/vice-next-mcp")

    def stdio(ns):
        async def serve():
            Path(ns.artifact_root).mkdir(parents=True, exist_ok=True)
            supervisor = Supervisor(ns.executable, workdir=ns.artifact_root)
            instance = supervisor.create(ns.machine)
            lease = supervisor.lease(instance.id)
            runtime = LiveMcpRuntime(supervisor)
            print(
                json.dumps(
                    {
                        "event": "instance_ready",
                        "instance_id": instance.id,
                        "generation": instance.generation,
                        "lease_token": lease.token,
                        "machine": ns.machine,
                    }
                ),
                flush=True,
            )
            try:
                for line in sys.stdin:
                    if not line.strip():
                        continue
                    response = await runtime.handle(json.loads(line))
                    if response is not None:
                        print(json.dumps(response, default=str), flush=True)
            finally:
                lease.release()
                supervisor.close()

        asyncio.run(serve())
        return 0

    m.set_defaults(func=stdio)
    ns = p.parse_args(argv)
    return ns.func(ns)


if __name__ == "__main__":
    raise SystemExit(main())
