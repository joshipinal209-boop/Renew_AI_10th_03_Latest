"""
RenewAI – ElevenLabs Voice Agent
=======================================
Handles automated outbound calls via ElevenLabs Conversational AI.
"""

import os
import requests
from typing import Optional

class ElevenLabsAgent:
    """Voice agent for triggering ElevenLabs Conversational AI outbound calls."""

    def __init__(self, db=None):
        self.db = db
        self.api_key = os.getenv("ELEVENLABS_API_KEY")
        self.agent_id = os.getenv("ELEVENLABS_AGENT_ID")
        self.phone_id = os.getenv("ELEVENLABS_PHONE_ID", "+15077650969")
        self.api_base = "https://api.elevenlabs.io/v1/convai"

    def trigger_outbound_call(self, policy_id: str) -> dict:
        """Trigger an outbound call for a policy renewal."""
        if not self.api_key or not self.agent_id:
            return {
                "success": False,
                "error": "MISSING_CREDENTIALS",
                "message": "ElevenLabs API Key or Agent ID not configured."
            }

        if not self.db:
            return {"success": False, "error": "No database connection"}

        policy = self.db.get_policy(policy_id)
        if not policy:
            return {"success": False, "error": "Policy not found"}

        customer = self.db.get_customer(policy["customer_id"])
        if not customer:
            return {"success": False, "error": "Customer not found"}

        # We use the primary phone number from the customer profile
        # If not present, we can't call
        phone_number = customer.get("phone")
        if not phone_number:
            return {"success": False, "error": "No phone number for customer"}

        # ElevenLabs Endpoint for Twilio Outbound Call
        url = f"{self.api_base}/twilio/outbound-call"
        headers = {"xi-api-key": self.api_key}
        
        # Inject context into the agent using initial_context
        # Use dynamic variables that the ElevenLabs agent can use
        payload = {
            "agent_id": self.agent_id,
            "to_number": phone_number,
            "agent_phone_number_id": self.phone_id,
            "conversation_config_override": {
                "agent": {
                    "prompt": {
                        "prompt": f"You are calling {customer.get('full_name')} regarding policy {policy_id}. "
                                  f"The premium due is ₹{policy.get('premium_amount', 0):,}. "
                                  f"The due date is {policy.get('due_date')}."
                    }
                }
            }
        }

        try:
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Log the call event
            self.db.log_event(policy_id, "voice", "call_initiated", {
                "provider": "elevenlabs",
                "call_id": data.get("call_id"),
                "to_number": phone_number
            })

            return {
                "success": True,
                "call_id": data.get("call_id"),
                "status": "initiated",
                "message": f"ElevenLabs call triggered for {policy_id}"
            }
        except Exception as e:
            error_msg = str(e)
            if hasattr(e, 'response') and e.response is not None:
                try:
                    error_msg = e.response.json().get('detail', error_msg)
                except:
                    pass
            
            print(f"[ElevenLabsAgent] Error: {error_msg}")
            return {
                "success": False,
                "error": "CALL_FAILED",
                "message": error_msg
            }
