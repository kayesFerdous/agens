# main.py — entry point
from config.logging import setup_logging
from agent.factory import build_agent

setup_logging()


def main() -> None:
    agent = build_agent()
    request = input("Request: ")
    response = agent.run(request)

    if response.success:
        print("\n" + (response.answer or "(no answer synthesized)"))
    else:
        print(f"\nFailed: {response.error}")

    if response.tool_history:
        print("\n=== Tool History ===")
        for i, call in enumerate(response.tool_history, 1):
            status = "FAIL" if call.error else "OK"
            print(f"  [{i}] [{status}] {call.tool}({call.arguments}) -> {call.result or call.error}")


if __name__ == "__main__":
    main()

