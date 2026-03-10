"""
RenewAI – Email Agent
===========================
Generates personalised, IRDAI-compliant renewal emails using Gemini 2.5 Flash
with strict grounding-facts validation and branded HTML templates.
"""

import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from gemini_integration import GeminiIntegration

load_dotenv()


class EmailAgent:
    """Specialised agent for generating insurance renewal emails."""

    SYSTEM_PROMPT = (
        "You are Suraksha Life Insurance's AI Email Agent generating renewal emails.\n"
        "Rules:\n"
        "1. ONLY use verified facts from context — never invent data.\n"
        "2. Body should be 120-160 words.\n"
        "3. Include a clear call-to-action (CTA) button.\n"
        "4. Mention UPI QR payment option if applicable.\n"
        "5. Never provide financial advice.\n"
        "6. Be empathetic but concise.\n"
        "7. Include contact info and opt-out.\n"
        "8. Use customer's preferred language.\n"
        "9. Be transparent that this is an AI-generated communication.\n"
        "10. Always offer 'speak to a human' option.\n"
        "11. Personalise with first name.\n\n"
        "Output JSON:\n"
        '{"subject": "...", "body_text": "...", "body_html": "...", "tone": "...", "compliance_flags": []}\n'
    )

    PRODUCT_BENEFITS = {
        "term": {
            "name": "Term Life Shield",
            "benefits": [
                "₹1 Crore life cover for your family's security",
                "Tax benefits under Section 80C (up to ₹1.5L) and Section 10(10D)",
                "Critical illness and accidental death riders available",
                "Flexible premium payment options",
            ],
            "emi_available": True,
            "grace_days": 30,
            "upi_id": "surakshalife.term@upi",
        },
        "endowment": {
            "name": "Endowment Plus",
            "benefits": [
                "Guaranteed maturity benefit with annual bonuses",
                "Life cover throughout the policy term",
                "Loan facility against accumulated value",
                "Tax benefits under Section 80C and 10(10D)",
            ],
            "emi_available": True,
            "grace_days": 30,
            "upi_id": "surakshalife.endow@upi",
        },
        "ulip": {
            "name": "Wealth Builder ULIP",
            "benefits": [
                "Market-linked returns with professional fund management",
                "Free fund switching (up to 4 switches/year)",
                "Partial withdrawal after 5 years",
                "Life cover with investment growth",
            ],
            "emi_available": False,
            "grace_days": 15,
            "upi_id": "surakshalife.wealth@upi",
        },
    }

    BASE_PAYMENT_URL = os.getenv("BASE_URL", "http://localhost:9000") + "/payment"

    def __init__(self, db=None):
        self.db = db
        self.gemini = GeminiIntegration(system_instruction=self.SYSTEM_PROMPT)

    # ── Public API ───────────────────────────────────────────────────────
    def generate_email(self, policy: dict, customer: dict,
                       touch: dict, journey_events: list | None = None) -> dict:
        """Generate a personalised renewal email for a policy."""
        # Grounding-facts validation
        if not policy.get("premium_amount") or not policy.get("due_date"):
            return {
                "error": "MISSING_VERIFIED_FACTS",
                "message": "Cannot generate email: premium_amount and due_date are required",
                "policy_id": policy.get("policy_id"),
            }

        product = policy.get("product", "term")
        benefits = self._get_benefits(product)
        payment_url = self._build_payment_url(policy["policy_id"], product)
        language = touch.get("language", customer.get("language_pref", "en-IN"))
        tone = touch.get("tone", "warm")

        # Build formatted context for Gemini
        recent_events = ""
        if journey_events:
            recent_events = "\n".join(
                f"- {e.get('timestamp','')}: {e.get('channel','')} → {e.get('event_type','')}"
                for e in journey_events[:5]
            )

        prompt = f"""Generate a renewal email for this policyholder.

VERIFIED FACTS (use ONLY these):
- Customer name: {customer.get('full_name', 'Valued Customer')}
- Policy ID: {policy['policy_id']}
- Product: {benefits['name']}
- Premium: ₹{policy['premium_amount']:,}
- Due date: {policy['due_date']}
- Language: {language}
- Tone: {tone}

PRODUCT BENEFITS:
{chr(10).join('• ' + b for b in benefits['benefits'])}

EMI available: {'Yes' if benefits['emi_available'] else 'No'}
Grace period: {benefits['grace_days']} days
Payment URL: {payment_url}
UPI: {benefits['upi_id']}

{'Recent journey events:' + chr(10) + recent_events if recent_events else ''}
{'Content brief: ' + touch.get('content_brief', '') if touch.get('content_brief') else ''}

Generate JSON with: subject, body_text, body_html (with inline CSS), tone, compliance_flags"""

        try:
            raw_response = self.gemini._call(prompt)
            email_data = self.gemini._parse_json(raw_response)

            if "subject" in email_data:
                html = self._render_html(email_data, customer, policy, payment_url)
                footer = self._build_footer(customer, language)
                return {
                    "subject": email_data["subject"],
                    "body_text": email_data.get("body_text", ""),
                    "body_html": html + footer,
                    "tone": email_data.get("tone", tone),
                    "language": language,
                    "payment_url": payment_url,
                    "metadata": {
                        "product": benefits["name"],
                        "policy_id": policy["policy_id"],
                        "generated_by": "gemini",
                        "timestamp": datetime.utcnow().isoformat(),
                    },
                    "compliance_flags": email_data.get("compliance_flags", []),
                }
        except Exception as e:
            print(f"[EmailAgent] Generation error: {e}")

        # Fallback
        return self._fallback_email(policy, customer, touch)

    def generate_batch(self, touches: list, db=None) -> list:
        """Generate emails for a batch of scheduled touches."""
        results = []
        for touch in touches:
            if not db:
                results.append({"error": "No DB instance provided"})
                continue
            policy = db.get_policy(touch.get("policy_id", ""))
            if not policy:
                results.append({"error": f"Policy {touch.get('policy_id')} not found"})
                continue
            customer = db.get_customer(policy["customer_id"])
            if not customer:
                results.append({"error": f"Customer not found for {policy['policy_id']}"})
                continue
            journey = db.get_journey(policy["policy_id"])
            result = self.generate_email(policy, customer, touch, journey)
            results.append(result)
        return results

    # ── Helpers ───────────────────────────────────────────────────────────
    def _get_benefits(self, product_type: str) -> dict:
        return self.PRODUCT_BENEFITS.get(product_type, self.PRODUCT_BENEFITS["term"])

    def _build_payment_url(self, policy_id: str, product_type: str) -> str:
        return f"{self.BASE_PAYMENT_URL}/{policy_id}?product={product_type}"

    def _render_html(self, email_data: dict, customer: dict,
                     policy: dict, payment_url: str) -> str:
        """Wrap Gemini-generated content in a branded HTML template."""
        body_html = email_data.get("body_html", email_data.get("body_text", ""))
        first_name = customer.get("full_name", "Customer").split()[0]
        product = self.PRODUCT_BENEFITS.get(policy.get("product", "term"), {})

        return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background:#f4f6f8;font-family:'Segoe UI',Roboto,Arial,sans-serif;">
