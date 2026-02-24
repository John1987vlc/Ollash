import os
import yaml
import re
import sys
from colorama import Fore, Style, init

init(autoreset=True)

# CONFIGURATION
PROMPTS_DIR = "./prompts"
REQUIRED_HEADERS = ["# CONTEXT", "# OBJECTIVE", "# INSTRUCTIONS", "# CONSTRAINTS", "# OUTPUT FORMAT"]
FORBIDDEN_FUZZY_WORDS = ["maybe", "try to", "approximately", "sort of", "usually", "as possible"]

class PromptValidator:
    def __init__(self):
        self.errors = []
        self.warnings = []

    def validate_content(self, filename, content):
        score = 100
        if not content:
            return 0

        # 1. Structure Check
        for header in REQUIRED_HEADERS:
            if header not in content:
                self.errors.append(f"[{filename}] Missing mandatory header: {header}")
                score -= 15

        # 2. Ambiguity Check (Non-deterministic language)
        for word in FORBIDDEN_FUZZY_WORDS:
            if re.search(rf"\b{word}\b", content, re.I):
                self.warnings.append(f"[{filename}] Ambiguous word detected: '{word}'")
                score -= 5

        # 3. SLM Compatibility (Length and Complexity)
        if len(content) > 3000:
            self.warnings.append(f"[{filename}] Large prompt size ({len(content)} chars). May degrade SLM performance.")
            score -= 10

        # 4. Instruction Density
        has_numbered = re.search(r"\d+\.", content)
        if not has_numbered:
            self.warnings.append(f"[{filename}] No numbered instructions found. Decreases determinism.")
            score -= 10

        return max(0, score)

    def process_file(self, file_path):
        rel_path = os.path.relpath(file_path, PROMPTS_DIR)
        print(f"\n{Fore.CYAN}🔍 Analyzing: {rel_path}")
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            
            # Handle both single prompt files and service maps
            if isinstance(data, dict):
                if 'prompt' in data:
                    score = self.validate_content(rel_path, data['prompt'])
                else:
                    # Nested services (like services.yaml)
                    scores = []
                    for key, sub_data in data.items():
                        if isinstance(sub_data, dict) and 'system' in sub_data:
                            scores.append(self.validate_content(f"{rel_path}->{key}", sub_data['system']))
                    score = sum(scores) / len(scores) if scores else 0
            else:
                score = 0
                self.errors.append(f"[{rel_path}] Invalid YAML structure (not a dictionary)")

            color = Fore.GREEN if score > 80 else Fore.YELLOW if score > 50 else Fore.RED
            print(f"{Style.BRIGHT}Quality Score: {color}{score}/100")

        except Exception as e:
            self.errors.append(f"[{rel_path}] YAML Parsing Error: {str(e)}")

    def run(self):
        if not os.path.exists(PROMPTS_DIR):
            print(f"{Fore.RED}Error: {PROMPTS_DIR} directory not found.")
            sys.exit(1)

        for root, _, files in os.walk(PROMPTS_DIR):
            for file in files:
                if file.endswith(('.yaml', '.yml')):
                    self.process_file(os.path.join(root, file))

        print(f"\n{Fore.MAGENTA}{'='*40}")
        print(f"{Fore.MAGENTA}REPORT SUMMARY")
        print(f"{Fore.MAGENTA}{'='*40}")
        
        for w in self.warnings:
            print(f"{Fore.YELLOW}⚠️  {w}")
        for e in self.errors:
            print(f"{Fore.RED}❌  {e}")

        if self.errors:
            print(f"\n{Fore.RED}Build failed due to structural errors.")
            sys.exit(1)
        else:
            print(f"\n{Fore.GREEN}All prompts passed structural validation.")
            sys.exit(0)

if __name__ == "__main__":
    PromptValidator().run()
