"""
RenewAI – WhatsApp Agent
===============================
Conversational agent for WhatsApp-based renewal interactions with
ChromaDB-backed objection handling, EMI/grace proposals, and
automatic human escalation on distress detection.
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from gemini_integration import GeminiIntegration

load_dotenv()


class WhatsAppAgent:
    """WhatsApp channel agent for insurance renewal conversations."""

    SYSTEM_PROMPT = (
        "You are Suraksha Life Insurance's WhatsApp Agent.\n"
        "Rules:\n"
        "1. ONLY use verified facts from the context provided. Never invent data.\n"
        "2. Keep messages conversational, ≤160 characters per bubble.\n"
        "3. Offer EMI or grace period options if available for the product.\n"
        "4. On the 3rd message from the customer, offer 'talk to a human'.\n"
        "5. Always verify payment status before discussing payments.\n"
        "6. If DISTRESS is detected (job loss, bereavement, illness), escalate immediately with empathy.\n"
        "7. Be transparent that you are an AI assistant.\n\n"
        "Output JSON:\n"
        '{"reply_text": "...", "suggested_quick_replies": [], "actions": [], '
        '"escalate": false, "detected_intent": "..."}\n'
    )

    PRODUCT_BENEFITS = {
        "term": {
            "name": "Term Life Shield",
            "emi_available": True,
            "grace_days": 30,
            "upi_id": "surakshalife.term@upi",
        },
        "endowment": {
            "name": "Endowment Plus",
            "emi_available": True,
            "grace_days": 30,
            "upi_id": "surakshalife.endow@upi",
        },
        "ulip": {
            "name": "Wealth Builder ULIP",
            "emi_available": False,
            "grace_days": 15,
            "upi_id": "surakshalife.wealth@upi",
        },
    }

    ESCALATION_MESSAGES = {
        "en-IN": (
            "I'm really sorry you're going through this. Your wellbeing matters most to us. "
            "I'm connecting you with a specialist who can help with your situation. "
            "They'll reach out within the next 2 hours. 🙏"
        ),
        "hi-IN": (
            "मुझे बहुत दुख है कि आप इस स्थिति से गुजर रहे हैं। आपकी भलाई हमारे लिए सबसे "
            "महत्वपूर्ण है। मैं आपको एक विशेषज्ञ से जोड़ रहा/रही हूं। वे 2 घंटे में संपर्क करेंगे। 🙏"
        ),
        "ta-IN": (
            "நீங்கள் இதை அனுபவிக்கிறீர்கள் என்பதில் மிகவும் வருந்துகிறேன். "
            "உங்கள் நலன் எங்களுக்கு மிக முக்கியம். "
            "ஒரு நிപുணரை உங்களுடன் இணைக்கிறேன். 🙏"
        ),
        "ml-IN": (
            "നിങ്ങൾ ഈ സാഹചര്യത്തിലൂടെ കടന്നുപോകുന്നതിൽ ഞാൻ ശരിക്കും ക്ഷമിക്കുന്നു. "
            "ഒരു സ്പെഷ്യലിസ്റ്റ് ഉടൻ ബന്ധപ്പെടും. 🙏"
        ),
    }

    def __init__(self, db=None):
        self.db = db
        self.gemini = GeminiIntegration(system_instruction=self.SYSTEM_PROMPT)
        self.objection_lib = None

        try:
            from objection_library import ObjectionLibrary
            self.objection_lib = ObjectionLibrary()
        except Exception as e:
            print(f"[WhatsAppAgent] Objection library init error: {e}")

    # ── Public API ───────────────────────────────────────────────────────
    def handle_message(self, policy_id: str, customer_message: str) -> dict:
        """Process an inbound WhatsApp message and generate a response."""
        if not self.db:
            return {"error": "No database connection"}

        policy = self.db.get_policy(policy_id)
        if not policy:
            return {"error": f"Policy {policy_id} not found"}

        # Grounding-facts validation
        if not policy.get("premium_amount") or not policy.get("due_date"):
            return {
                "error": "MISSING_VERIFIED_FACTS",
                "message": "Cannot process: premium_amount and due_date are required",
            }

        customer = self.db.get_customer(policy["customer_id"])
        if not customer:
            return {"error": "Customer not found"}

        language = customer.get("language_pref", "en-IN")
        product = self.PRODUCT_BENEFITS.get(policy.get("product", "term"), {})

        # Get conversation context
        history = self._get_history(policy_id)
        wa_count = self._get_wa_count(policy_id)
        payment_status = self._check_payment_status(policy_id)

        # Query objection library
        objection_context = ""
        if self.objection_lib:
            try:
                matches = self.objection_lib.query(customer_message, n_results=1)
                if matches and matches[0].get("distance", 999) < 1.5:
                    objection_context = (
                        f"Relevant objection handling:\n"
                        f"Category: {matches[0]['category']}\n"
                        f"Suggested approach: {matches[0]['response']}"
                    )
            except Exception:
                pass

        # Third message flag
        is_third = wa_count >= 2
        third_msg_flag = (
            "IMPORTANT: This is the 3rd+ message from this customer. "
            "You MUST offer to connect with a human agent."
            if is_third else
            "This is message #{} from this customer.".format(wa_count + 1)
        )

        # Build prompt
        prompt = f"""Respond to this WhatsApp message from an insurance customer.

