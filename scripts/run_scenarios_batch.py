import subprocess
import sys
import os
import time

def run_single_scenario(index):
    scenario_name = f"scenario{index}"
    print(f"\n🔍 Running {scenario_name}...", end="", flush=True)
    
    cmd = [
        "pytest", "tests/manual/test_agent_scenarios.py",
        "-m", "manual",
        "-s",
        "-k", scenario_name,
        "--tb=short"
    ]
    
    failed = False
    output_lines = []
    
    # Track start time for custom timeout
    start_time = time.time()
    max_duration = 600 # 10 minutes per scenario
    
    with open("scenarios_test.txt", "a", encoding="utf-8") as f:
        f.write(f"\n\n>>> [{scenario_name}] START <<<\n")
        
        # Use a longer timeout for the subprocess itself
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        
        while True:
            line = process.stdout.readline()
            if not line:
                if process.poll() is not None:
                    break
                time.sleep(1)
                continue
                
            f.write(line)
            f.flush()
            output_lines.append(line)
            print(".", end="", flush=True)
            
            # Check for failure markers
            upper_line = line.upper()
            if "FAILED" in upper_line or "ERROR" in upper_line:
                if "COLLECTING" not in upper_line:
                    failed = True
            
            # Check if we exceeded max duration
            if time.time() - start_time > max_duration:
                print(f" ⌛ TIMEOUT (10 min)")
                process.kill()
                f.write(f"\n🛑 Scenario timed out after {max_duration}s\n")
                return False

        process.wait()
        f.write(f"\n>>> [{scenario_name}] END (Code {process.returncode}) <<<\n")
        
    if failed or process.returncode != 0:
        print(f" ❌ FAILED")
        context = "".join(output_lines[-15:])
        print(f"\n--- FAILURE CONTEXT ---\n{context}\n----------------------")
        return False
    
    print(f" ✅ PASSED")
    return True

if __name__ == "__main__":
    with open("scenarios_test.txt", "w", encoding="utf-8") as f:
        f.write("OLLASH E2E SCENARIOS ROBUST RUN\n")
        
    for i in range(100):
        # Heartbeat to tell parent tool we are active
        if not run_single_scenario(i):
            print(f"\n🛑 Execution halted at scenario {i}.")
            sys.exit(1)
            
    print("\n🎉 ALL 100 SCENARIOS PASSED!")
