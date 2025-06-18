import asyncio
from bot import check_chase_for, CHASE_ZELLE_URL

async def main():
    amt = float(input("Enter amount to check (e.g. 12.34): "))
    ok = await check_chase_for(amt)
    if ok:
        print(f"✅ Found a completed Zelle for ${amt:.2f}")
    else:
        print(f"❌ No matching payment of ${amt:.2f} detected")

if __name__ == "__main__":
    asyncio.run(main())
