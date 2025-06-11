#!/usr/bin/env python3

import asyncio
import aiohttp
import sys
import json
sys.path.append('.')
from src.config import get_setting

async def test_api():
    headers = {"X-Api-Key": get_setting("API_NINJAS_KEY")}
    
    async with aiohttp.ClientSession() as sess:
        print("Testing JPM with show_upcoming=true:")
        async with sess.get("https://api.api-ninjas.com/v1/earningscalendar?ticker=JPM&show_upcoming=true", headers=headers) as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))
        
        print("\nTesting JPM without show_upcoming:")
        async with sess.get("https://api.api-ninjas.com/v1/earningscalendar?ticker=JPM", headers=headers) as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))
        
        print("\nTesting C with show_upcoming=true:")
        async with sess.get("https://api.api-ninjas.com/v1/earningscalendar?ticker=C&show_upcoming=true", headers=headers) as resp:
            data = await resp.json()
            print(json.dumps(data, indent=2))

if __name__ == "__main__":
    asyncio.run(test_api()) 