VERIFIED FACTS:
- Customer: {customer.get('full_name')} ({language})
- Policy: {policy_id} – {product.get('name', policy.get('product'))}
- Premium: ₹{policy['premium_amount']:,}
- Due date: {policy['due_date']}
- Payment status: {payment_status}
- EMI: {'Available' if product.get('emi_available') else 'Not available'}
- Grace period: {product.get('grace_days', 30)} days

{third_msg_flag}

{f'Conversation history:{chr(10)}{history}' if history else 'No prior messages.'}

{objection_context}

Customer message: "{customer_message}"

Respond with JSON: {{reply_text, suggested_quick_replies, actions, escalate, detected_intent}}"""

        result = {
            "reply_text": "",
            "detected_intent": "UNCLEAR",
            "quick_replies": [],
            "escalated": False,
            "policy_id": policy_id,
        }

        try:
            raw_response = self.gemini._call(prompt)
            parsed = self.gemini._parse_json(raw_response)

            result["reply_text"] = parsed.get("reply_text", "")
            result["detected_intent"] = str(parsed.get("detected_intent", "UNCLEAR"))
            result["quick_replies"] = parsed.get("suggested_quick_replies", [])
            escalate = parsed.get("escalate", False)

            # Check for distress or human request
            intent = result["detected_intent"].upper()
            if intent in ("DISTRESS", "HUMAN_REQUEST") or escalate:
                esc = self._escalate_human(policy_id, customer_message, language)
                result["escalated"] = True
                result["escalation_id"] = esc.get("escalation_id")
                if intent == "DISTRESS":
                    result["reply_text"] = self.ESCALATION_MESSAGES.get(
                        language, self.ESCALATION_MESSAGES["en-IN"]
                    )
        except Exception as e:
            print(f"[WhatsAppAgent] Error: {e}")
            result["reply_text"] = (
                "Thank you for your message. Let me check on this for you. "
                "A team member will assist you shortly."
            )

        # Fallback if empty
        if not result["reply_text"]:
            result["reply_text"] = (
                "Thank you for reaching out! I'm here to help with your "
                f"{product.get('name', 'policy')} renewal. How can I assist you?"
            )

        # Log events
        self.db.log_event(policy_id, "whatsapp", "replied", {
            "message": customer_message,
            "response": result["reply_text"][:200],
            "intent": result["detected_intent"],
        })

        return result

    def send_reminder(self, policy_id: str, touch: dict) -> dict:
        """Send a proactive WhatsApp renewal reminder."""
        if not self.db:
            return {"error": "No database connection"}

        policy = self.db.get_policy(policy_id)
        if not policy:
            return {"error": f"Policy {policy_id} not found"}

        if not policy.get("premium_amount") or not policy.get("due_date"):
            return {"error": "MISSING_VERIFIED_FACTS"}

        customer = self.db.get_customer(policy["customer_id"])
        product = self.PRODUCT_BENEFITS.get(policy.get("product", "term"), {})
        language = touch.get("language", customer.get("language_pref", "en-IN"))

        prompt = f"""Generate a proactive WhatsApp renewal reminder.

