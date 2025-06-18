#!/usr/bin/env bash
set -euo pipefail

echo "👉 Testing DoorDash account creation with SMSPool…"

python3 - << 'EOF'
import asyncio
from bot import create_doordash_account_with_sms

async def main():
    try:
        result = await create_doordash_account_with_sms()
        print("🎉 Success:", result)
    except Exception as e:
        print("❌ Failure:", e)

asyncio.run(main())
EOF
