"""
RenewAI – Renewal Orchestrator
======================================
Core state-machine engine that manages the insurance policy renewal lifecycle.
Applies hard rules before AI, selects channels, dispatches to agents, handles
customer replies, and manages scheduled outreach touches.
"""

import json
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


# ── State & Action Enums ─────────────────────────────────────────────────

class RenewalState:
    T45_INITIATED = "T45_INITIATED"
    T30_OFFER_SENT = "T30_OFFER_SENT"
    T20_REMINDER = "T20_REMINDER"
    T10_URGENCY = "T10_URGENCY"
    T5_FINAL_ATTEMPT = "T5_FINAL_ATTEMPT"
    T0_DUE = "T0_DUE"
    GRACE_PERIOD = "GRACE_PERIOD"
    PAID = "PAID"
    LAPSED = "LAPSED"
    REVIVAL_CAMPAIGN = "REVIVAL_CAMPAIGN"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    HUMAN_ESCALATED = "HUMAN_ESCALATED"


class ActionType:
    SEND_EMAIL = "send_email"
    SEND_WHATSAPP = "send_whatsapp"
    SCHEDULE_VOICE = "schedule_voice_call"
    DUAL_DISPATCH = "dual_dispatch"
    ENQUEUE_HUMAN = "enqueue_human"
    MARK_PAID = "mark_paid"
    MARK_LAPSED = "mark_lapsed"
    WAIT = "wait"


# ── Template Mapping ─────────────────────────────────────────────────────

TEMPLATE_MAP = {
    "T45": "T45_AWARENESS",
    "T30": "T30_OFFER",
    "T20": "T20_REMINDER",
    "T10": "T10_URGENCY",
    "T5":  "T5_FINAL",
    "T0":  "T0_DUE",
    "REVIVAL": "REVIVAL_CAMPAIGN",
}