VERIFIED FACTS:
- Customer: {customer.get('full_name')} ({language})
- Policy: {policy_id} – {product.get('name', policy.get('product', 'Insurance Policy'))}
- Premium: ₹{policy['premium_amount']:,}
- Due date: {policy['due_date']}

Brief: {touch.get('content_brief', 'Friendly renewal reminder')}
Tone: {touch.get('tone', 'warm')}

Generate a short WhatsApp message (≤160 chars) with quick reply options.
Respond with JSON: {{reply_text, suggested_quick_replies}}"""

        try:
            raw_response = self.gemini._call(prompt)
            parsed = self.gemini._parse_json(raw_response)

            msg = parsed.get("reply_text", "")
            if msg:
                self.db.log_event(policy_id, "whatsapp", "sent", {
                    "type": "proactive_reminder",
                    "content": msg[:200],
                })
                return {
                    "success": True,
                    "message": msg,
                    "quick_replies": parsed.get("suggested_quick_replies", []),
                }
        except Exception as e:
            print(f"[WhatsAppAgent] Reminder error: {e}")

        # Fallback reminder
        fallback = self._fallback_reminder(customer, policy, product, language)
        self.db.log_event(policy_id, "whatsapp", "sent", {"type": "fallback_reminder"})
        return fallback

    # ── Helpers ───────────────────────────────────────────────────────────
    def _get_history(self, policy_id: str) -> str:
        events = self.db.get_journey(policy_id)
        wa_events = [e for e in events if e.get("channel") == "whatsapp" and e.get("event_type") == "replied"][:3]
        history = ""
        for e in reversed(wa_events):
            payload = json.loads(e["payload"]) if isinstance(e["payload"], str) else e["payload"]
            history += "Customer: {}\nAI: {}\n".format(payload.get('message'), payload.get('response'))
        return history

    def _get_wa_count(self, policy_id: str) -> int:
        events = self.db.get_journey(policy_id)
        return len([e for e in events if e.get("channel") == "whatsapp" and e.get("event_type") == "replied"])

    def _check_payment_status(self, policy_id: str) -> str:
        payments = self.db.get_payments_by_policy(policy_id)
        if not payments:
            return "pending"
        return payments[0].get("status", "pending")

    def _fallback_reminder(self, customer: dict, policy: dict, product: dict, language: str) -> dict:
        first_name = customer.get("full_name", "there").split()[0]
        msg = "Namaste {}! Your {} premium of ₹{:,} is due soon on {}. Please renew to ensure uninterrupted protection.".format(
            first_name, product.get("name", "policy"), policy["premium_amount"], policy["due_date"]
        )
        return {
            "success": True,
            "message": msg,
            "quick_replies": ["Pay Now", "Remind me later"],
        }

    def _escalate_human(self, policy_id: str, message: str, language: str) -> dict:
        reason = "Manual request or detected distress in WhatsApp: {}".format(message[:150])
        return self.db.create_escalation(policy_id, reason, priority=1)


if __name__ == "__main__":
    from database import DB
    db = DB()
    agent = WhatsAppAgent(db=db)
    print("Test Policy Reminder:")
    print(agent.send_reminder("POL-1009", {"tone": "urgent"}))
    print("\nTest Customer Reply:")
    print(agent.handle_message("POL-1009", "Is my premium high?"))
