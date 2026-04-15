import asyncio
import httpx
import redis.asyncio as redis
import json

async def main():
    r = redis.from_url("redis://localhost:6379")
    token = await r.get("fyers:access-token")
    if not token:
        print("No token found in Redis!")
        return
    token = token.decode() if isinstance(token, bytes) else token

    headers = {"Authorization": f"V14SK80BWD-100:{token}"}
    url = "https://api-t1.fyers.in/data/options-chain-v3?symbol=NSE:NIFTY50-INDEX&strikecount=12"

    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=headers)
        data = resp.json()
        print(json.dumps(data, indent=2)[:3000])

asyncio.run(main())