"""Demo: What happens when agent tries to run npx http-server"""
import asyncio
from agent_framework.tools.bash_tool import BashTool

async def demo_without_background():
    """Show what happens WITHOUT background=True"""
    print("=" * 80)
    print("SCENARIO 1: Agent tries to run npx http-server WITHOUT background=True")
    print("=" * 80)

    tool = BashTool()
    result = await tool.execute(
        command='cd "C:\\projects\\dev\\games" && npx http-server -p 8000 --cors',
        background=False  # Agent forgot to use background mode
    )

    if result.error:
        print("\n❌ ERROR RETURNED TO AGENT:")
        print(result.error)
        print("\n✅ Agent sees this error and self-corrects!")
    else:
        print("\n✅ SUCCESS:")
        print(result.output)

    print("\n" + "=" * 80)

async def demo_with_background():
    """Show what happens WITH background=True"""
    print("\n" + "=" * 80)
    print("SCENARIO 2: Agent corrects itself and uses background=True")
    print("=" * 80)

    tool = BashTool()
    result = await tool.execute(
        command='cd "C:\\projects\\dev\\games" && npx http-server -p 8000 --cors',
        background=True  # Correct usage!
    )

    if result.error:
        print("\n❌ ERROR:")
        print(result.error)
    else:
        print("\n✅ SUCCESS - Process started in background!")
        print(result.output)

        # Extract PID
        import re
        match = re.search(r'PID:\s*(\d+)', result.output)
        if match:
            pid = int(match.group(1))
            print(f"\n📊 Process is running with PID: {pid}")
            print(f"🛑 Agent can now stop it with: process_manager(operation='stop', pid={pid})")

            # Clean up - stop the process
            from agent_framework.tools.process_manager_tool import ProcessManagerTool
            pm = ProcessManagerTool()
            stop_result = await pm.execute(operation="stop", pid=pid)
            print(f"\n🧹 Cleanup: {stop_result.output.split(chr(10))[0]}")

    print("\n" + "=" * 80)

async def main():
    await demo_without_background()
    await demo_with_background()

if __name__ == "__main__":
    asyncio.run(main())
