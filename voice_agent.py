"""
RenewAI – Voice Agent
===========================
Generates automated voice call scripts using Gemini 2.5 Flash with
TTS emotional cues, identity verification, and multi-language support.
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from gemini_integration import GeminiIntegration

load_dotenv()


class VoiceAgent:
    """Voice channel agent for generating outbound renewal call scripts."""

    SYSTEM_PROMPT = (
        "You are Suraksha Life Insurance's AI Voice Call Agent generating outbound renewal call scripts.\n"
        "Rules:\n"
        "1. ONLY use verified facts from context — never invent policy data.\n"
        "2. Scripts should be 40-70 seconds when spoken (approx 100-175 words).\n"
        "3. Greet the customer by name and verify identity using last 2 digits of policy ID.\n"
        "4. Check payment status before discussing payments.\n"
        "5. Handle common objections empathetically.\n"
        "6. Mention EMI/grace period options if available.\n"
        "7. Use [PAUSE] for natural speech breaks.\n"
        "8. Use [WARM], [REASSURING], [URGENT] for TTS emotion cues.\n"
        "9. Be transparent that this is an AI-assisted call.\n\n"
        "Output JSON:\n"
        '{"script": "...", "language": "...", "estimated_duration_seconds": N, '
        '"tone": "...", "requires_human_callback": false}\n'
    )

    PRODUCT_BENEFITS = {
        "term": {
            "name": "Term Life Shield",
            "emi_available": True,
            "grace_days": 30,
        },
        "endowment": {
            "name": "Endowment Plus",
            "emi_available": True,
            "grace_days": 30,
        },
        "ulip": {
            "name": "Wealth Builder ULIP",
            "emi_available": False,
            "grace_days": 15,
        },
    }

    # Max unresolved objections before escalating to human
    MAX_OBJECTIONS_BEFORE_ESCALATE = 3

    def __init__(self, db=None):
        self.db = db
        self.gemini = GeminiIntegration(system_instruction=self.SYSTEM_PROMPT)
        self._objection_counts: Dict[str, int] = {}  # policy_id -> count

        # Load the objection library for dynamic responses
        try:
            from objection_library import ObjectionLibrary
            self.objection_lib = ObjectionLibrary()
        except Exception:
            self.objection_lib = None

    # ── Public API ───────────────────────────────────────────────────────
    def generate_script(self, policy_id: str) -> dict:
        """Generate a voice call script for a policy renewal."""
        if not self.db:
            return {"error": "No database connection", "success": False}

        policy = self.db.get_policy(policy_id)
        if not policy:
            return {"error": f"Policy {policy_id} not found", "success": False}

        # Grounding-facts validation
        if not policy.get("premium_amount") or not policy.get("due_date"):
            return {
                "error": "MISSING_VERIFIED_FACTS",
                "message": "Cannot generate script: premium_amount and due_date required",
                "success": False,
            }

        customer = self.db.get_customer(policy["customer_id"])
        if not customer:
            return {"error": "Customer not found", "success": False}

        product = self.PRODUCT_BENEFITS.get(policy.get("product", "term"), {})
        payment_status = self._check_payment_status(policy_id)
        last_2 = policy_id[-2:] if len(policy_id) >= 2 else "XX"
        language = customer.get("language_pref", "en-IN")

        # Get recent journey for context
        events = self.db.get_journey(policy_id)[:5]
        recent = "\n".join(
            f"- {e.get('channel', '')}: {e.get('event_type', '')} on {e.get('timestamp', '')}"
            for e in events
        ) if events else "No recent interactions"

        prompt = f"""Generate a voice call script for this insurance renewal call.

VERIFIED FACTS:
- Customer name: {customer.get('full_name')}
- Policy ID: {policy_id}
- Product: {product.get('name', policy.get('product'))}
- Premium: ₹{policy['premium_amount']:,}
- Due date: {policy['due_date']}
- Payment status: {payment_status}
- Language: {language}
- Last 2 digits for verification: {last_2}
- EMI available: {'Yes' if product.get('emi_available') else 'No'}
- Grace period: {product.get('grace_days', 30)} days

Recent interactions:
{recent}

{'NOTE: Payment is already done — generate a thank-you + confirmation script.' if payment_status == 'paid' else ''}

