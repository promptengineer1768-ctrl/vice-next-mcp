"""Launch one configured VICE instance; exits cleanly when VICE is unavailable."""
import asyncio, os
from vice_next_mcp.process import ProcessController

async def main():
    exe = os.environ.get("VICE_X64SC")
    if not exe:
        print("SKIP: set VICE_X64SC to run this example")
        return
    ctl = ProcessController("artifacts")
    proc = await ctl.launch("c64", exe)
    try:
        print(f"instance={proc.instance_id} port={proc.monitor_port}")
    finally:
        await proc.stop()

if __name__ == "__main__":
    asyncio.run(main())