class RenewalOrchestrator:
    """State-machine driven renewal orchestration engine."""

    # Pinned 'today' for reproducible demo behaviour
    DEMO_TODAY = datetime(2026, 3, 5)

    def __init__(self, db=None):
        if db is None:
            from database import DB
            db = DB()
        self.db = db

        from gemini_integration import GeminiIntegration
        self.gemini = GeminiIntegration()

        from email_agent import EmailAgent
        self.email_agent = EmailAgent()

        from whatsapp_agent import WhatsAppAgent
        self.whatsapp_agent = WhatsAppAgent(db=self.db)

        from voice_agent import VoiceAgent
        self.voice_agent = VoiceAgent(db=self.db)

        from elevenlabs_agent import ElevenLabsAgent
        self.elevenlabs_agent = ElevenLabsAgent(db=self.db)

    # ══════════════════════════════════════════════════════════════════════
    # CORE ORCHESTRATION
    # ══════════════════════════════════════════════════════════════════════

    def orchestrate(self, policy_id: str) -> dict:
        """Orchestrate renewal for a single policy through the state machine."""
        policy = self.db.get_policy(policy_id)
        if not policy:
            return self._result(policy_id, "error", f"Policy {policy_id} not found")

        customer = self.db.get_customer(policy["customer_id"])
        if not customer:
            return self._result(policy_id, "error", "Customer not found")

        payments = self.db.get_payments_by_policy(policy_id)

        # ── Hard Rule 1: Missing grounding facts ─────────────────────────
        if not policy.get("premium_amount") or not policy.get("due_date"):
            self._audit("orchestrator", "abort_missing_facts",
                       {"policy_id": policy_id},
                       {"reason": "Missing premium_amount or due_date"})
            return self._result(policy_id, "aborted",
                               "Cannot process: missing verified facts (premium/due_date)",
                               RenewalState.T45_INITIATED, customer, policy)

        # ── Hard Rule 2: No contact channel ──────────────────────────────
        if not customer.get("email") and not customer.get("whatsapp_opt_in"):
            esc = self.db.create_escalation(
                policy_id, "No contact channel available", priority=2,
                assigned_to="customer_support",
            )
            self._audit("orchestrator", "escalate_no_contact",
                       {"policy_id": policy_id}, esc)
            return self._result(policy_id, ActionType.ENQUEUE_HUMAN,
                               "No contact channel — escalated to human",
                               RenewalState.HUMAN_ESCALATED, customer, policy)

        # ── Hard Rule 3: Already paid this cycle ─────────────────────────
        paid_this_cycle = any(
            p["status"] == "paid" and self._is_current_cycle(p.get("paid_at"), policy["due_date"])
            for p in payments
        )
        if paid_this_cycle:
            self.db.update_policy_status(policy_id, "active")
            self._audit("orchestrator", "mark_paid",
                       {"policy_id": policy_id}, {"status": "paid"})
            return self._result(policy_id, ActionType.MARK_PAID,
                               "Payment already received this cycle",
                               RenewalState.PAID, customer, policy)

        # ── Hard Rule 4: Post-lapse / Revival (up to 90 days) ───────────
        due = datetime.strptime(policy["due_date"], "%Y-%m-%d")
        days_overdue = (self.DEMO_TODAY - due).days
        if days_overdue > 90:
            self.db.update_policy_status(policy_id, "lapsed")
            esc = self.db.create_escalation(
                policy_id, f"Policy terminated — {days_overdue} days overdue",
                priority=2, assigned_to="retention_team",
            )
            self._audit("orchestrator", "mark_lapsed",
                       {"policy_id": policy_id, "days_overdue": days_overdue}, esc)
            return self._result(policy_id, ActionType.MARK_LAPSED,
                               f"Policy lapsed ({days_overdue} days overdue)",
                               RenewalState.LAPSED, customer, policy)

        # ── Calculate state ──────────────────────────────────────────────
        days_to_due = (due - self.DEMO_TODAY).days
        state = self._days_to_state(days_to_due)
        template_key = self._template_key(days_to_due)

        # ── Channel selection ────────────────────────────────────────────
        risk = policy.get("risk_score", 0)
        channel = self._select_channel(customer, risk, days_to_due)

        # ── T-30 Spec Override: Force WhatsApp if opted-in ───────────────
        if template_key == "T30_OFFER" and customer.get("whatsapp_opt_in"):
            channel = "whatsapp"

        # ── Hard Rule 5: Email 3-attempt no-open escalation ──────────────
        if channel == "email":
            journey = self.db.get_journey(policy_id)
            email_sends = sum(1 for e in journey
                              if e.get("channel") == "email" and e.get("event_type") == "sent")
            email_opens = sum(1 for e in journey
                              if e.get("channel") == "email" and e.get("event_type") == "opened")
            if email_sends >= 3 and email_opens == 0:
                esc = self.db.create_escalation(
                    policy_id,
                    f"Email: {email_sends} sends with 0 opens — customer unresponsive via email",
                    priority=2,
                    assigned_to="retention_team",
                )
                self._audit("orchestrator", "escalate_email_no_open",
                           {"policy_id": policy_id, "email_sends": email_sends,
                            "email_opens": email_opens}, esc)
                # Try switching to WhatsApp or Voice instead of giving up
                if customer.get("whatsapp_opt_in"):
                    channel = "whatsapp"
                else:
                    channel = "voice"
                self.db.log_event(policy_id, "email", "channel_switch", {
                    "reason": f"No opens after {email_sends} emails",
                    "new_channel": channel,
                    "escalation_id": esc.get("escalation_id"),
                })

        # ── Build touch info ─────────────────────────────────────────────
        tone = "urgent" if days_to_due <= 5 else ("formal" if risk < 0.2 else "warm")
        language = customer.get("language_pref", "en-IN")
        schedule_at = self._schedule_time(customer, channel)

        touch = {
            "policy_id": policy_id,
            "channel": channel,
            "schedule_at": schedule_at,
            "language": language,
            "tone": tone,
            "content_brief": f"{template_key} outreach for {policy.get('product', 'term')} renewal",
            "template": template_key,
        }

        # ── Dispatch to agent ────────────────────────────────────────────
        action_map = {
            "email": ActionType.SEND_EMAIL,
            "whatsapp": ActionType.SEND_WHATSAPP,
            "voice": ActionType.SCHEDULE_VOICE,
        }
        action = action_map.get(channel, ActionType.SEND_EMAIL)

        # Log events
        self.db.log_event(policy_id, channel, "sent", {
            "template": template_key,
            "tone": tone,
            "risk": risk,
            "days_to_due": days_to_due,
        })

        self._audit("orchestrator", "orchestrate",
                   {"policy_id": policy_id, "channel": channel,
                    "template": template_key, "days_to_due": days_to_due},
                   {"action": action, "state": state})

        # ── T-45 Branch Logic: schedule follow-up after 48h ────────────────
        # Spec: "If email opened within 48h → wait. If not → escalate to
        #         WhatsApp at T-30"
        if template_key == "T45_AWARENESS" and channel == "email":
            followup_channel = "whatsapp" if customer.get("whatsapp_opt_in") else "voice"
            followup_dt = (self.DEMO_TODAY + timedelta(days=2)).replace(
                hour=10, minute=0, second=0)
            self.db.schedule_touch(
                policy_id, followup_channel, followup_dt.isoformat(),
                language=language, tone="warm",
                content_brief=(
                    "T45_FOLLOWUP: Check if T-45 email was opened. "
                    "If NOT opened within 48h, send follow-up via "
                    f"{followup_channel}."
                ),
            )
            self.db.log_event(policy_id, "orchestrator", "followup_scheduled", {
                "trigger": "T45_email_sent",
                "followup_channel": followup_channel,
                "followup_at": followup_dt.isoformat(),
                "condition": "email_not_opened_within_48h",
            })

        # ── T-30 Branch Logic: schedule voice follow-up at T-20 ──────────
        # Spec: "Conversational WhatsApp in preferred language.
        #         If not read in 24h → Voice call at T-20"
        if template_key == "T30_OFFER" and channel == "whatsapp":
            followup_dt = (due - timedelta(days=20)).replace(
                hour=10, minute=0, second=0)
            self.db.schedule_touch(
                policy_id, "voice", followup_dt.isoformat(),
                language=language, tone="warm",
                content_brief=(
                    "T30_FOLLOWUP: Check if T-30 WhatsApp was read. "
                    "If NOT read, escalate to voice call at T-20."
                ),
            )
            self.db.log_event(policy_id, "orchestrator", "followup_scheduled", {
                "trigger": "T30_whatsapp_sent",
                "followup_channel": "voice",
                "followup_at": followup_dt.isoformat(),
                "condition": "whatsapp_not_read_before_T20",
            })

        # ── T-10 Branch Logic: Dual Dispatch (WA + Email) ────────────────
        # Spec: "WhatsApp + Email. 'Last chance' message with ECS mandate link,
        #         UPI AutoPay option, grace period explanation."
        if template_key == "T10_URGENCY":
            # Override content brief for T-10 specifics
            touch["content_brief"] = (
                "T10_URGENCY: 'Last chance' message. Include ECS mandate setup link, "
                "UPI AutoPay option, and grace period explanation."
            )
            # If WhatsApp is opted-in, schedule it as an additional touch
            if customer.get("whatsapp_opt_in") and channel != "whatsapp":
                self.db.schedule_touch(
                    policy_id, "whatsapp", schedule_at,
                    language=language, tone="urgent",
                    content_brief=touch["content_brief"],
                )
                action = ActionType.DUAL_DISPATCH
                self.db.log_event(policy_id, "orchestrator", "dual_dispatch_scheduled", {
                    "primary": channel,
                    "secondary": "whatsapp",
                    "template": "T10_URGENCY"
                })

        # ── T-5 Branch Logic: Dual Dispatch (Voice + WhatsApp) ──────────
        # Spec: "Urgent dual-channel outreach. Offers 30-day grace period,
        #         premium holiday option, partial payment plan if available."
        if template_key == "T5_FINAL":
            touch["content_brief"] = (
                "T5_URGENCY: Critical zone. Offer 30-day grace period, "
                "premium holiday option, and partial payment plan."
            )
            # Force AI Voice + WhatsApp
            channel = "voice" 
            action = ActionType.DUAL_DISPATCH
            
            # Schedule the secondary WhatsApp touch
            if customer.get("whatsapp_opt_in"):
                self.db.schedule_touch(
                    policy_id, "whatsapp", schedule_at,
                    language=language, tone="urgent",
                    content_brief=touch["content_brief"],
                )
                self.db.log_event(policy_id, "orchestrator", "dual_dispatch_scheduled", {
                    "primary": "voice",
                    "secondary": "whatsapp",
                    "template": "T5_FINAL"
                })

        # ── Post-lapse Branch Logic: Revival Campaign ────────────────────
        if state == RenewalState.REVIVAL_CAMPAIGN:
            rev_quote = self._calculate_revival_quote(policy["premium_amount"], days_overdue)
            touch["content_brief"] = (
                f"REVIVAL: Day {days_overdue} post-lapse. "
                f"Offer penalty waiver. Quote: ₹{rev_quote['total']:,} "
                f"(Penalty: ₹{rev_quote['penalty']:,} waived)."
            )
            # Priority: WhatsApp -> Email
            channel = "whatsapp" if customer.get("whatsapp_opt_in") else "email"
            action = ActionType.SEND_WHATSAPP if channel == "whatsapp" else ActionType.SEND_EMAIL
            touch["template"] = "REVIVAL_CAMPAIGN"

        return self._result(
            policy_id, action,
            f"{template_key} via {channel} (risk={risk:.2f}, {days_to_due}d to due)",
            state, customer, policy,
            channel=channel, template=template_key,
            days_to_due=days_to_due, schedule_at=schedule_at,
        )

    # ══════════════════════════════════════════════════════════════════════
    # CUSTOMER REPLY HANDLING
    # ══════════════════════════════════════════════════════════════════════

    def handle_customer_reply(self, policy_id: str, channel: str,
                              message: str) -> dict:
        """Process an inbound customer message using NLU."""
        policy = self.db.get_policy(policy_id)
        if not policy:
            return {"error": f"Policy {policy_id} not found"}

        customer = self.db.get_customer(policy["customer_id"])
        if not customer:
            return {"error": "Customer not found"}

        language = customer.get("language_pref", "en-IN")

        # Step 1: Classify intent via Gemini
        context = (
            f"Policy: {policy_id}, Product: {policy.get('product')}, "
            f"Premium: ₹{policy.get('premium_amount', 0):,}, "
            f"Due: {policy.get('due_date')}"
        )
        intent_result = self.gemini.classify_intent(message, context)
        intent = intent_result.get("intent", "UNCLEAR")
        confidence = intent_result.get("confidence", 0)

        # Step 2: Sentiment analysis
        sentiment = self.gemini.analyze_sentiment(message, channel)

        # Step 3: Handle based on intent
        escalation_id = None
        rationale = ""
        briefing = None
        
        # New: Specific detection for Premium Holiday / Grace Period / Medical
        is_medical = any(k in message.lower() for k in ["medical", "doctor", "hospital", "surgery", "illness", "disease"])
        is_premium_holiday = any(k in message.lower() for k in ["holiday", "pause", "stop payment", "break", "skip"])

        existing_escs = self.db.get_escalations_by_policy(policy_id)
        open_esc = next((e for e in existing_escs if e["status"] in ("queued", "in_progress")), None)

        if intent in ("DISTRESS", "HUMAN_REQUEST") or sentiment.get("should_escalate") or is_medical or is_premium_holiday:
            priority = 1 if (intent == "DISTRESS" or is_medical) else 2
            assigned_to = "human_specialist" if is_medical else "retention_team"
            
            reason = intent
            if is_medical: reason = "MEDICAL_ISSUE"
            if is_premium_holiday: reason = "PREMIUM_HOLIDAY_REQUEST"

            if open_esc:
                # Update existing escalation instead of creating a new one
                escalation_id = open_esc["escalation_id"]
                new_reason = f"{open_esc['reason']} | UPDATE: {message[:100]}"
                self.db.update_escalation(escalation_id, reason=new_reason)
                response_text = self._follow_up_empathy_message(language)
                rationale = f"Updated existing escalation {escalation_id} with new message."
                state = RenewalState.HUMAN_ESCALATED
                action = ActionType.ENQUEUE_HUMAN
            else:
                # Create new escalation
                esc_data = self.db.create_escalation(
                    policy_id,
                    f"{reason}: {message[:200]}",
                    priority=priority,
                    assigned_to=assigned_to,
                )
                escalation_id = esc_data["escalation_id"]
                rationale = f"Escalated: {reason} detected. Assigned to {assigned_to}."

                # Generate structured briefing note for the human agent
                briefing = self._generate_briefing_note(
                    policy_id, customer, policy, intent if not is_medical else "MEDICAL", sentiment, message,
                )
                self.db.update_escalation(escalation_id, briefing_note=json.dumps(briefing))

                # Empathy response
                response_text = self._empathy_message(intent if not is_medical else "DISTRESS", language)
                action = ActionType.ENQUEUE_HUMAN
                state = RenewalState.HUMAN_ESCALATED
        elif intent == "ALREADY_PAID":
            response_text = (
                "Thank you for letting us know! Payments may take 24-48 hours to reflect. "
                "Could you share the transaction reference so we can verify?"
            )
            action = ActionType.WAIT
            state = RenewalState.T45_INITIATED
            rationale = "Customer claims already paid — verification requested"
        else:
            # Generate response via Gemini
            ai_response = self.gemini.generate_response(
                intent, message, channel, language, context,
            )
            response_text = ai_response.get("response", "Thank you for your message.")
            action = ai_response.get("next_action", ActionType.WAIT)
            state = RenewalState.T45_INITIATED
            rationale = f"AI response for intent={intent}"

        # Log events
        self.db.log_event(policy_id, channel, "replied", {
            "customer_message": message,
            "intent": intent,
            "sentiment": sentiment.get("sentiment"),
            "response": response_text[:200],
        })

        self._audit("orchestrator", "handle_reply",
                   {"policy_id": policy_id, "channel": channel,
                    "message": message[:100], "intent": intent},
                   {"response": response_text[:200], "action": action})

        result = {
            "policy_id": policy_id,
            "intent": intent,
            "confidence": confidence,
            "sentiment": sentiment,
            "action": action,
            "state": state,
            "response_to_customer": response_text,
            "ai_response": {"response": response_text},
            "rationale": rationale,
        }
        if escalation_id:
            result["escalation_id"] = escalation_id
            result["briefing_note"] = briefing
        return result

    # ══════════════════════════════════════════════════════════════════════
    # DAILY BATCH PROCESSING
    # ══════════════════════════════════════════════════════════════════════

    def run_daily_batch(self, within_days: int = 45) -> dict:
        """Orchestrate all policies due within N days."""
        due_policies = self.db.get_due_policies(within_days)
        results = []
        skipped = 0

        for p in due_policies:
            pid = p["policy_id"]
            # Skip already-handled statuses
            if p["status"] == "lapsed":
                skipped += 1
                continue
            result = self.orchestrate(pid)
            results.append(result)

        self._audit("orchestrator", "daily_batch",
                   {"within_days": within_days, "total_found": len(due_policies)},
                   {"processed": len(results), "skipped": skipped})

        return {
            "total_found": len(due_policies),
            "processed": len(results),
            "skipped": skipped,
            "results": results,
        }

    # ══════════════════════════════════════════════════════════════════════
    # SCHEDULED TOUCHES
    # ══════════════════════════════════════════════════════════════════════

    def plan_next_touch(self, policy_id: str, channel: str, schedule_at: str,
                        language: str = "en-IN", tone: str = "warm",
                        content_brief: str = "") -> dict:
        """Plan a future outreach touchpoint."""
        policy = self.db.get_policy(policy_id)
        if not policy:
            return {"error": f"Policy {policy_id} not found"}

        customer = self.db.get_customer(policy["customer_id"])

        # Consent check
        if channel == "whatsapp" and not customer.get("whatsapp_opt_in"):
            return {"error": "Customer has not opted in for WhatsApp"}

        result = self.db.schedule_touch(
            policy_id=policy_id,
            channel=channel,
            schedule_at=schedule_at,
            language=language,
            tone=tone,
            content_brief=content_brief,
        )

        self.db.log_event(policy_id, channel, "sent", {
            "type": "touch_planned",
            "touch_id": result.get("touch_id"),
            "schedule_at": schedule_at,
        })

        self._audit("orchestrator", "plan_touch",
                   {"policy_id": policy_id, "channel": channel, "schedule_at": schedule_at},
                   result)

        return {
            "policy_id": policy_id,
            "action": "scheduled",
            "rationale": "Touchpoint planned successfully",
            "state": RenewalState.T45_INITIATED,
            "channel": channel,
            "schedule_at": schedule_at,
            **result,
        }

    def execute_pending_touches(self, as_of: str | None = None) -> list:
        """Execute all pending scheduled touches that are due."""
        cutoff = as_of or self.DEMO_TODAY.isoformat()
        touches = self.db.get_pending_touches(before=cutoff)
        results = []

        for touch in touches:
            tid = touch["touch_id"]
            pid = touch["policy_id"]
            channel = touch["channel"]
            brief = touch.get("content_brief", "")

            try:
                # ── T-45 Follow-up: check if email was opened before sending WhatsApp
                if channel == "whatsapp" and "T45_FOLLOWUP" in brief:
                    journey = self.db.get_journey(pid)
                    email_opened = any(
                        e.get("channel") == "email" and e.get("event_type") == "opened"
                        for e in journey
                    )
                    if email_opened:
                        # Email was opened → skip WhatsApp, wait for customer action
                        self.db.cancel_touch(tid)
                        self.db.log_event(pid, "orchestrator", "followup_skipped", {
                            "reason": "T-45 email was opened within 48h",
                            "cancelled_touch": tid,
                        })
                        results.append({
                            "touch_id": tid,
                            "status": "skipped",
                            "reason": "Email opened — waiting for customer action",
                        })
                        continue

                # ── T-30 Follow-up: check if WhatsApp was read before calling ─────
                if channel == "voice" and "T30_FOLLOWUP" in brief:
                    journey = self.db.get_journey(pid)
                    wa_read = any(
                        e.get("channel") == "whatsapp" and e.get("event_type") == "read"
                        for e in journey
                    )
                    if wa_read:
                        # WhatsApp was read → skip Voice call, wait for customer action
                        self.db.cancel_touch(tid)
                        self.db.log_event(pid, "orchestrator", "followup_skipped", {
                            "reason": "T-30 WhatsApp was read within 24h",
                            "cancelled_touch": tid,
                        })
                        results.append({
                            "touch_id": tid,
                            "status": "skipped",
                            "reason": "WhatsApp read — waiting for customer action",
                        })
                        continue

                if channel == "email":
                    result = self._dispatch_email(touch)
                elif channel == "whatsapp":
                    result = self._dispatch_whatsapp(touch)
                elif channel == "voice":
                    result = self._dispatch_voice(touch)
                else:
                    result = {"error": f"Unknown channel: {channel}"}

                self.db.mark_touch_sent(tid, result)
                results.append({"touch_id": tid, "status": "sent", "result": result})
            except Exception as e:
                results.append({"touch_id": tid, "status": "failed", "error": str(e)})

        self._audit("orchestrator", "execute_touches",
                   {"cutoff": cutoff, "total": len(touches)},
                   {"executed": len(results)})

        return results

    def cancel_touch(self, touch_id: str) -> dict:
        """Cancel a scheduled touch."""
        result = self.db.cancel_touch(touch_id)
        self._audit("orchestrator", "cancel_touch", {"touch_id": touch_id}, result)
        return result

    # ══════════════════════════════════════════════════════════════════════
    # HELPERS
    # ══════════════════════════════════════════════════════════════════════

    def _select_channel(self, customer: dict, risk: float, days_to_due: int) -> str:
        """Select the optimal outreach channel based on risk, segment, and consent."""
        if risk >= 0.5 and days_to_due <= 10:
            return "voice"
        if (risk >= 0.3 or customer.get("segment") == "HNI") and customer.get("whatsapp_opt_in"):
            return "whatsapp"
        if customer.get("email"):
            return "email"
        if customer.get("whatsapp_opt_in"):
            return "whatsapp"
        return "voice"

    def _template_key(self, days_to_due: int) -> str:
        """Select template based on days to due date."""
        if days_to_due >= 36:
            return "T45_AWARENESS"
        if days_to_due >= 26:
            return "T30_OFFER"
        if days_to_due >= 16:
            return "T20_REMINDER"
        if days_to_due >= 10:
            return "T10_URGENCY"
        if days_to_due >= 5:
            return "T5_FINAL"
        if days_to_due >= 0:
            return "T0_DUE"
        return "REVIVAL"

    def _days_to_state(self, days_to_due: int) -> str:
        """Map days-to-due to a renewal state."""
        if days_to_due >= 36:
            return RenewalState.T45_INITIATED
        if days_to_due >= 26:
            return RenewalState.T30_OFFER_SENT
        if days_to_due >= 16:
            return RenewalState.T20_REMINDER
        if days_to_due >= 10:
            return RenewalState.T10_URGENCY
        if days_to_due >= 5:
            return RenewalState.T5_FINAL_ATTEMPT
        if days_to_due >= 0:
            return RenewalState.T0_DUE
        if days_to_due >= -90:
            return RenewalState.REVIVAL_CAMPAIGN
        return RenewalState.GRACE_PERIOD  # Fallback

    def _calculate_revival_quote(self, premium: float, days_overdue: int) -> dict:
        """Calculate revival amount including penalty and waiver."""
        # Penalty: 9% per annum pro-rata
        penalty_rate = 0.09
        penalty = (premium * penalty_rate * days_overdue) / 365
        penalty = round(penalty, 2)
        
        return {
            "premium": premium,
            "penalty": penalty,
            "waiver_offered": True,
            "total": premium # Penalty waived for revival campaign
        }

    def _schedule_time(self, customer: dict, channel: str) -> str:
        """Build an ISO-8601 timestamp in the customer's preferred window."""
        base = self.DEMO_TODAY
        window = customer.get("preferred_contact_window", "morning")
        hours = {"morning": 9, "afternoon": 14, "evening": 18, "weekend": 10}
        hour = hours.get(window, 10)
        scheduled = base.replace(hour=hour, minute=0, second=0)
        return scheduled.isoformat()

    def _is_current_cycle(self, paid_at: str | None, due_date: str) -> bool:
        """Check if a payment is for the current renewal cycle."""
        if not paid_at:
            return False
        try:
            paid = datetime.fromisoformat(paid_at.replace("Z", "+00:00")
                                          if "Z" in (paid_at or "") else paid_at)
            due = datetime.strptime(due_date, "%Y-%m-%d")
            # Payment within 90 days before due date counts as current cycle
            return (due - timedelta(days=90)) <= paid <= (due + timedelta(days=30))
        except (ValueError, TypeError):
            return False

    def _empathy_message(self, intent: str, language: str) -> str:
        """Return an empathetic response for distress or human request."""
        messages = {
            "DISTRESS": {
                "en-IN": "I'm deeply sorry for what you're going through. A specialist from our team will contact you within 2 hours to assist you personally. Your wellbeing is our priority. 🙏",
                "hi-IN": "मुझे बहुत दुख है। हमारी टीम का एक विशेषज्ञ 2 घंटे के भीतर आपसे संपर्क करेगा। आपकी भलाई हमारी प्राथमिकता है। 🙏",
            },
            "HUMAN_REQUEST": {
                "en-IN": "Of course! I'm connecting you with a human advisor right away. They will call you within 30 minutes. Thank you for your patience.",
                "hi-IN": "बिल्कुल! मैं आपको अभी एक सलाहकार से जोड़ रहा हूं। वे 30 मिनट में कॉल करेंगे।",
            },
        }
        return messages.get(intent, messages["HUMAN_REQUEST"]).get(language, messages.get(intent, {}).get("en-IN", "A team member will contact you shortly."))

    def _follow_up_empathy_message(self, language: str) -> str:
        """Return a message for repeated human/distress requests."""
        messages = {
            "en-IN": "Our team has already prioritized your request and a specialist will be calling you shortly. We have also updated your request with your latest message. Thank you for your patience.",
            "hi-IN": "हमारी टीम ने पहले ही आपकी मदद के लिए काम शुरू कर दिया है और एक विशेषज्ञ जल्द ही आपको कॉल करेगा। हमने आपके अनुरोध को आपके नए संदेश के साथ अपडेट कर दिया है। धैर्य रखने के लिए धन्यवाद।",
        }
        return messages.get(language, messages["en-IN"])

    # ── Human Queue Briefing Note ─────────────────────────────────────────

    def _generate_briefing_note(self, policy_id: str, customer: dict,
                                 policy: dict, intent: str,
                                 sentiment: dict, trigger_message: str) -> dict:
        """Generate a structured briefing document for the human agent.

        Includes: policy summary, customer profile, all prior AI interactions,
        detected sentiment, and recommended approach.
        """
        # Gather full context
        payments = self.db.get_payments_by_policy(policy_id)
        journey = self.db.get_journey(policy_id)
        escalations = self.db.get_escalations_by_policy(policy_id)

        # Summarise AI interactions
        ai_interactions = []
        for e in journey:
            ai_interactions.append({
                "timestamp": e.get("timestamp"),
                "channel": e.get("channel"),
                "event": e.get("event_type"),
                "detail": (e.get("payload") or "")[:200] if isinstance(e.get("payload"), str) else str(e.get("payload", ""))[:200],
            })

        # Determine recommended approach
        approach_map = {
            "DISTRESS": {
                "strategy": "Empathetic retention",
                "opening": "Begin with sincere empathy. Acknowledge their situation before any policy discussion.",
                "actions": [
                    "Offer premium waiver or grace period extension",
                    "Discuss policy conversion options (reduce sum assured)",
                    "Offer to connect with Suraksha Life's welfare programme",
                    "Do NOT pressure for immediate payment",
                ],
            },
            "HUMAN_REQUEST": {
                "strategy": "Personalised service",
                "opening": "Acknowledge their desire to speak with a person. Thank them for their patience.",
                "actions": [
                    "Review their specific concerns from conversation history",
                    "Provide clear, direct answers to pending questions",
                    "Confirm next steps before ending the call",
                ],
            },
            "PRICE_OBJECTION": {
                "strategy": "Value-focused retention",
                "opening": "Acknowledge the cost concern and transition to value discussion.",
                "actions": [
                    "Present EMI / instalment options",
                    "Highlight claim ratio and benefits specific to their product",
                    "Offer premium reduction through sum-assured adjustment",
                ],
            },
        }
        recommended = approach_map.get(intent, approach_map["HUMAN_REQUEST"])

        # Build the briefing note
        briefing = {
            "generated_at": datetime.utcnow().isoformat(),
            "policy_summary": {
                "policy_id": policy_id,
                "product": policy.get("product"),
                "premium_amount": policy.get("premium_amount"),
                "due_date": policy.get("due_date"),
                "status": policy.get("status"),
                "risk_score": policy.get("risk_score"),
            },
            "customer_profile": {
                "name": customer.get("full_name"),
                "age": customer.get("age"),
                "segment": customer.get("segment"),
                "language": customer.get("language_pref"),
                "preferred_contact": customer.get("preferred_contact_window"),
            },
            "payment_history": [
                {
                    "amount": p.get("amount"),
                    "status": p.get("status"),
                    "date": p.get("paid_at") or p.get("created_at"),
                }
                for p in payments[:5]
            ],
            "ai_interaction_history": ai_interactions[-15:],  # Last 15 events
            "trigger": {
                "intent": intent,
                "message": trigger_message[:500],
                "sentiment": sentiment,
            },
            "prior_escalations": len(escalations),
            "recommended_approach": recommended,
        }

        # Audit the briefing generation
        self._audit("orchestrator", "generate_briefing",
                   {"policy_id": policy_id, "intent": intent},
                   {"briefing_sections": list(briefing.keys())})

        return briefing

    def generate_briefing(self, policy_id: str) -> dict:
        """Public API: Generate a briefing note for any policy (for Human Queue dashboard)."""
        policy = self.db.get_policy(policy_id)
        if not policy:
            return {"error": f"Policy {policy_id} not found"}

        customer = self.db.get_customer(policy["customer_id"])
        if not customer:
            return {"error": "Customer not found"}

        escalations = self.db.get_escalations_by_policy(policy_id)
        last_esc = escalations[0] if escalations else {}

        return self._generate_briefing_note(
            policy_id, customer, policy,
            intent=last_esc.get("reason", "REVIEW").split(":")[0].strip(),
            sentiment={"sentiment": "unknown", "should_escalate": True},
            trigger_message=last_esc.get("reason", "Manual review requested"),
        )

    def _dispatch_email(self, touch: dict) -> dict:
        """Dispatch a touch via the email agent."""
        policy = self.db.get_policy(touch["policy_id"])
        customer = self.db.get_customer(policy["customer_id"]) if policy else None
        if not policy or not customer:
            return {"error": "Policy or customer not found"}
        journey = self.db.get_journey(touch["policy_id"])
        return self.email_agent.generate_email(policy, customer, touch, journey)

    def _dispatch_whatsapp(self, touch: dict) -> dict:
        """Dispatch a touch via the WhatsApp agent."""
        return self.whatsapp_agent.send_reminder(touch["policy_id"], touch)

    def _dispatch_voice(self, touch: dict) -> dict:
        """Dispatch a touch via the ElevenLabs voice agent."""
        return self.elevenlabs_agent.trigger_outbound_call(touch["policy_id"])

    def _audit(self, actor: str, action: str, req: Any = None, res: Any = None):
        """Write to audit log."""
        try:
            self.db.audit(actor, action, req, res)
        except Exception:
            pass

    def _result(self, policy_id: str, action: str, rationale: str,
                state: str = "", customer: dict | None = None,
                policy: dict | None = None, **extra) -> dict:
        """Build a standardised orchestration result."""
        result = {
            "policy_id": policy_id,
            "action": action,
            "rationale": rationale,
            "state": state,
        }
        if customer:
            result["customer_name"] = customer.get("full_name")
            result["segment"] = customer.get("segment")
        if policy:
            result["product"] = policy.get("product")
            result["premium"] = policy.get("premium_amount")
            result["due_date"] = policy.get("due_date")
            result["risk_score"] = policy.get("risk_score")
        result.update(extra)
        return result


if __name__ == "__main__":
    orch = RenewalOrchestrator()
    print("=== Orchestrate POL-1009 ===")
    r = orch.orchestrate("POL-1009")
    print(json.dumps(r, indent=2, default=str))
    print("\n=== Handle reply ===")
    r2 = orch.handle_customer_reply("POL-1009", "whatsapp", "The premium is too high for me")
    print(f"Intent: {r2.get('intent')}")
    print(f"Response: {r2.get('response_to_customer', '')[:100]}")
