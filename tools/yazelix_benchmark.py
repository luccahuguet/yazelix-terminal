#!/usr/bin/env python3
"""Benchmark harnesses for the Yazelix terminal experiment."""

from __future__ import annotations

import argparse
import csv
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ARTIFACT_ROOT = ROOT / "artifacts" / "benchmarks" / "frame_time"
DEFAULT_SHADER = ROOT / "conformance" / "shaders" / "ghostty_cursor_probe.glsl"


def default_terminal() -> Path:
    release = ROOT / "target" / "release" / "rio"
    if release.exists():
        return release
    return ROOT / "target" / "debug" / "rio"


def timestamp_name() -> str:
    return time.strftime("%Y_%m_%d_%H%M%S")


def json_string(value: str) -> str:
    return json.dumps(value)


def write_rio_config(config_home: Path, template: str) -> Path | None:
    if template == "host":
        return None

    config_home.mkdir(parents=True, exist_ok=True)
    config = config_home / "config.toml"
    if template == "cpu":
        text = "[renderer]\nuse-cpu = true\n"
    elif template == "wgpu":
        text = '[renderer]\nbackend = "Webgpu"\n'
    elif template == "wgpu-shader":
        text = (
            '[renderer]\n'
            'backend = "Webgpu"\n'
            'strategy = "Game"\n'
            f"custom-shader = [{json_string(str(DEFAULT_SHADER))}]\n"
        )
    else:
        raise SystemExit(f"unsupported config template: {template}")
    config.write_text(text, encoding="utf-8")
    return config


def built_in_workload(name: str, lines: int, hold_seconds: float) -> list[str]:
    if name == "scroll":
        script = (
            f"for i in $(seq 1 {lines}); do "
            "printf 'yazelix frame benchmark line %05d\\n' \"$i\"; "
            f"done; sleep {hold_seconds}"
        )
    elif name == "idle":
        script = f"printf 'yazelix frame benchmark idle\\n'; sleep {hold_seconds}"
    elif name == "kitty-graphics":
        script = (
            "python3 tools/yazelix_conformance.py emit kitty_graphics_1x1_rgba; "
            f"printf '\\nkitty graphics fixture emitted\\n'; sleep {hold_seconds}"
        )
    elif name == "sixel":
        script = (
            "python3 tools/yazelix_conformance.py emit sixel_minimal; "
            f"printf '\\nsixel fixture emitted\\n'; sleep {hold_seconds}"
        )
    else:
        raise SystemExit(f"unsupported workload: {name}")

    return ["bash", "--noprofile", "--norc", "-c", script]


def read_proc_sample(pid: int, start_ns: int) -> dict[str, int] | None:
    proc = Path("/proc") / str(pid)
    try:
        stat = (proc / "stat").read_text(encoding="utf-8").split()
        status = (proc / "status").read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None
    except ProcessLookupError:
        return None

    rss_kb = 0
    for line in status:
        if line.startswith("VmRSS:"):
            rss_kb = int(line.split()[1])
            break

    return {
        "elapsed_ns": time.monotonic_ns() - start_ns,
        "cpu_ticks": int(stat[13]) + int(stat[14]),
        "rss_kb": rss_kb,
    }