<div style="max-width:600px;margin:0 auto;background:#ffffff;border-radius:12px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1a237e,#4a148c);padding:28px 32px;text-align:center;">
    <h1 style="color:#ffffff;margin:0;font-size:24px;letter-spacing:1px;">Suraksha Life</h1>
    <p style="color:rgba(255,255,255,0.8);margin:6px 0 0;font-size:13px;">Protecting What Matters Most</p>
  </div>
  <!-- Body -->
  <div style="padding:32px;">
    {body_html}
    <!-- CTA Button -->
    <div style="text-align:center;margin:28px 0;">
      <a href="{payment_url}" style="display:inline-block;padding:14px 36px;background:linear-gradient(135deg,#4CAF50,#2E7D32);color:#fff;text-decoration:none;border-radius:8px;font-size:16px;font-weight:600;box-shadow:0 4px 16px rgba(46,125,50,0.3);">
        Renew Now – ₹{policy.get('premium_amount',0):,}
      </a>
    </div>
    <!-- Product Benefits -->
    <div style="background:#f8f9fa;padding:20px;border-radius:8px;margin:20px 0;">
      <h3 style="margin:0 0 12px;color:#1a237e;font-size:15px;">✨ Your {product.get('name', 'Plan')} Benefits</h3>
      <ul style="margin:0;padding-left:18px;color:#555;font-size:13px;line-height:1.8;">
        {''.join(f'<li>{b}</li>' for b in product.get('benefits', []))}
      </ul>
    </div>
    <!-- Payment Info -->
    <div style="background:#e8f5e9;padding:16px;border-radius:8px;border-left:4px solid #4CAF50;margin:16px 0;">
      <p style="margin:0;font-size:13px;color:#2E7D32;">
        💳 <strong>Quick Pay via UPI:</strong> {product.get('upi_id', '')}
        {' | 📱 EMI options available' if product.get('emi_available') else ''}
      </p>
    </div>
  </div>
