from __future__ import annotations

import shutil
import subprocess
import sys


def notify(summary: str, body: str = "") -> None:
    if shutil.which("notify-send"):
        args = ["notify-send", "--app-name=Media Preview", summary]
        if body:
            args.append(body)
        subprocess.run(args, check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return

    message = summary if not body else f"{summary}: {body}"
    print(message, file=sys.stderr)