def write_samples(path: Path, samples: list[dict[str, int]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as sample_file:
        writer = csv.DictWriter(
            sample_file,
            fieldnames=["elapsed_ns", "cpu_ticks", "rss_kb"],
        )
        writer.writeheader()
        writer.writerows(samples)


def read_samples(path: Path | None) -> list[dict[str, int]]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as sample_file:
        return [
            {
                "elapsed_ns": int(row["elapsed_ns"]),
                "cpu_ticks": int(row["cpu_ticks"]),
                "rss_kb": int(row["rss_kb"]),
            }
            for row in csv.DictReader(sample_file)
        ]


def read_frame_log(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as frame_file:
        for line_number, line in enumerate(frame_file, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as err:
                raise SystemExit(f"{path}:{line_number}: invalid frame JSON: {err}") from err
    return events


def percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    if len(sorted_values) == 1:
        return sorted_values[0]
    rank = (len(sorted_values) - 1) * pct
    low = int(rank)
    high = min(low + 1, len(sorted_values) - 1)
    weight = rank - low
    return sorted_values[low] * (1.0 - weight) + sorted_values[high] * weight


def stats_ms(ns_values: list[int]) -> dict[str, float | int]:
    values = sorted(value / 1_000_000.0 for value in ns_values)
    if not values:
        return {"count": 0}
    return {
        "count": len(values),
        "min": values[0],
        "mean": sum(values) / len(values),
        "median": percentile(values, 0.50),
        "p95": percentile(values, 0.95),
        "p99": percentile(values, 0.99),
        "max": values[-1],
    }


def frame_deltas(events: list[dict[str, Any]]) -> list[int]:
    deltas: list[int] = []
    previous_end: int | None = None
    for event in events:
        end = int(event["end_elapsed_ns"])
        if previous_end is not None:
            deltas.append(max(0, end - previous_end))
        previous_end = end
    return deltas


def summarize_proc(samples: list[dict[str, int]]) -> dict[str, float | int | None]:
    if not samples:
        return {
            "sample_count": 0,
            "wall_seconds": None,
            "cpu_seconds": None,
            "cpu_percent": None,
            "max_rss_kb": None,
        }

    first = samples[0]
    last = samples[-1]
    ticks_per_second = os.sysconf(os.sysconf_names["SC_CLK_TCK"])
    wall_seconds = max(0.0, (last["elapsed_ns"] - first["elapsed_ns"]) / 1_000_000_000.0)
    cpu_seconds = max(0.0, (last["cpu_ticks"] - first["cpu_ticks"]) / ticks_per_second)
    cpu_percent = None if wall_seconds == 0.0 else (cpu_seconds / wall_seconds) * 100.0
    return {
        "sample_count": len(samples),
        "wall_seconds": wall_seconds,
        "cpu_seconds": cpu_seconds,
        "cpu_percent": cpu_percent,
        "max_rss_kb": max(sample["rss_kb"] for sample in samples),
    }


def summarize(events: list[dict[str, Any]], samples: list[dict[str, int]]) -> dict[str, Any]:
    redraws = [event for event in events if event.get("event") == "redraw"]
    presented = [event for event in redraws if event.get("presented")]
    first_redraw = redraws[0] if redraws else None
    first_presented = presented[0] if presented else None
    vblank_values = [
        int(event["vblank_interval_ns"])
        for event in redraws
        if int(event.get("vblank_interval_ns", 0)) > 0
    ]

    return {
        "schema": 1,
        "frame_count": len(redraws),
        "presented_frame_count": len(presented),
        "first_redraw_ms": None
        if first_redraw is None
        else int(first_redraw["end_elapsed_ns"]) / 1_000_000.0,
        "first_presented_frame_ms": None
        if first_presented is None
        else int(first_presented["end_elapsed_ns"]) / 1_000_000.0,
        "redraw_delta_ms": stats_ms(frame_deltas(redraws)),
        "presented_delta_ms": stats_ms(frame_deltas(presented)),
        "render_duration_ms": stats_ms(
            [int(event["render_duration_ns"]) for event in redraws]
        ),
        "target_vblank_ms": stats_ms(vblank_values),
        "process": summarize_proc(samples),
    }


def flatten_summary(summary: dict[str, Any], prefix: str = "") -> list[tuple[str, Any]]:
    rows: list[tuple[str, Any]] = []
    for key, value in summary.items():
        name = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            rows.extend(flatten_summary(value, name))
        else:
            rows.append((name, value))
    return rows


def write_summary(summary: dict[str, Any], json_path: Path, csv_path: Path) -> None:
    json_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(["metric", "value"])
        writer.writerows(flatten_summary(summary))


def child_command_from_args(args: argparse.Namespace) -> list[str]:
    if args.command:
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise SystemExit("--command requires argv after --")
        return command
    return built_in_workload(args.workload, args.lines, args.hold_seconds)


def command_frame_run(args: argparse.Namespace) -> int:
    terminal = Path(args.terminal).expanduser()
    if not terminal.exists():
        raise SystemExit(f"terminal binary does not exist: {terminal}")

    artifact_dir = Path(args.artifact_dir or DEFAULT_ARTIFACT_ROOT / timestamp_name())
    if not artifact_dir.is_absolute():
        artifact_dir = ROOT / artifact_dir
    artifact_dir.mkdir(parents=True, exist_ok=True)
    frame_log = artifact_dir / "frame_log.jsonl"
    samples_csv = artifact_dir / "proc_samples.csv"
    stdout_log = artifact_dir / "stdout.log"
    stderr_log = artifact_dir / "stderr.log"
    config_home = artifact_dir / "rio_config_home"
    config_path = write_rio_config(config_home, args.config_template)

    env = os.environ.copy()
    env["YAZELIX_TERMINAL_FRAME_LOG"] = str(frame_log)
    if config_path is not None:
        env["RIO_CONFIG_HOME"] = str(config_home)
    if args.config_template.startswith("wgpu"):
        env.setdefault("WGPU_BACKEND", "vulkan")
    for item in args.env:
        if "=" not in item:
            raise SystemExit(f"--env requires NAME=VALUE, got: {item}")
        name, value = item.split("=", 1)
        env[name] = value

    terminal_argv = [str(terminal), "-e", *child_command_from_args(args)]
    start_ns = time.monotonic_ns()
    samples: list[dict[str, int]] = []
    timed_out = False
    with stdout_log.open("wb") as stdout_file, stderr_log.open("wb") as stderr_file:
        process = subprocess.Popen(
            terminal_argv,
            cwd=ROOT,
            env=env,
            stdout=stdout_file,
            stderr=stderr_file,
        )
        deadline = time.monotonic() + args.timeout
        while process.poll() is None:
            sample = read_proc_sample(process.pid, start_ns)
            if sample is not None:
                samples.append(sample)
            if time.monotonic() >= deadline:
                timed_out = True
                process.terminate()
                try:
                    process.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2.0)
                break
            time.sleep(args.sample_interval)

        final_sample = read_proc_sample(process.pid, start_ns)
        if final_sample is not None:
            samples.append(final_sample)
        returncode = process.poll()

    write_samples(samples_csv, samples)
    events = read_frame_log(frame_log) if frame_log.exists() else []
    summary = summarize(events, samples)
    summary["command"] = {
        "terminal_argv": terminal_argv,
        "returncode": returncode,
        "timed_out": timed_out,
        "frame_log": str(frame_log.relative_to(ROOT)),
        "proc_samples": str(samples_csv.relative_to(ROOT)),
        "config_template": args.config_template,
        "config_path": None if config_path is None else str(config_path.relative_to(ROOT)),
    }
    write_summary(summary, artifact_dir / "summary.json", artifact_dir / "summary.csv")

    print(json.dumps(summary, indent=2, sort_keys=True))
    if timed_out:
        return 124
    return 0 if returncode == 0 else int(returncode or 1)


def command_frame_summary(args: argparse.Namespace) -> int:
    events = read_frame_log(Path(args.frame_log))
    samples = read_samples(Path(args.samples) if args.samples else None)
    summary = summarize(events, samples)
    if args.json_out or args.csv_out:
        json_path = Path(args.json_out or Path(args.frame_log).with_suffix(".summary.json"))
        csv_path = Path(args.csv_out or Path(args.frame_log).with_suffix(".summary.csv"))
        write_summary(summary, json_path, csv_path)
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


def command_self_test(_: argparse.Namespace) -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        frame_log = Path(temp_dir) / "frame_log.jsonl"
        frame_log.write_text(
            "\n".join(
                [
                    '{"event":"benchmark_start","pid":123,"elapsed_ns":0}',
                    '{"event":"redraw","frame_index":0,"window_id":"WindowId(1)",'
                    '"route":"terminal","presented":true,"dirty_after":false,'
                    '"game_mode":false,"start_elapsed_ns":9000000,'
                    '"end_elapsed_ns":10000000,"render_duration_ns":1000000,'
                    '"delta_ns":0,"vblank_interval_ns":16666000}',
                    '{"event":"redraw","frame_index":1,"window_id":"WindowId(1)",'
                    '"route":"terminal","presented":false,"dirty_after":true,'
                    '"game_mode":false,"start_elapsed_ns":25000000,'
                    '"end_elapsed_ns":26000000,"render_duration_ns":1000000,'
                    '"delta_ns":16000000,"vblank_interval_ns":16666000}',
                    '{"event":"redraw","frame_index":2,"window_id":"WindowId(1)",'
                    '"route":"terminal","presented":true,"dirty_after":false,'
                    '"game_mode":false,"start_elapsed_ns":42000000,'
                    '"end_elapsed_ns":43000000,"render_duration_ns":1000000,'
                    '"delta_ns":17000000,"vblank_interval_ns":16666000}',
                    "",
                ]
            ),
            encoding="utf-8",
        )
        summary = summarize(read_frame_log(frame_log), [])
        assert summary["frame_count"] == 3
        assert summary["presented_frame_count"] == 2
        assert summary["first_redraw_ms"] == 10.0
        assert summary["first_presented_frame_ms"] == 10.0
        assert summary["redraw_delta_ms"]["count"] == 2
        assert summary["presented_delta_ms"]["count"] == 1
        assert summary["presented_delta_ms"]["max"] == 33.0
    print("ok yazelix_benchmark self-test")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command_name", required=True)

    run = subcommands.add_parser("frame-run", help="run Rio with frame logging enabled")
    run.add_argument("--terminal", default=str(default_terminal()))
    run.add_argument("--artifact-dir")
    run.add_argument(
        "--config-template",
        choices=["host", "cpu", "wgpu", "wgpu-shader"],
        default="wgpu",
    )
    run.add_argument(
        "--workload",
        choices=["scroll", "idle", "kitty-graphics", "sixel"],
        default="scroll",
    )
    run.add_argument("--lines", type=int, default=20_000)
    run.add_argument("--hold-seconds", type=float, default=0.2)
    run.add_argument("--sample-interval", type=float, default=0.05)
    run.add_argument("--timeout", type=float, default=15.0)
    run.add_argument("--env", action="append", default=[])
    run.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="optional child command after --, passed to rio -e",
    )
    run.set_defaults(func=command_frame_run)

    summary = subcommands.add_parser("frame-summary", help="summarize a frame log")
    summary.add_argument("frame_log")
    summary.add_argument("--samples")
    summary.add_argument("--json-out")
    summary.add_argument("--csv-out")
    summary.set_defaults(func=command_frame_summary)

    self_test = subcommands.add_parser("self-test", help="run harness unit checks")
    self_test.set_defaults(func=command_self_test)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
