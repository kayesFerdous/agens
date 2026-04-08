import asyncio

from config.logging import setup_logging
from agent.factory import build_agent
from db.database import async_session
from db.repository import create_session

setup_logging()


async def main() -> None:
    agent = build_agent()
    
    async with async_session() as db:
        session = await create_session(db, title="CLI Auto Session")
        session_id = session.id
        print(f"\n[Started new session: {session_id}]")

    exit_commands = ["exit", "quit"]

    while True:
        request = input("Request: ")
        if request in exit_commands:
            print("\n\nThanks bruhh")
            break
        
        async with async_session() as db:
            response = await agent.run(request, session_id, db)

            if response.success:
                print((response.answer or "(no answer synthesized)"))
            else:
                print(f"\nFailed: {response.error}")

            if response.tool_history:
                print("\n=== Tool History ===")
                for i, call in enumerate(response.tool_history, 1):
                    status = "FAIL" if call.error else "OK"
                    print(f"  [{i}] [{status}] {call.tool}({call.arguments}) -> {call.result or call.error}")

            if response.usage:
                u = response.usage
                print(f"\nTokens — prompt: {u.prompt_tokens}  completion: {u.completion_tokens}  total: {u.total_tokens}", end="\n\n\n")


if __name__ == "__main__":
    asyncio.run(main())
