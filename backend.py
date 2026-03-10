"""
RenewAI – Flask REST API Backend
========================================
Exposes 20+ endpoints for the dashboard UI, orchestration engine,
and all three channel agents (Email, WhatsApp, Voice).
"""

import json
import os
import uuid
from datetime import datetime

from dotenv import load_dotenv
from flask import Flask, jsonify, request, send_file, send_from_directory
from flask_cors import CORS

load_dotenv()

# ── Initialise App ───────────────────────────────────────────────────────

app = Flask(__name__, static_folder=".", static_url_path="")
CORS(app)

# ── Initialise Services ─────────────────────────────────────────────────

from database import DB
from orchestrator import RenewalOrchestrator
from email_agent import EmailAgent
from whatsapp_agent import WhatsAppAgent
from voice_agent import VoiceAgent
from elevenlabs_agent import ElevenLabsAgent

db = DB()
orchestrator = RenewalOrchestrator(db=db)
email_agent = EmailAgent()
whatsapp_agent = WhatsAppAgent(db=db)
voice_agent = VoiceAgent(db=db)
elevenlabs_agent = ElevenLabsAgent(db=db)


# ── Response Helper ──────────────────────────────────────────────────────

def api_response(success=True, data=None, message="", status=200):
    return jsonify({"success": success, "message": message, "data": data}), status


# ════════════════════════════════════════════════════════════════════════
# PAGE SERVING
# ════════════════════════════════════════════════════════════════════════

@app.route("/")
def index():
    return send_file("frontend.html")


@app.route("/payment/<policy_id>")
def payment_page(policy_id):
    return send_file("payment.html")


# ════════════════════════════════════════════════════════════════════════
# HEALTH
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/health")
def health():
    from gemini_integration import GeminiIntegration
    g = GeminiIntegration()
    return api_response(data={
        "status": "healthy",
        "service": "RenewAI",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "gemini_enabled": g.enabled,
        "gemini_model": os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
    })


# ════════════════════════════════════════════════════════════════════════
# DASHBOARD
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/dashboard")
def dashboard():
    stats = db.get_dashboard_stats()
    return api_response(data=stats)


# ════════════════════════════════════════════════════════════════════════
# CUSTOMERS
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/customers")
def get_customers():
    segment = request.args.get("segment")
    language = request.args.get("language")
    customers = db.search_customers(segment=segment, language=language)
    return api_response(data=customers)


@app.route("/api/customer/<customer_id>")
def get_customer(customer_id):
    profile = db.get_customer_profile(customer_id)
    if not profile:
        return api_response(False, message="Customer not found", status=404)
    return api_response(data=profile)


# ════════════════════════════════════════════════════════════════════════
# POLICIES
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/policies/due")
def get_due_policies():
    days = request.args.get("days", 30, type=int)
    policies = db.get_due_policies(within_days=days)
    return api_response(data=policies)


@app.route("/api/policies/lapsed")
def get_lapsed_policies():
    policies = db.get_lapsed_policies()
    return api_response(data=policies)


@app.route("/api/policy/<policy_id>")
def get_policy(policy_id):
    policy = db.get_policy(policy_id)
    if not policy:
        return api_response(False, message="Policy not found", status=404)
    payments = db.get_payments_by_policy(policy_id)
    journey = db.get_journey(policy_id)
    escalations = db.get_escalations_by_policy(policy_id)
    return api_response(data={
        "policy": policy,
        "payments": payments,
        "journey": journey,
        "escalations": escalations,
    })


# ════════════════════════════════════════════════════════════════════════
# ESCALATIONS
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/escalations")
def get_escalations():
    status = request.args.get("status")
    escalations = db.get_escalations(status=status)
    return api_response(data=escalations)


# ════════════════════════════════════════════════════════════════════════
# AUDIT LOG
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/audit")
def get_audit():
    actor = request.args.get("actor")
    limit = request.args.get("limit", 50, type=int)
    logs = db.get_audit_log(actor=actor, limit=limit)
    return api_response(data=logs)


# ════════════════════════════════════════════════════════════════════════
# ORCHESTRATION
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/orchestrate", methods=["POST"])
def orchestrate():
    body = request.get_json(silent=True) or {}
    policy_id = body.get("policy_id")
    if not policy_id:
        return api_response(False, message="policy_id is required", status=400)
    result = orchestrator.orchestrate(policy_id)
    return api_response(data=result)


