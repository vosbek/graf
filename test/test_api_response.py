#!/usr/bin/env python3

import asyncio
import aiohttp
import time

async def test_api_endpoints():
    """Test API endpoints to diagnose hanging issue."""
    
    endpoints = [
        "http://localhost:8090/",
        "http://localhost:8090/api/v1/health/",
        "http://localhost:8090/api/v1/health/live",
        "http://localhost:8090/api/v1/health/ready"
    ]
    
    timeout = aiohttp.ClientTimeout(total=5)  # 5 second timeout
    
    async with aiohttp.ClientSession(timeout=timeout) as session:
        for endpoint in endpoints:
            try:
                print(f"Testing {endpoint}...")
                start_time = time.time()
                
                async with session.get(endpoint) as response:
                    response_time = time.time() - start_time
                    status = response.status
                    text = await response.text()
                    
                    print(f"  Status: {status}")
                    print(f"  Response time: {response_time:.3f}s")
                    print(f"  Response length: {len(text)} chars")
                    
                    if len(text) < 500:  # Only print short responses
                        print(f"  Response: {text}")
                    else:
                        print(f"  Response preview: {text[:200]}...")
                    
            except asyncio.TimeoutError:
                print(f"  TIMEOUT - {endpoint} took longer than 5 seconds")
            except Exception as e:
                print(f"  ERROR - {endpoint}: {e}")
            
            print()

if __name__ == "__main__":
    asyncio.run(test_api_endpoints())