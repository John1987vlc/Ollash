import logging
import json
import traceback
from typing import Dict, List, Any, Optional
from colorama import init, Fore, Style, Back

# Initialize colorama for Windows support
init(autoreset=True)

class AgentLogger:
    """Enhanced logging with colors and structure"""
    
    def __init__(self, log_file: str = "agent.log"):
        self.logger = logging.getLogger("CodeAgent")
        self.logger.setLevel(logging.DEBUG)
        
        # Ensure handlers are not added multiple times
        if not self.logger.handlers:
            # File handler - detailed logs
            fh = logging.FileHandler(log_file, encoding='utf-8')
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                '%(asctime)s | %(levelname)-8s | %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.logger.addHandler(fh)
            
            # Console handler - important info only
            ch = logging.StreamHandler()
            ch.setLevel(logging.INFO)
            ch.setFormatter(logging.Formatter('%(message)s'))
            self.logger.addHandler(ch)
    
    def tool_call(self, tool_name: str, args: Dict):
        """Log tool call with details"""
        msg = f"🔧 TOOL CALL: {tool_name}"
        self.logger.info(f"{Fore.CYAN}{msg}{Style.RESET_ALL}")
        
        # Log arguments
        for key, value in args.items():
            if key == "content" and isinstance(value, str) and len(value) > 100:
                preview = value[:100] + "..."
                self.logger.debug(f"   {key}: {preview}")
            else:
                self.logger.debug(f"   {key}: {value}")
    
    def tool_result(self, tool_name: str, result: Dict, success: bool = True):
        """Log tool result"""
        status = "✅ SUCCESS" if success else "❌ FAILED"
        color = Fore.GREEN if success else Fore.RED
        self.logger.info(f"{color}{status}: {tool_name}{Style.RESET_ALL}")
        self.logger.debug(f"   Result: {json.dumps(result, indent=2)[:200]}")
    
    def api_request(self, messages_count: int, tools_count: int):
        """Log API request"""
        msg = f"📡 API REQUEST: {messages_count} messages, {tools_count} tools available"
        self.logger.info(f"{Fore.YELLOW}{msg}{Style.RESET_ALL}")
    
    def api_response(self, has_tool_calls: bool, tool_count: int = 0):
        """Log API response"""
        if has_tool_calls:
            msg = f"📨 API RESPONSE: {tool_count} tool call(s)"
        else:
            msg = "📨 API RESPONSE: Final answer"
        self.logger.info(f"{Fore.YELLOW}{msg}{Style.RESET_ALL}")
    
    def error(self, error_msg: str, exception: Optional[Exception] = None):
        """Log error with full traceback"""
        self.logger.error(f"{Fore.RED}❌ ERROR: {error_msg}{Style.RESET_ALL}")
        if exception:
            self.logger.error(f"   Exception: {str(exception)}")
            self.logger.debug(traceback.format_exc())
    
    def info(self, msg: str):
        """Log info message"""
        self.logger.info(msg)
    
    def debug(self, msg: str):
        """Log debug message"""
        self.logger.debug(msg)
    
    def warning(self, msg: str):
        """Log warning message"""
        self.logger.warning(f"{Fore.YELLOW}⚠️  {msg}{Style.RESET_ALL}")
