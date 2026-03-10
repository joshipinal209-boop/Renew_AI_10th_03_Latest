"""
RenewAI – SQLite Data-Access Layer
=============================================
Thin wrapper around SQLite with domain-specific query methods for
customers, policies, payments, journey events, escalations,
scheduled touches, and the audit log.
"""

import json
import os
import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

from pii_masking import mask_for_audit


def _new_id(prefix: str = "") -> str:
    return f"{prefix}{uuid.uuid4().hex[:8]}"


class DB:
    """SQLite data layer for the RenewAI platform."""

    def __init__(self, db_path: str | None = None):
        self.db_path = db_path or os.path.join(os.path.dirname(__file__) or ".", "renewai.db")
        self.db: sqlite3.Connection | None = None
        self._ensure_db()

    # ── Setup ────────────────────────────────────────────────────────────
    def _ensure_db(self):
        needs_seed = not os.path.exists(self.db_path)
        self.db = sqlite3.connect(self.db_path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA foreign_keys=ON")

        # Always run schema (IF NOT EXISTS makes it safe)
        schema_path = os.path.join(os.path.dirname(__file__) or ".", "schema.sql")
        if os.path.exists(schema_path):
            self.db.executescript(Path(schema_path).read_text())

        if needs_seed:
            seed_path = os.path.join(os.path.dirname(__file__) or ".", "seed_data.sql")
            if os.path.exists(seed_path):
                self.db.executescript(Path(seed_path).read_text())
                self.db.commit()

    def reset(self):
        """Drop and recreate the database."""
        if self.db:
            self.db.close()
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
        self._ensure_db()

    def _rows(self, sql: str, params: tuple | list = ()) -> list[dict]:
        cur = self.db.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]

    def _row(self, sql: str, params: tuple | list = ()) -> dict | None:
        cur = self.db.execute(sql, params)
        r = cur.fetchone()
        return dict(r) if r else None

    # ── Customers ────────────────────────────────────────────────────────
    def get_customer(self, customer_id: str) -> dict | None:
        return self._row("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))

    def get_all_customers(self) -> list[dict]:
        return self._rows("SELECT * FROM customers ORDER BY full_name")

    def search_customers(self, segment: str | None = None, language: str | None = None) -> list[dict]:
        sql = "SELECT * FROM customers WHERE 1=1"
        params: list = []
        if segment:
            sql += " AND segment = ?"
            params.append(segment)
        if language:
            sql += " AND language_pref = ?"
            params.append(language)
        sql += " ORDER BY full_name"
        return self._rows(sql, params)

    def upsert_customer(self, data: dict) -> dict:
        cid = data.get("customer_id") or _new_id("CUST-")
        sql = """
        INSERT INTO customers (customer_id, full_name, age, language_pref,
                              whatsapp_opt_in, email, phone, segment,
                              preferred_contact_window)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(customer_id) DO UPDATE SET
            full_name=excluded.full_name, age=excluded.age,
            language_pref=excluded.language_pref,
            whatsapp_opt_in=excluded.whatsapp_opt_in,
            email=excluded.email, phone=excluded.phone,
            segment=excluded.segment,
            preferred_contact_window=excluded.preferred_contact_window
        """
        self.db.execute(sql, (
            cid, data.get("full_name"), data.get("age"),
            data.get("language_pref", "en-IN"),
            data.get("whatsapp_opt_in", 1),
            data.get("email"), data.get("phone"),
            data.get("segment"), data.get("preferred_contact_window"),
        ))
        self.db.commit()
        return self.get_customer(cid)

    # ── Policies ─────────────────────────────────────────────────────────
    def get_policy(self, policy_id: str) -> dict | None:
        return self._row("SELECT * FROM policies WHERE policy_id = ?", (policy_id,))

    def get_policies_by_customer(self, customer_id: str) -> list[dict]:
        return self._rows(
            "SELECT * FROM policies WHERE customer_id = ? ORDER BY due_date",
            (customer_id,),
        )

    def get_due_policies(self, within_days: int = 30) -> list[dict]:
        cutoff = (datetime(2026, 3, 5) + timedelta(days=within_days)).strftime("%Y-%m-%d")
        sql = """
        SELECT p.*, c.full_name, c.segment, c.language_pref,
               c.whatsapp_opt_in, c.email, c.phone
        FROM policies p
        JOIN customers c ON p.customer_id = c.customer_id
        WHERE p.status IN ('due','active')
          AND p.due_date <= ?
        ORDER BY p.due_date ASC
        """
        return self._rows(sql, (cutoff,))

    def get_lapsed_policies(self) -> list[dict]:
        sql = """
        SELECT p.*, c.full_name, c.segment
        FROM policies p
        JOIN customers c ON p.customer_id = c.customer_id
        WHERE p.status = 'lapsed'
        ORDER BY p.due_date DESC
        """
        return self._rows(sql)

    def update_policy_status(self, policy_id: str, status: str):
        self.db.execute(
            "UPDATE policies SET status = ? WHERE policy_id = ?",
            (status, policy_id),
        )
        self.db.commit()

    def upsert_policy(self, data: dict) -> dict:
        pid = data.get("policy_id") or _new_id("POL-")
        sql = """
        INSERT INTO policies (policy_id, customer_id, product, premium_amount,
                             due_date, status, risk_score)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(policy_id) DO UPDATE SET
            customer_id=excluded.customer_id, product=excluded.product,
            premium_amount=excluded.premium_amount, due_date=excluded.due_date,
            status=excluded.status, risk_score=excluded.risk_score
        """
        self.db.execute(sql, (
            pid, data["customer_id"], data["product"],
            data.get("premium_amount"), data.get("due_date"),
            data.get("status", "active"), data.get("risk_score", 0.0),
        ))
        self.db.commit()
        return self.get_policy(pid)

    # ── Payments ─────────────────────────────────────────────────────────
    def get_payments_by_policy(self, policy_id: str) -> list[dict]:
        return self._rows(
            "SELECT * FROM payments WHERE policy_id = ? ORDER BY paid_at DESC",
            (policy_id,),
        )

    def record_payment(self, policy_id: str, amount: int,
                       status: str = "pending", txn_ref: str | None = None) -> dict:
        pay_id = _new_id("PAY-")
        paid_at = datetime.utcnow().isoformat() if status == "paid" else None
        self.db.execute(
            "INSERT INTO payments (payment_id, policy_id, amount, status, txn_ref, paid_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (pay_id, policy_id, amount, status, txn_ref, paid_at),
        )
        self.db.commit()
        return {"payment_id": pay_id, "status": status}

    def update_payment_status(self, payment_id: str, status: str,
                              txn_ref: str | None = None):
        sql = "UPDATE payments SET status = ?"
        params: list = [status]
        if txn_ref:
            sql += ", txn_ref = ?"
            params.append(txn_ref)
        if status == "paid":
            sql += ", paid_at = ?"
            params.append(datetime.utcnow().isoformat())
        sql += " WHERE payment_id = ?"
        params.append(payment_id)
        self.db.execute(sql, params)
        self.db.commit()

    # ── Journey Events ───────────────────────────────────────────────────
    def get_journey(self, policy_id: str) -> list[dict]:
        return self._rows(
            "SELECT * FROM journey_events WHERE policy_id = ? ORDER BY timestamp DESC",
            (policy_id,),
        )

    def log_event(self, policy_id: str, channel: str, event_type: str,
                  payload: Any = None) -> str:
        eid = _new_id("EVT-")
        self.db.execute(
            "INSERT INTO journey_events (event_id, policy_id, timestamp, channel, event_type, payload) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (eid, policy_id, datetime.utcnow().isoformat(), channel, event_type,
             json.dumps(payload) if payload else None),
        )
        self.db.commit()
        return eid

    # ── Escalations ──────────────────────────────────────────────────────
    def get_escalations(self, status: str | None = None) -> list[dict]:
        if status:
            return self._rows(
                "SELECT * FROM escalations WHERE status = ? ORDER BY created_at DESC",
                (status,),
            )
        return self._rows("SELECT * FROM escalations ORDER BY priority ASC, created_at DESC")

    def get_escalations_by_policy(self, policy_id: str) -> list[dict]:
        return self._rows(
            "SELECT * FROM escalations WHERE policy_id = ? ORDER BY created_at DESC",
            (policy_id,),
        )

    def create_escalation(self, policy_id: str, reason: str,
                          priority: int = 3, assigned_to: str | None = None) -> dict:
        eid = _new_id("ESC-")
        self.db.execute(
            "INSERT INTO escalations (escalation_id, policy_id, reason, priority, assigned_to) "
            "VALUES (?, ?, ?, ?, ?)",
            (eid, policy_id, reason, priority, assigned_to),
        )
        self.db.commit()
        return {"escalation_id": eid, "policy_id": policy_id, "priority": priority}

    def update_escalation_status(self, escalation_id: str, status: str):
        self.db.execute(
            "UPDATE escalations SET status = ? WHERE escalation_id = ?",
            (status, escalation_id),
        )
        self.db.commit()

    def update_escalation(self, escalation_id: str, **kwargs):
        """Update escalation fields dynamically."""
        if not kwargs:
            return
        keys = [f"{k} = ?" for k in kwargs.keys()]
        values = list(kwargs.values())
        values.append(escalation_id)
        sql = f"UPDATE escalations SET {', '.join(keys)} WHERE escalation_id = ?"
        self.db.execute(sql, tuple(values))
        self.db.commit()

    # ── Scheduled Touches ────────────────────────────────────────────────
    def schedule_touch(self, policy_id: str, channel: str, schedule_at: str,
                       language: str = "en-IN", tone: str = "warm",
                       content_brief: str = "") -> dict:
        tid = _new_id("TCH-")
        self.db.execute(
            """INSERT INTO scheduled_touches
               (touch_id, policy_id, channel, schedule_at, language, tone, content_brief)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (tid, policy_id, channel, schedule_at, language, tone, content_brief),
        )
        self.db.commit()
        return {"touch_id": tid, "status": "scheduled"}

    def get_pending_touches(self, before: str | None = None) -> list[dict]:
        sql = "SELECT * FROM scheduled_touches WHERE status = 'pending'"
        params: list = []
        if before:
            sql += " AND schedule_at <= ?"
            params.append(before)
        sql += " ORDER BY schedule_at ASC"
        return self._rows(sql, params)

    def get_touches_by_policy(self, policy_id: str) -> list[dict]:
        return self._rows(
            "SELECT * FROM scheduled_touches WHERE policy_id = ? ORDER BY schedule_at DESC",
            (policy_id,),
        )

    def cancel_touch(self, touch_id: str) -> dict:
        self.db.execute(
            "UPDATE scheduled_touches SET status = 'cancelled' WHERE touch_id = ?",
            (touch_id,),
        )
        self.db.commit()
        return {"touch_id": touch_id, "status": "cancelled"}

    def mark_touch_sent(self, touch_id: str, result: Any = None):
        self.db.execute(
            """UPDATE scheduled_touches
               SET status = 'sent', executed_at = ?, result = ?
               WHERE touch_id = ?""",
            (datetime.utcnow().isoformat(),
             json.dumps(result) if result else None,
             touch_id),
        )
        self.db.commit()

    # ── Audit Log ────────────────────────────────────────────────────────
    def audit(self, actor: str, action: str,
              request: Any = None, response: Any = None,
              pii_masked: bool = True):
        req = mask_for_audit(request) if pii_masked and request else request
        res = mask_for_audit(response) if pii_masked and response else response
        self.db.execute(
            "INSERT INTO audit_log (ts, actor, action, request, response, pii_masked) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (datetime.utcnow().isoformat(), actor, action,
             json.dumps(req) if req else None,
             json.dumps(res) if res else None,
             1 if pii_masked else 0),
        )
        self.db.commit()

    def get_audit_log(self, actor: str | None = None, limit: int = 50) -> list[dict]:
        sql = "SELECT * FROM audit_log"
        params: list = []
        if actor:
            sql += " WHERE actor = ?"
            params.append(actor)
        sql += " ORDER BY ts DESC LIMIT ?"
        params.append(limit)
        rows = self._rows(sql, params)
        # Parse JSON fields
        for r in rows:
            for k in ("request", "response"):
                if isinstance(r.get(k), str):
                    try:
                        r[k] = json.loads(r[k])
                    except (json.JSONDecodeError, TypeError):
                        pass
        return rows

    # ── Customer Profile (360°) ──────────────────────────────────────────
    def get_customer_profile(self, customer_id: str) -> dict | None:
        customer = self.get_customer(customer_id)
        if not customer:
            return None

        policies = self.get_policies_by_customer(customer_id)
        payments = []
        journey = []
        for p in policies:
            payments.extend(self.get_payments_by_policy(p["policy_id"]))
            journey.extend(self.get_journey(p["policy_id"]))

        # Summary
        total_premium = sum(p.get("premium_amount", 0) or 0 for p in policies)
        due_count = sum(1 for p in policies if p["status"] == "due")
        lapsed_count = sum(1 for p in policies if p["status"] == "lapsed")
        max_risk = max((p.get("risk_score", 0) or 0 for p in policies), default=0)

        return {
            "customer": customer,
            "policies": policies,
            "payments": payments,
            "journey": sorted(journey, key=lambda x: x.get("timestamp", ""), reverse=True)[:20],
            "summary": {
                "total_policies": len(policies),
                "total_annual_premium": total_premium,
                "due_policies": due_count,
                "lapsed_policies": lapsed_count,
                "max_risk_score": max_risk,
                "total_payments": len(payments),
            },
        }

    # ── Dashboard Stats ──────────────────────────────────────────────────
    def get_dashboard_stats(self) -> dict:
        total_customers = self._row("SELECT COUNT(*) AS c FROM customers")["c"]
        total_policies = self._row("SELECT COUNT(*) AS c FROM policies")["c"]

        policy_status = {}
        for row in self._rows("SELECT status, COUNT(*) AS c FROM policies GROUP BY status"):
            policy_status[row["status"]] = row["c"]

        total_active_premium = self._row(
            "SELECT COALESCE(SUM(premium_amount),0) AS s FROM policies WHERE status IN ('active','due')"
        )["s"]

        escalation_status = {}
        for row in self._rows("SELECT status, COUNT(*) AS c FROM escalations GROUP BY status"):
            escalation_status[row["status"]] = row["c"]

        channel_dist = {}
        for row in self._rows("SELECT channel, COUNT(*) AS c FROM journey_events GROUP BY channel"):
            channel_dist[row["channel"]] = row["c"]

        payment_stats = {}
        for row in self._rows(
            "SELECT status, COUNT(*) AS c, COALESCE(SUM(amount),0) AS total FROM payments GROUP BY status"
        ):
            payment_stats[row["status"]] = {"count": row["c"], "total": row["total"]}

        return {
            "total_customers": total_customers,
            "total_policies": total_policies,
            "policy_status": policy_status,
            "total_active_premium": total_active_premium,
            "escalations": escalation_status,
            "channel_distribution": channel_dist,
            "payment_stats": payment_stats,
        }
