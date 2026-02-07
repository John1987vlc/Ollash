from typing import List, Dict, Any, Optional
from datetime import datetime # Keep datetime import
from colorama import Fore, Style

class PlanningTools:
    def __init__(self, logger: Any):
        self.logger = logger
        # Removed _current_plan

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