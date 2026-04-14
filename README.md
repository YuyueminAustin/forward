# forward

Local port forwarding via SSH, with a single command.

## Install

```bash
pip install .
```

This adds the `forward` command to your PATH.

## Usage

```bash
# Forward local port 8888 to remote port 8888 on an SSH config alias
forward server1:8888

# Use a different local port
forward server1:8888 -l 9999

# Works with user@host too
forward user@192.168.1.1:3306
```

Press `Ctrl+C` to stop.

## Requirements

- Python >= 3.9
- OpenSSH (`ssh` on PATH)
- No external Python dependencies

## How it works

Runs `ssh -N -L` under the hood. SSH config aliases from `~/.ssh/config` work automatically. Auto-exits if the remote service refuses connections.
