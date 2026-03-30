# SPDX-License-Identifier: MIT
"""NeuroGPT v2 - CLI Demo App."""

from pipeline.orchestrator import run_pipeline
from core.types import CaseState



def main() -> None:
    session_id = "cli-demo-001"
    state: CaseState | None = None
    print("NeuroGPT v2 CLI Demo")
    print("输入症状描述，输入 exit 退出。")

    while True:
        user_input = input("你：").strip()
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit"}:
            break

        state, output = run_pipeline(session_id, user_input, state)
        if output.needs_follow_up_question:
            print(f"\nNeuroGPT：{output.follow_up_question}\n")
        else:
            print(f"\nNeuroGPT：关注等级={output.concern_level}，建议行动={output.action_level}\n")


if __name__ == "__main__":
    main()
