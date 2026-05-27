# SPDX-License-Identifier: MIT
"""Entrypoint for the local NeuroGPT MVP API."""
from __future__ import annotations

import os

from ui.api import app


if __name__ == "__main__":
    app.run(
        host=os.environ.get("NEUROGPT_API_HOST", "127.0.0.1"),
        port=int(os.environ.get("NEUROGPT_API_PORT", "5050")),
        debug=False,
    )
