# SPDX-License-Identifier: MIT
"""Flask entrypoint for NeuroGPT demo UI."""
from __future__ import annotations

import os

from ui.web import create_app

app = create_app()


if __name__ == "__main__":
    app.run(
        host=os.environ.get("NEUROGPT_FLASK_HOST", "127.0.0.1"),
        port=int(os.environ.get("NEUROGPT_FLASK_PORT", "5000")),
        debug=False,
    )