@app.route("/api/orchestrate/batch", methods=["POST"])
def orchestrate_batch():
    body = request.get_json(silent=True) or {}
    within_days = body.get("within_days", 45)
    result = orchestrator.run_daily_batch(within_days=within_days)
    return api_response(data=result)


@app.route("/api/reply", methods=["POST"])
def handle_reply():
    body = request.get_json(silent=True) or {}
    policy_id = body.get("policy_id")
    channel = body.get("channel", "whatsapp")
    message = body.get("message", "")

    if not policy_id:
        return api_response(False, message="policy_id is required", status=400)
    if not message:
        return api_response(False, message="message is required", status=400)

    result = orchestrator.handle_customer_reply(policy_id, channel, message)
    return api_response(data=result)


# ════════════════════════════════════════════════════════════════════════
# PAYMENT CONFIRMATION (SIMULATION)
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/payment/confirm", methods=["POST"])
def confirm_payment():
    body = request.get_json(silent=True) or {}
    policy_id = body.get("policy_id")
    
    if not policy_id:
        return api_response(False, message="policy_id is required", status=400)
        
    policy = db.get_policy(policy_id)
    if not policy:
        return api_response(False, message="Policy not found", status=404)
        
    # 1. Record the payment in DB
    db.record_payment(
        policy_id=policy_id,
        amount=policy["premium_amount"],
        status="paid",
        txn_ref=f"SIM-{uuid.uuid4().hex[:8].upper()}"
    )
    
    # 2. Update policy status to active
    db.update_policy_status(policy_id, "active")
    
    # 3. Log event in journey
    db.log_event(policy_id, "system", "payment_received", {
        "amount": policy["premium_amount"],
        "channel": "web_portal"
    })
    
    # 4. Success result
    return api_response(data={
        "policy_id": policy_id,
        "status": "active",
        "message": "Payment confirmed and policy renewed."
    })


# ════════════════════════════════════════════════════════════════════════
# SCHEDULED TOUCHES
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/touch/plan", methods=["POST"])
def plan_touch():
    body = request.get_json(silent=True) or {}
    required = ["policy_id", "channel", "schedule_at", "language", "tone", "content_brief"]
    missing = [f for f in required if not body.get(f)]
    if missing:
        return api_response(False, message=f"Missing required fields: {missing}", status=400)

    result = orchestrator.plan_next_touch(
        policy_id=body["policy_id"],
        channel=body["channel"],
        schedule_at=body["schedule_at"],
        language=body["language"],
        tone=body["tone"],
        content_brief=body["content_brief"],
    )
    if "error" in result:
        return api_response(False, message=result["error"], status=400)
    return api_response(data=result)


@app.route("/api/touches/pending")
def get_pending_touches():
    before = request.args.get("before")
    touches = db.get_pending_touches(before=before)
    return api_response(data=touches)


@app.route("/api/touches/<policy_id>")
def get_touches_for_policy(policy_id):
    touches = db.get_touches_by_policy(policy_id)
    return api_response(data=touches)


@app.route("/api/touches/execute", methods=["POST"])
def execute_touches():
    body = request.get_json(silent=True) or {}
    as_of = body.get("as_of")
    results = orchestrator.execute_pending_touches(as_of=as_of)
    return api_response(data={"total": len(results), "results": results})


@app.route("/api/touch/cancel", methods=["POST"])
def cancel_touch():
    body = request.get_json(silent=True) or {}
    touch_id = body.get("touch_id")
    if not touch_id:
        return api_response(False, message="touch_id is required", status=400)
    result = orchestrator.cancel_touch(touch_id)
    return api_response(data=result)


# ════════════════════════════════════════════════════════════════════════
# EMAIL AGENT
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/email/generate", methods=["POST"])
def generate_email():
    body = request.get_json(silent=True) or {}
    policy_id = body.get("policy_id")
    if not policy_id:
        return api_response(False, message="policy_id is required", status=400)

    policy = db.get_policy(policy_id)
    if not policy:
        return api_response(False, message="Policy not found", status=404)

    customer = db.get_customer(policy["customer_id"])
    journey = db.get_journey(policy_id)

    touch = {
        "content_brief": body.get("content_brief", "Renewal reminder"),
        "tone": body.get("tone", "warm"),
        "language": body.get("language", customer.get("language_pref", "en-IN")),
    }

    result = email_agent.generate_email(policy, customer, touch, journey)
    return api_response(data=result)


