import pytest
from unittest.mock import MagicMock, patch
import json
import os

# The fixtures mock_ollama_client, temp_project_root, and default_agent are now provided by conftest.py



# ==============================================================================



# TESTS



# ==============================================================================







def test_network_discovery_no_plan_loop(default_agent, mock_ollama_client):



    user_query = "dime que equipos estan conectados en mi red"



    



    # Define the system prompt for the network agent



    network_agent_system_prompt = "You are Local IT Agent - Ollash, a specialized AI Network Agent. Your task is to assist the user with network-related operations, diagnostics, and configurations."







    # Mock responses to simulate the desired flow:



    # 1. _preprocess_instruction call



    # 2. plan_actions call



    # 3. select_agent_type to 'network'



    # 4. A network tool call (or simply a final content message to signify progression)



    # 5. _translate_to_user_language



    mock_ollama_client.chat.side_effect = [



        # 1st call: _preprocess_instruction



        ({"message": {"content": "Refined English instruction: Find devices on my network."}}, {"prompt_tokens": 10, "completion_tokens": 5}),



        # 2nd call: LLM calls plan_actions (within the main chat loop, first iteration)



        (



            {"message": {"tool_calls": [{"function": {



                "name": "plan_actions", 



                "arguments": {



                    "goal": "Provide a detailed report of connected devices on the user's local network.",



                    "steps": ["Analyze network environment.", "Switch to network agent.", "Identify devices."]



                }



            }}]}},



            {"prompt_tokens": 50, "completion_tokens": 20}



        ),



        # 3rd call: LLM calls select_agent_type to 'network' (within the main chat loop, second iteration)



        (



            {"message": {"tool_calls": [{"function": {"name": "select_agent_type", "arguments": {"agent_type": "network", "reason": "User requested network discovery."}}}]}},



            {"prompt_tokens": 30, "completion_tokens": 10}



        ),



        # 4th call: LLM, now as network agent, returns a result (or calls a network tool) (within the main chat loop, third iteration)



        (



            {"message": {"content": "Network scan initiated to identify connected devices. Results will follow."}},



            {"prompt_tokens": 40, "completion_tokens": 15}



        ),



        # 5th call: _translate_to_user_language



        (



            {"message": {"content": "Network scan initiated to identify connected devices. Results will follow."}},



            {"prompt_tokens": 40, "completion_tokens": 15}



        )



    ]







    response = default_agent.chat(user_query)







    # Assertions



    assert mock_ollama_client.chat.call_count == 5, "Expected 5 LLM calls: preprocess, plan, switch agent, network action, translate"



    assert "Network scan initiated" in response



    assert default_agent.active_agent_type == "network"



    assert network_agent_system_prompt in default_agent.system_prompt
