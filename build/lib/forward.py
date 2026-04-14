import argparse
import shutil
import subprocess
import sys
import threading


def parse_target(target: str) -> tuple:
    """Parse a HOST:PORT target string, returning (host, port)."""
    # Handle bracketed IPv6: [::1]:22
    if "]" in target:
        bracket_end = target.index("]")
        host = target[: bracket_end + 1]
        rest = target[bracket_end + 1 :]
        if not rest.startswith(":"):
            raise argparse.ArgumentTypeError("Target must be in HOST:PORT format")
        port_str = rest[1:]
    else:
        parts = target.rsplit(":", 1)
        if len(parts) != 2:
            raise argparse.ArgumentTypeError("Target must be in HOST:PORT format")
        host, port_str = parts

    if not host:
        raise argparse.ArgumentTypeError("Host cannot be empty")

    if not port_str.isdigit():
        raise argparse.ArgumentTypeError(f"Port must be a number, got '{port_str}'")

    port = int(port_str)
    if not (1 <= port <= 65535):
        raise argparse.ArgumentTypeError(f"Port must be between 1 and 65535, got {port}")

    return host, port


def find_ssh() -> str:
    """Locate the ssh binary on PATH."""
    path = shutil.which("ssh")
    if path is None:
        print("Error: ssh command not found. Is OpenSSH installed?", file=sys.stderr)
        sys.exit(1)
    return path


def build_ssh_command(ssh_path: str, host: str, local_port: int, remote_port: int) -> list:
    """Build the ssh subprocess argument list."""
    return [
        ssh_path,
        "-N",
        "-o", "ExitOnForwardFailure=yes",
        "-L", f"{local_port}:localhost:{remote_port}",
        host,
    ]


def _monitor_stderr(proc: subprocess.Popen, fail_event: threading.Event) -> None:
    """Watch SSH stderr for connection refused messages."""
    refuse_count = 0
    for line in proc.stderr:
        text = line.decode(errors="replace")
        sys.stderr.write(text)
        sys.stderr.flush()
        if "connect failed" in text.lower() and "connection refused" in text.lower():
            refuse_count += 1
            if refuse_count >= 3:
                fail_event.set()
                return


def run_forward(ssh_cmd: list, host: str, local_port: int, remote_port: int) -> None:
    """Launch the SSH tunnel subprocess and wait for it."""
    print(f"Forwarding local {local_port} -> {host}:{remote_port} ... (Ctrl+C to stop)", file=sys.stderr)

    proc = subprocess.Popen(ssh_cmd, stderr=subprocess.PIPE)
    fail_event = threading.Event()
    monitor = threading.Thread(target=_monitor_stderr, args=(proc, fail_event), daemon=True)
    monitor.start()

    try:
        while proc.poll() is None:
            if fail_event.is_set():
                print("\nRemote service refused connection. Exiting.", file=sys.stderr)
                proc.terminate()
                proc.wait(timeout=5)
                sys.exit(1)
            # Small sleep to avoid busy-waiting
            fail_event.wait(timeout=0.5)
    except KeyboardInterrupt:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        print("\nClosing connection...", file=sys.stderr)
        sys.exit(0)

    if proc.returncode != 0:
        print(f"\nConnection failed. Exiting.", file=sys.stderr)
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="forward",
        description="Forward a local port to a remote host via SSH",
    )
    parser.add_argument(
        "target",
        help="Target in HOST:PORT format (e.g. server1:8888, user@host:3306)",
    )
    parser.add_argument(
        "-l", "--local-port",
        type=int,
        default=None,
        help="Local port to bind (default: same as remote port)",
    )

    args = parser.parse_args()
    host, remote_port = parse_target(args.target)
    local_port = args.local_port if args.local_port is not None else remote_port

    if not (1 <= local_port <= 65535):
        parser.error(f"Local port must be between 1 and 65535, got {args.local_port}")

    ssh_path = find_ssh()
    ssh_cmd = build_ssh_command(ssh_path, host, local_port, remote_port)
    run_forward(ssh_cmd, host, local_port, remote_port)


if __name__ == "__main__":
    main()