@app.route("/api/email/preview/<policy_id>")
def preview_email(policy_id):
    policy = db.get_policy(policy_id)
    if not policy:
        return "Policy not found", 404

    customer = db.get_customer(policy["customer_id"])
    journey = db.get_journey(policy_id)
    touch = {"content_brief": "Preview", "tone": "warm",
             "language": customer.get("language_pref", "en-IN")}
    result = email_agent.generate_email(policy, customer, touch, journey)
    return result.get("body_html", "<p>No email generated</p>"), 200, {"Content-Type": "text/html"}


# ════════════════════════════════════════════════════════════════════════
# WHATSAPP AGENT
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/whatsapp/handle", methods=["POST"])
def whatsapp_handle():
    body = request.get_json(silent=True) or {}
    policy_id = body.get("policy_id")
    message = body.get("message", "")

    if not policy_id:
        return api_response(False, message="policy_id is required", status=400)
    if not message:
        return api_response(False, message="message is required", status=400)

    result = whatsapp_agent.handle_message(policy_id, message)
    return api_response(data=result)


@app.route("/api/whatsapp/remind", methods=["POST"])
def whatsapp_remind():
    body = request.get_json(silent=True) or {}
    policy_id = body.get("policy_id")
    if not policy_id:
        return api_response(False, message="policy_id is required", status=400)

    touch = {
        "content_brief": body.get("content_brief", "Renewal reminder"),
        "tone": body.get("tone", "warm"),
        "language": body.get("language", "en-IN"),
    }
    result = whatsapp_agent.send_reminder(policy_id, touch)
    return api_response(data=result)


# ════════════════════════════════════════════════════════════════════════
# VOICE AGENT
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/voice/elevenlabs/trigger", methods=["POST"])
def voice_elevenlabs_trigger():
    """Manually trigger an ElevenLabs outbound call."""
    body = request.get_json(silent=True) or {}
    policy_id = body.get("policy_id")
    if not policy_id:
        return api_response(False, message="policy_id is required", status=400)
    result = elevenlabs_agent.trigger_outbound_call(policy_id)
    return api_response(data=result)


@app.route("/api/voice/objection", methods=["POST"])
def voice_objection():
    """Handle a voice-call objection; escalates after 3 unresolved."""
    body = request.get_json(silent=True) or {}
    policy_id = body.get("policy_id")
    objection = body.get("objection", "")

    if not policy_id:
        return api_response(False, message="policy_id is required", status=400)
    if not objection:
        return api_response(False, message="objection text is required", status=400)

    result = voice_agent.handle_objection(policy_id, objection)
    return api_response(data=result)


# ════════════════════════════════════════════════════════════════════════
# HUMAN QUEUE BRIEFING
# ════════════════════════════════════════════════════════════════════════

@app.route("/api/briefing/<policy_id>")
def get_briefing(policy_id):
    """Generate a structured briefing note for the human agent queue."""
    briefing = orchestrator.generate_briefing(policy_id)
    if briefing.get("error"):
        return api_response(False, message=briefing["error"], status=404)
    return api_response(data=briefing)


# ════════════════════════════════════════════════════════════════════════
# ERROR HANDLERS
# ════════════════════════════════════════════════════════════════════════

@app.errorhandler(404)
def not_found(e):
    return api_response(False, message="Endpoint not found", status=404)


@app.errorhandler(500)
def server_error(e):
    return api_response(False, message="Internal server error", status=500)


# ════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    port = int(os.getenv("PORT", 9000))
    host = os.getenv("HOST", "0.0.0.0")
    debug = os.getenv("DEBUG", "False").lower() == "true"

    banner = f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   🚀  RenewAI – Insurance Renewal Orchestration Platform     ║
║   ─────────────────────────────────────────────────────────   ║
║   Server:   http://{host}:{port}                             ║
║   Gemini:   {os.getenv('GEMINI_MODEL', 'gemini-2.5-flash')}                          ║
║   Database: renewai.db                                       ║
║   Version:  2.0.0                                            ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝
"""
    print(banner)
    app.run(host=host, port=port, debug=debug)
