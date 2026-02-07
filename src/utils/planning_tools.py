from typing import List, Dict, Any, Optional
from datetime import datetime
from colorama import Fore, Style
import json
from pathlib import Path # Added Path import

class PlanningTools:
    def __init__(self, logger: Any, project_root: Path): # Added project_root
        self.logger = logger
        self.project_root = project_root

    def plan_actions(self, goal: str, steps: List[str], requires_confirmation: bool = False):
        """Display and return the action plan"""
        plan = {
            "goal": goal,
            "steps": steps,
            "requires_confirmation": requires_confirmation,
            "created_at": datetime.now().isoformat()
        }
        
        self.logger.info(f"\n{Fore.CYAN}{'='*60}")
        self.logger.info("📋 ACTION PLAN")
        self.logger.info(f"{'='*60}{Style.RESET_ALL}")
        self.logger.info(f"🎯 Goal: {Fore.WHITE}{goal}{Style.RESET_ALL}")
        self.logger.info(f"\n📝 Steps ({len(steps)}):")
        for i, step in enumerate(steps, 1):
            self.logger.info(f"  {Fore.YELLOW}{i}.{Style.RESET_ALL} {step}")
        self.logger.info(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}\n")
        
        self.logger.info(f"Plan created: {goal}")
        for i, step in enumerate(steps, 1):
            self.logger.debug(f"  Step {i}: {step}")
        
        return {
            "ok": True,
            "goal": goal,
            "steps": steps,
            "plan_displayed": True,
            "plan_data": plan # Return the full plan data
        }

    def select_agent_type(self, agent_type: str) -> Dict[str, Any]:
        """
        Loads the system prompt for a specified agent type.
        """
        valid_agent_types = {"code", "network", "system", "cybersecurity", "orchestrator"}
        if agent_type not in valid_agent_types:
            self.logger.error(f"Invalid agent type: {agent_type}. Must be one of {', '.join(valid_agent_types)}")
            return {"ok": False, "error": f"Invalid agent type: {agent_type}"}

        prompt_file_name = f"default_{agent_type}.json" if agent_type == "orchestrator" else f"default_{agent_type}_agent.json"
        prompt_path = self.project_root / "prompts" / agent_type / prompt_file_name

        try:
            with open(prompt_path, "r", encoding="utf-8") as f:
                prompt_data = json.load(f)
            system_prompt = prompt_data.get("prompt")

            if system_prompt:
                self.logger.info(f"✅ Switched agent context to: {agent_type}")
                return {"ok": True, "agent_type": agent_type, "system_prompt": system_prompt}
            else:
                self.logger.error(f"Prompt field not found or empty in {prompt_path}")
                return {"ok": False, "error": f"Prompt field empty in {prompt_path}"}
        except FileNotFoundError:
            self.logger.error(f"Prompt file not found for agent type '{agent_type}': {prompt_path}")
            return {"ok": False, "error": f"Prompt file not found: {prompt_path}"}
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON from prompt file {prompt_path}")
            return {"ok": False, "error": f"Invalid JSON in prompt file: {prompt_path}"}
        except Exception as e:
            self.logger.error(f"Unexpected error loading prompt for '{agent_type}': {e}", e)
            return {"ok": False, "error": str(e)}
