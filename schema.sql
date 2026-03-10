-- ============================================================================
-- RenewAI – Insurance Policy Renewal Orchestration System
-- SQLite Database Schema
-- ============================================================================

CREATE TABLE IF NOT EXISTS customers (
  customer_id TEXT PRIMARY KEY,
  full_name TEXT NOT NULL,
  age INTEGER,
  language_pref TEXT DEFAULT 'en-IN',
  whatsapp_opt_in BOOLEAN DEFAULT 1,
  email TEXT,
  phone TEXT,
  segment TEXT,               -- 'Wealth Builder', 'Budget Conscious', 'Mass Affluent', 'HNI'
  preferred_contact_window TEXT -- 'morning', 'afternoon', 'evening', 'weekend'
);

CREATE TABLE IF NOT EXISTS policies (
  policy_id TEXT PRIMARY KEY,
  customer_id TEXT NOT NULL,
  product TEXT NOT NULL,      -- 'term', 'endowment', 'ulip'
  premium_amount INTEGER,
  due_date DATE,
  status TEXT DEFAULT 'active', -- 'active', 'due', 'lapsed'
  risk_score REAL DEFAULT 0.0,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE IF NOT EXISTS payments (
  payment_id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL,
  amount INTEGER,
  status TEXT DEFAULT 'pending', -- 'paid', 'failed', 'pending'
  txn_ref TEXT,
  paid_at DATETIME,
  FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);

CREATE TABLE IF NOT EXISTS journey_events (
  event_id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL,
  timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
  channel TEXT,               -- 'email', 'whatsapp', 'voice'
  event_type TEXT,            -- 'sent', 'opened', 'clicked', 'replied', 'call_answered', 'payment_confirmed'
  payload JSON,
  FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);

CREATE TABLE IF NOT EXISTS escalations (
  escalation_id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL,
  created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
  reason TEXT,
  priority INTEGER DEFAULT 3, -- 1=critical, 2=high, 3=medium, 4=low
  assigned_to TEXT,
  status TEXT DEFAULT 'queued', -- 'queued', 'in_progress', 'resolved'
  FOREIGN KEY (policy_id) REFERENCES policies(policy_id)
);

CREATE TABLE IF NOT EXISTS scheduled_touches (
  touch_id TEXT PRIMARY KEY,
  policy_id TEXT NOT NULL REFERENCES policies(policy_id),
  channel TEXT NOT NULL CHECK(channel IN ('email','whatsapp','voice')),
  schedule_at TEXT NOT NULL,              -- ISO-8601 in policyholder TZ
  language TEXT NOT NULL DEFAULT 'en-IN',
  tone TEXT NOT NULL CHECK(tone IN ('warm','formal','urgent','reassuring')),
  content_brief TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','sent','cancelled','failed')),
  created_at DATETIME DEFAULT (datetime('now')),
  executed_at DATETIME,
  result JSON
);

CREATE INDEX IF NOT EXISTS idx_touch_policy ON scheduled_touches(policy_id);
CREATE INDEX IF NOT EXISTS idx_touch_status ON scheduled_touches(status);
CREATE INDEX IF NOT EXISTS idx_touch_schedule ON scheduled_touches(schedule_at);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts DATETIME DEFAULT CURRENT_TIMESTAMP,
  actor TEXT,                 -- 'email_agent', 'whatsapp_agent', 'voice_agent', 'orchestrator', 'system'
  action TEXT,
  request JSON,
  response JSON,
  pii_masked BOOLEAN DEFAULT 1
);

-- ============================================================================
-- Indexes for performance
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_policies_customer ON policies(customer_id);
CREATE INDEX IF NOT EXISTS idx_policies_status ON policies(status);
CREATE INDEX IF NOT EXISTS idx_policies_due_date ON policies(due_date);
CREATE INDEX IF NOT EXISTS idx_payments_policy ON payments(policy_id);
CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status);
CREATE INDEX IF NOT EXISTS idx_journey_policy ON journey_events(policy_id);
CREATE INDEX IF NOT EXISTS idx_journey_channel ON journey_events(channel);
CREATE INDEX IF NOT EXISTS idx_escalations_policy ON escalations(policy_id);
CREATE INDEX IF NOT EXISTS idx_escalations_status ON escalations(status);
CREATE INDEX IF NOT EXISTS idx_audit_actor ON audit_log(actor);
CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(ts);
