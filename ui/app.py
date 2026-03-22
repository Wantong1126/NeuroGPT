# SPDX-License-Identifier: MIT
\"\"\"NeuroGPT v2 — CLI Demo App.\"\"\"
from pipeline.orchestrator import run_pipeline
from pipeline.state import new_case
from core.types import CaseState

def main():
    session_id = "cli-demo-001"
    state: CaseState | None = None
    print("NeuroGPT v2 — 神经内科症状评估工具 (Demo)")
    print("输入症状描述，按回车发送。输入 exit 退出。\n")
    while True:
        user_input = input("您：").strip()
        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "退出"):
            break
        state, output = run_pipeline(session_id, user_input, state)
        if output.needs_follow_up_question:
            print(f"\nNeuroGPT：{output.follow_up_question}\n")
        else:
            print(f"\nNeuroGPT：评估完成。担忧等级：{output.concern_level}，建议：{output.action_level}\n")

if __name__ == "__main__":
    main()