Generate a {('thank-you' if payment_status == 'paid' else 'renewal reminder')} call script.
Include [PAUSE], [WARM], [REASSURING], [URGENT] cues where appropriate.
Respond with JSON: {{script, language, estimated_duration_seconds, tone, requires_human_callback}}"""

        try:
            raw_response = self.gemini._call(prompt)
            parsed = self.gemini._parse_json(raw_response)

            if parsed.get("script"):
                self.db.log_event(policy_id, "voice", "sent", {
                    "type": "script_generated",
                    "duration": parsed.get("estimated_duration_seconds"),
                    "tone": parsed.get("tone"),
                })
                return {
                    "success": True,
                    "script": parsed["script"],
                    "language": parsed.get("language", language),
                    "estimated_duration_seconds": parsed.get("estimated_duration_seconds", 50),
                    "tone": parsed.get("tone", "warm"),
                    "requires_human_callback": parsed.get("requires_human_callback", False),
                    "policy_id": policy_id,
                    "customer_name": customer.get("full_name"),
                }
        except Exception as e:
            print(f"[VoiceAgent] Generation error: {e}")

        # Fallback
        fallback = self._fallback_script(customer, policy, payment_status, product, last_2)
        self.db.log_event(policy_id, "voice", "sent", {
            "type": "script_generated",
            "generated_by": "fallback",
        })
        return fallback

    # ── Objection Handling ────────────────────────────────────────────────

    def handle_objection(self, policy_id: str, objection_text: str) -> dict:
        """Handle a voice-call objection. Escalates after 3 unresolved objections."""
        if not self.db:
            return {"error": "No database connection", "success": False}

        # Increment counter
        self._objection_counts[policy_id] = self._objection_counts.get(policy_id, 0) + 1
        count = self._objection_counts[policy_id]

        # Query objection library for best response
        response_text = ""
        if self.objection_lib:
            matches = self.objection_lib.query(objection_text, n_results=1)
            if matches:
                response_text = matches[0].get("response", "")

        if not response_text:
            response_text = (
                "I understand your concern. Let me see how we can help. "
                "We have flexible options including EMI payments and grace periods."
            )

        # Log the objection event
        self.db.log_event(policy_id, "voice", "objection_raised", {
            "objection": objection_text[:200],
            "objection_count": count,
            "response_provided": response_text[:200],
        })

        # Check if we've hit the limit → escalate
        if count >= self.MAX_OBJECTIONS_BEFORE_ESCALATE:
            policy = self.db.get_policy(policy_id)
            customer = self.db.get_customer(policy["customer_id"]) if policy else None

            esc = self.db.create_escalation(
                policy_id,
                f"Voice call: {count} unresolved objections. Last: {objection_text[:150]}",
                priority=2,
                assigned_to="retention_team",
            )

            self.db.log_event(policy_id, "voice", "escalated", {
                "reason": f"{count}_objections_unresolved",
                "escalation_id": esc.get("escalation_id"),
            })

            # Reset counter after escalation
            self._objection_counts[policy_id] = 0

            return {
                "success": True,
                "escalated": True,
                "escalation_id": esc.get("escalation_id"),
                "objection_count": count,
                "message": f"Escalated to human agent after {count} unresolved objections.",
                "last_response": response_text,
                "policy_id": policy_id,
            }

        return {
            "success": True,
            "escalated": False,
            "objection_count": count,
            "remaining_before_escalation": self.MAX_OBJECTIONS_BEFORE_ESCALATE - count,
            "response": response_text,
            "policy_id": policy_id,
        }

    def reset_objection_count(self, policy_id: str):
        """Reset objection counter (e.g. after successful resolution)."""
        self._objection_counts.pop(policy_id, None)

    # ── Helpers ───────────────────────────────────────────────────────────
    def _check_payment_status(self, policy_id: str) -> str:
        payments = self.db.get_payments_by_policy(policy_id)
        if not payments:
            return "no_payment"
        return payments[0].get("status", "unknown")

    def _fallback_script(self, customer: dict, policy: dict,
                         payment_status: str, product: dict,
                         last_2: str) -> dict:
        """Generate a template-based fallback script."""
        first_name = customer.get("full_name", "Sir/Madam").split()[0]

        if payment_status == "paid":
            script = (
                f"[WARM] Namaste, am I speaking with {first_name}? [PAUSE] "
                f"This is an automated call from Suraksha Life Insurance. [PAUSE] "
                f"I'm calling to confirm that we've received your payment for your "
                f"{product.get('name', 'policy')}. [PAUSE] "
                f"Your policy ending in {last_2} is now renewed and your coverage "
                f"continues without interruption. [PAUSE] "
                f"[REASSURING] Thank you for trusting Suraksha Life with your family's protection. "
                f"If you have any questions, please call us at 1800-XXX-XXXX. [PAUSE] "
                f"Have a wonderful day!"
            )
        else:
            script = (
                f"[WARM] Namaste, am I speaking with {first_name}? [PAUSE] "
                f"This is an automated call from Suraksha Life Insurance. "
                f"For verification, your policy ends in {last_2}. [PAUSE] "
                f"I'm calling about your {product.get('name', 'policy')} renewal. "
                f"Your premium of rupees {policy.get('premium_amount', 0):,} is due on "
                f"{policy.get('due_date', 'soon')}. [PAUSE] "
                f"{'We offer convenient monthly EMI payments. ' if product.get('emi_available') else ''}"
                f"You also have a {product.get('grace_days', 30)}-day grace period. [PAUSE] "
                f"[REASSURING] Your policy protects your family's future. "
                f"Would you like to renew now, or shall I have an advisor call you back? [PAUSE] "
                f"You can also pay via UPI or our website. "
                f"For assistance, call 1800-XXX-XXXX. Thank you!"
            )

        return {
            "success": True,
            "script": script,
            "language": customer.get("language_pref", "en-IN"),
            "estimated_duration_seconds": 55,
            "tone": "warm",
            "requires_human_callback": payment_status != "paid",
            "policy_id": policy.get("policy_id"),
            "customer_name": customer.get("full_name"),
            "generated_by": "fallback",
        }


if __name__ == "__main__":
    from database import DB
    db = DB()
    agent = VoiceAgent(db=db)
    print("Test — POL-1009 (pending):")
    r = agent.generate_script("POL-1009")
    print(f"  Script: {r.get('script', '')[:100]}...")
    print(f"  Duration: {r.get('estimated_duration_seconds')}s")
    print(f"  Tone: {r.get('tone')}")
