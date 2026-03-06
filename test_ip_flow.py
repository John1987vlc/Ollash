
import asyncio
import os
import sys
from pathlib import Path

# Add project root to path
sys.path.append(str(Path.cwd()))

from backend.agents.default_agent import DefaultAgent
from backend.core.kernel import AgentKernel

async def main():
    print("🚀 Starting Repro Test: 'dime mi ip'")
    
    # Initialize kernel and agent
    kernel = AgentKernel()
    agent = DefaultAgent(kernel=kernel, project_root=".ollash")
    
    print("\n--- Sending Instruction ---")
    instruction = "dime mi ip"
    
    try:
        # Run chat
        result = await agent.chat(instruction)
        
        print("\n--- FINAL RESULT ---")
        if isinstance(result, dict):
            print(f"Text: {result.get('text')}")
            print(f"Metrics: {result.get('metrics')}")
            content_len = len(result.get('text', ''))
            print(f"Content Length: {content_len}")
            
            if content_len > 0:
                print("\n✅ SUCCESS: Content received!")
            else:
                print("\n❌ FAILURE: Content is empty.")
        else:
            print(f"Result: {result}")
            
    except Exception as e:
        print(f"\n❌ CRITICAL ERROR during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
