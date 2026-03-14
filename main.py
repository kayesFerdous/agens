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
        for r in response.results:
            status = "OK" if r.success else "FAIL"
            print(f"  [{status}] {r.step.tool}: {r.output[:200]}")


if __name__ == "__main__":
    main()