"""

    def _build_footer(self, customer: dict, language: str = "en-IN") -> str:
        """IRDAI-compliant email footer with unsubscribe + multi-language."""
        footers = {
            "en-IN": (
                "This is an automated AI-generated communication from Suraksha Life Insurance Co. Ltd. "
                "(IRDAI Reg. No. XXX). For queries, call 1800-XXX-XXXX (toll-free) or email "
                "support@surakshalife.com. To unsubscribe from renewal reminders, "
                '<a href="#unsubscribe" style="color:#1a73e8;">click here</a>.'
            ),
            "hi-IN": (
                "यह सुरक्षा लाइफ इंश्योरेंस कंपनी लिमिटेड (IRDAI रजि. सं. XXX) का "
                "एक स्वचालित AI-जनित संचार है। प्रश्नों के लिए 1800-XXX-XXXX (टोल-फ्री) पर कॉल करें। "
                'अनसब्सक्राइब करने के लिए <a href="#unsubscribe" style="color:#1a73e8;">यहाँ क्लिक करें</a>।'
            ),
            "ta-IN": (
                "இது சுரக்ஷா லைஃப் இன்ஷூரன்ஸ் நிறுவனத்தின் AI தானியக்க தகவல் (IRDAI பதிவு எண் XXX). "
                'விலக <a href="#unsubscribe" style="color:#1a73e8;">இங்கே கிளிக் செய்யவும்</a>.'
            ),
            "gu-IN": (
                "સુરક્ષા લાઇફ ઇન્શ્યોરન્સ કંપનીનો AI સ્વયંસંચાલિત સંદેશ (IRDAI નોં. XXX). "
                'અનસબ્સ્ક્રાઇબ કરવા <a href="#unsubscribe" style="color:#1a73e8;">અહીં ક્લિક કરો</a>.'
            ),
            "ml-IN": (
                "സുരക്ഷ ലൈഫ് ഇൻഷുറൻസ് കമ്പനിയുടെ AI സ്വയംചാലിത സന്ദേശം (IRDAI രജി. നമ്പർ XXX). "
                'അൺസബ്‌സ്‌ക്രൈബ് ചെയ്യാൻ <a href="#unsubscribe" style="color:#1a73e8;">ഇവിടെ ക്ലിക്ക് ചെയ്യുക</a>.'
            ),
        }
        footer_text = footers.get(language, footers["en-IN"])
        return f"""
  <!-- Footer -->
  <div style="background:#f8f9fa;padding:20px 32px;border-top:1px solid #e0e0e0;">
    <p style="margin:0;font-size:11px;color:#888;line-height:1.6;">
      {footer_text}
    </p>
    <p style="margin:8px 0 0;font-size:10px;color:#aaa;">
      © 2026 Suraksha Life Insurance Co. Ltd. All rights reserved. | Policy ID: {customer.get('customer_id', '')}
    </p>
  </div>
</div>
</body>
</html>"""

    def _fallback_email(self, policy: dict, customer: dict,
                        touch: dict, error: str | None = None) -> dict:
        """Template-based fallback if Gemini is unavailable."""
        first_name = customer.get("full_name", "Customer").split()[0]
        product = self.PRODUCT_BENEFITS.get(policy.get("product", "term"), {})
        payment_url = self._build_payment_url(policy["policy_id"], policy.get("product", "term"))

        subject = f"Renewal Reminder: Your {product.get('name', 'Policy')} – ₹{policy.get('premium_amount', 0):,} due {policy.get('due_date', 'soon')}"
        body_text = (
            f"Dear {first_name},\n\n"
            f"This is a friendly reminder that your {product.get('name', 'policy')} "
            f"(Policy: {policy['policy_id']}) renewal of ₹{policy.get('premium_amount', 0):,} "
            f"is due on {policy.get('due_date', 'soon')}.\n\n"
            f"Your coverage protects what matters most to your family. "
            f"{'EMI payment options are available. ' if product.get('emi_available') else ''}"
            f"You have a {product.get('grace_days', 30)}-day grace period.\n\n"
            f"Pay now: {payment_url}\n"
            f"UPI: {product.get('upi_id', '')}\n\n"
            f"Need help? Call 1800-XXX-XXXX or reply to this email.\n\n"
            f"Warm regards,\nSuraksha Life Insurance"
        )

        body_html = f"<p>Dear {first_name},</p><p>{body_text.replace(chr(10), '<br>')}</p>"
        html = self._render_html(
            {"body_html": body_html, "subject": subject},
            customer, policy, payment_url,
        )
        footer = self._build_footer(customer, touch.get("language", "en-IN"))

        return {
            "subject": subject,
            "body_text": body_text,
            "body_html": html + footer,
            "tone": touch.get("tone", "warm"),
            "language": touch.get("language", "en-IN"),
            "payment_url": payment_url,
            "metadata": {
                "product": product.get("name"),
                "policy_id": policy["policy_id"],
                "generated_by": "fallback",
                "timestamp": datetime.utcnow().isoformat(),
                "fallback_reason": error,
            },
            "compliance_flags": [],
        }


if __name__ == "__main__":
    from database import DB
    db = DB()
    agent = EmailAgent(db=db)
    policy = db.get_policy("POL-1001")
    customer = db.get_customer(policy["customer_id"])
    touch = {"content_brief": "Renewal reminder", "tone": "warm", "language": "en-IN"}
    result = agent.generate_email(policy, customer, touch)
    print(f"Subject: {result.get('subject', 'N/A')}")
    print(f"Has HTML: {len(result.get('body_html', '')) > 0}")
    print(f"Generated by: {result.get('metadata', {}).get('generated_by', 'N/A')}")
