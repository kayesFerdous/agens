import asyncio



from config.logging import setup_logging
from agent.factory import build_agent
from db.database import async_session

setup_logging()


async def main() -> None:
    agent = build_agent()
    session_id = "str"

    exit = ["exit", "quit"]

    while True:
        request = input("Request: ")
        if request in exit:
            print("\n\nThanks bruhh")
            break
        async with async_session() as db:
            response = await agent.run(request, session_id, db)
        # response = await agent.run(request, session_id, db)

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
    asyncio.run(main())
