-- ============================================================================
-- RenewAI – Seed Data
-- Realistic Indian insurance customer data based on existing project context
-- ============================================================================

-- ─── CUSTOMERS ──────────────────────────────────────────────────────────────

INSERT INTO customers VALUES
  ('CUST-001', 'Rajesh Kumar',       45, 'en-IN', 1, 'rajesh.kumar@example.com',   '+919876543210', 'Mass Affluent',    'evening'),
  ('CUST-002', 'Priya Singh',        38, 'hi-IN', 1, 'priya.singh@example.com',    '+919876543211', 'Wealth Builder',   'morning'),
  ('CUST-003', 'Rajesh Patel',       52, 'gu-IN', 1, 'rajesh.patel@example.com',   '+919876543212', 'HNI',              'weekend'),
  ('CUST-004', 'Ananya Iyer',        29, 'ta-IN', 1, 'ananya.iyer@example.com',    '+919876543213', 'Budget Conscious', 'evening'),
  ('CUST-005', 'Mohammed Farooq',    41, 'en-IN', 0, 'farooq.m@example.com',       '+919876543214', 'Mass Affluent',    'afternoon'),
  ('CUST-006', 'Lakshmi Menon',      34, 'ml-IN', 1, 'lakshmi.menon@example.com',  '+919876543215', 'Wealth Builder',   'morning'),
  ('CUST-007', 'Suresh Reddy',       60, 'te-IN', 1, 'suresh.reddy@example.com',   '+919876543216', 'HNI',              'weekend'),
  ('CUST-008', 'Kavita Sharma',      47, 'hi-IN', 1, 'kavita.sharma@example.com',  '+919876543217', 'Budget Conscious', 'evening'),
  ('CUST-009', 'Arun Nair',          55, 'ml-IN', 0, 'arun.nair@example.com',      '+919876543218', 'Mass Affluent',    'afternoon'),
  ('CUST-010', 'Deepa Choudhury',    33, 'bn-IN', 1, 'deepa.c@example.com',        '+919876543219', 'Wealth Builder',   'morning');

-- ─── POLICIES ───────────────────────────────────────────────────────────────

INSERT INTO policies VALUES
  -- Rajesh Kumar – 2 policies
  ('POL-1001', 'CUST-001', 'term',      25000,  '2026-03-15', 'due',    0.15, '2020-03-15 10:00:00'),
  ('POL-1002', 'CUST-001', 'endowment', 20000,  '2026-06-10', 'active', 0.08, '2021-06-10 11:30:00'),

  -- Priya Singh – 3 policies
  ('POL-1003', 'CUST-002', 'term',      65000,  '2026-05-20', 'active', 0.35, '2021-05-20 09:00:00'),
  ('POL-1004', 'CUST-002', 'ulip',      15000,  '2026-11-05', 'active', 0.12, '2020-11-05 14:00:00'),
  ('POL-1005', 'CUST-002', 'term',      15000,  '2026-02-14', 'due',    0.28, '2022-02-14 16:00:00'),

  -- Rajesh Patel – 3 policies (HNI)
  ('POL-1006', 'CUST-003', 'ulip',      200000, '2026-04-01', 'active', 0.10, '2019-04-01 10:00:00'),
  ('POL-1007', 'CUST-003', 'endowment', 100000, '2026-01-10', 'lapsed', 0.65, '2019-01-10 12:00:00'),
  ('POL-1008', 'CUST-003', 'term',      50000,  '2026-07-15', 'active', 0.18, '2019-07-15 09:30:00'),

  -- Ananya Iyer – 1 policy
  ('POL-1009', 'CUST-004', 'term',      8000,   '2026-03-20', 'due',    0.42, '2023-03-20 11:00:00'),

  -- Mohammed Farooq – 2 policies
  ('POL-1010', 'CUST-005', 'endowment', 30000,  '2026-08-12', 'active', 0.20, '2021-08-12 10:00:00'),
  ('POL-1011', 'CUST-005', 'term',      18000,  '2026-02-28', 'lapsed', 0.72, '2022-02-28 15:00:00'),

  -- Lakshmi Menon – 2 policies
  ('POL-1012', 'CUST-006', 'ulip',      45000,  '2026-09-01', 'active', 0.09, '2022-09-01 10:00:00'),
  ('POL-1013', 'CUST-006', 'term',      22000,  '2026-03-10', 'due',    0.30, '2022-03-10 14:00:00'),

  -- Suresh Reddy – 2 policies (HNI)
  ('POL-1014', 'CUST-007', 'ulip',      300000, '2026-12-01', 'active', 0.05, '2018-12-01 09:00:00'),
  ('POL-1015', 'CUST-007', 'endowment', 150000, '2026-06-15', 'active', 0.11, '2018-06-15 11:00:00'),

  -- Kavita Sharma – 1 policy
  ('POL-1016', 'CUST-008', 'term',      10000,  '2026-03-08', 'due',    0.55, '2023-03-08 13:00:00'),

  -- Arun Nair – 1 policy
  ('POL-1017', 'CUST-009', 'endowment', 35000,  '2026-05-01', 'active', 0.22, '2021-05-01 10:00:00'),

  -- Deepa Choudhury – 2 policies
  ('POL-1018', 'CUST-010', 'term',      28000,  '2026-04-15', 'active', 0.19, '2022-04-15 09:00:00'),
  ('POL-1019', 'CUST-010', 'ulip',      40000,  '2026-10-20', 'active', 0.07, '2022-10-20 11:00:00');

-- ─── PAYMENTS ───────────────────────────────────────────────────────────────

INSERT INTO payments VALUES
  -- Rajesh Kumar
  ('PAY-001', 'POL-1001', 25000, 'paid',    'TXN-RZP-20250315-001', '2025-03-15 10:30:00'),
  ('PAY-002', 'POL-1001', 25000, 'pending',  NULL,                   NULL),
  ('PAY-003', 'POL-1002', 20000, 'paid',    'TXN-RZP-20250610-001', '2025-06-10 09:00:00'),

  -- Priya Singh
  ('PAY-004', 'POL-1003', 65000, 'paid',    'TXN-RZP-20250520-001', '2025-05-20 14:10:00'),
  ('PAY-005', 'POL-1004', 15000, 'paid',    'TXN-RZP-20251105-001', '2025-11-05 10:45:00'),
  ('PAY-006', 'POL-1005', 15000, 'failed',  'TXN-RZP-20260214-001', '2026-02-14 16:20:00'),
  ('PAY-007', 'POL-1005', 15000, 'pending',  NULL,                   NULL),

  -- Rajesh Patel
  ('PAY-008', 'POL-1006', 200000, 'paid',   'TXN-RZP-20250401-001', '2025-04-01 11:00:00'),
  ('PAY-009', 'POL-1007', 100000, 'failed', 'TXN-RZP-20260110-001', '2026-01-10 09:15:00'),
  ('PAY-010', 'POL-1007', 100000, 'failed', 'TXN-RZP-20260125-001', '2026-01-25 12:00:00'),
  ('PAY-011', 'POL-1008', 50000,  'paid',   'TXN-RZP-20250715-001', '2025-07-15 10:00:00'),

  -- Ananya Iyer
  ('PAY-012', 'POL-1009', 8000,  'pending',  NULL,                   NULL),

  -- Mohammed Farooq
  ('PAY-013', 'POL-1010', 30000, 'paid',    'TXN-RZP-20250812-001', '2025-08-12 14:30:00'),
  ('PAY-014', 'POL-1011', 18000, 'failed',  'TXN-RZP-20260228-001', '2026-02-28 09:00:00'),

  -- Lakshmi Menon
  ('PAY-015', 'POL-1012', 45000, 'paid',    'TXN-RZP-20250901-001', '2025-09-01 10:00:00'),
  ('PAY-016', 'POL-1013', 22000, 'pending',  NULL,                   NULL),

  -- Suresh Reddy
  ('PAY-017', 'POL-1014', 300000, 'paid',   'TXN-RZP-20251201-001', '2025-12-01 09:00:00'),
  ('PAY-018', 'POL-1015', 150000, 'paid',   'TXN-RZP-20250615-001', '2025-06-15 11:30:00'),

  -- Kavita Sharma
  ('PAY-019', 'POL-1016', 10000, 'failed',  'TXN-RZP-20260308-001', '2026-03-08 13:15:00'),
  ('PAY-020', 'POL-1016', 10000, 'pending',  NULL,                   NULL),

  -- Arun Nair
  ('PAY-021', 'POL-1017', 35000, 'paid',    'TXN-RZP-20250501-001', '2025-05-01 10:00:00'),

  -- Deepa Choudhury
  ('PAY-022', 'POL-1018', 28000, 'paid',    'TXN-RZP-20250415-001', '2025-04-15 09:00:00'),
  ('PAY-023', 'POL-1019', 40000, 'paid',    'TXN-RZP-20251020-001', '2025-10-20 11:00:00');

-- ─── JOURNEY EVENTS ─────────────────────────────────────────────────────────

INSERT INTO journey_events VALUES
  -- POL-1001  Rajesh Kumar  (due in 10 days → escalating journey)
  ('EVT-001', 'POL-1001', '2026-02-20 09:00:00', 'email',    'sent',              '{"template":"renewal_30d","subject":"Your Term Plan renewal is due soon"}'),
  ('EVT-002', 'POL-1001', '2026-02-20 14:30:00', 'email',    'opened',            '{"opened_from":"gmail","device":"mobile"}'),
  ('EVT-003', 'POL-1001', '2026-02-25 10:00:00', 'whatsapp', 'sent',              '{"template":"renewal_reminder","language":"en-IN"}'),
  ('EVT-004', 'POL-1001', '2026-02-25 18:30:00', 'whatsapp', 'replied',           '{"message":"Will pay next week"}'),
  ('EVT-005', 'POL-1001', '2026-03-03 11:00:00', 'voice',    'sent',              '{"call_type":"outbound","agent":"voice_bot"}'),
  ('EVT-006', 'POL-1001', '2026-03-03 11:02:00', 'voice',    'call_answered',     '{"duration_sec":180,"outcome":"promised_payment"}'),

  -- POL-1005  Priya Singh  (overdue → failed payment → escalation)
  ('EVT-007', 'POL-1005', '2026-01-15 09:00:00', 'email',    'sent',              '{"template":"renewal_30d","subject":"Secure Future renewal approaching"}'),
  ('EVT-008', 'POL-1005', '2026-01-15 11:00:00', 'email',    'opened',            '{"opened_from":"outlook","device":"desktop"}'),
  ('EVT-009', 'POL-1005', '2026-01-15 11:05:00', 'email',    'clicked',           '{"link":"pay_now","destination":"/payment/POL-1005"}'),
  ('EVT-010', 'POL-1005', '2026-02-10 10:00:00', 'whatsapp', 'sent',              '{"template":"renewal_urgent","language":"hi-IN"}'),
  ('EVT-011', 'POL-1005', '2026-02-14 16:20:00', 'email',    'sent',              '{"template":"payment_failed","subject":"Payment unsuccessful – please retry"}'),
  ('EVT-012', 'POL-1005', '2026-02-18 09:00:00', 'voice',    'sent',              '{"call_type":"outbound","agent":"voice_bot"}'),
  ('EVT-013', 'POL-1005', '2026-02-18 09:01:00', 'voice',    'call_answered',     '{"duration_sec":240,"outcome":"requested_callback"}'),

  -- POL-1007  Rajesh Patel  (lapsed – failed payments)
  ('EVT-014', 'POL-1007', '2025-12-10 09:00:00', 'email',    'sent',              '{"template":"renewal_30d","subject":"Endowment Plus renewal due soon"}'),
  ('EVT-015', 'POL-1007', '2025-12-20 10:00:00', 'whatsapp', 'sent',              '{"template":"renewal_reminder","language":"gu-IN"}'),
  ('EVT-016', 'POL-1007', '2026-01-10 09:15:00', 'email',    'sent',              '{"template":"payment_failed","subject":"Payment failed for Endowment Plus"}'),
  ('EVT-017', 'POL-1007', '2026-01-15 10:00:00', 'voice',    'sent',              '{"call_type":"outbound","agent":"voice_bot"}'),
  ('EVT-018', 'POL-1007', '2026-01-25 12:00:00', 'email',    'sent',              '{"template":"payment_failed_2nd","subject":"Second payment attempt failed"}'),
  ('EVT-019', 'POL-1007', '2026-02-01 09:00:00', 'voice',    'sent',              '{"call_type":"outbound","agent":"human_advisor"}'),
  ('EVT-020', 'POL-1007', '2026-02-01 09:05:00', 'voice',    'call_answered',     '{"duration_sec":600,"outcome":"refused_payment","notes":"Financial difficulty"}'),

  -- POL-1009  Ananya Iyer  (due soon – budget conscious)
  ('EVT-021', 'POL-1009', '2026-02-20 09:00:00', 'email',    'sent',              '{"template":"renewal_30d","subject":"Your Term Plan renewal is approaching"}'),
  ('EVT-022', 'POL-1009', '2026-03-01 10:00:00', 'whatsapp', 'sent',              '{"template":"renewal_reminder","language":"ta-IN"}'),
  ('EVT-023', 'POL-1009', '2026-03-01 15:00:00', 'whatsapp', 'replied',           '{"message":"Premium is too expensive, looking for cheaper options"}'),

  -- POL-1013  Lakshmi Menon  (due in 5 days)
  ('EVT-024', 'POL-1013', '2026-02-10 09:00:00', 'email',    'sent',              '{"template":"renewal_30d","subject":"Term Plan renewal reminder"}'),
  ('EVT-025', 'POL-1013', '2026-02-10 12:00:00', 'email',    'opened',            '{"opened_from":"gmail","device":"mobile"}'),
  ('EVT-026', 'POL-1013', '2026-03-01 09:00:00', 'whatsapp', 'sent',              '{"template":"renewal_urgent","language":"ml-IN"}'),
  ('EVT-027', 'POL-1013', '2026-03-03 10:00:00', 'voice',    'sent',              '{"call_type":"outbound","agent":"voice_bot"}'),

  -- POL-1016  Kavita Sharma  (due, payment failed → high risk)
  ('EVT-028', 'POL-1016', '2026-02-08 09:00:00', 'email',    'sent',              '{"template":"renewal_30d","subject":"Renewal reminder for your Term Plan"}'),
  ('EVT-029', 'POL-1016', '2026-02-20 10:00:00', 'whatsapp', 'sent',              '{"template":"renewal_reminder","language":"hi-IN"}'),
  ('EVT-030', 'POL-1016', '2026-03-04 09:00:00', 'voice',    'sent',              '{"call_type":"outbound","agent":"voice_bot"}'),
  ('EVT-031', 'POL-1016', '2026-03-08 13:15:00', 'email',    'sent',              '{"template":"payment_failed","subject":"Payment failed – please update card"}'),

  -- POL-1011  Mohammed Farooq  (lapsed)
  ('EVT-032', 'POL-1011', '2026-01-28 09:00:00', 'email',    'sent',              '{"template":"renewal_30d","subject":"Term Plan renewal approaching"}'),
  ('EVT-033', 'POL-1011', '2026-02-15 10:00:00', 'whatsapp', 'sent',              '{"template":"renewal_urgent","language":"en-IN"}'),
  ('EVT-034', 'POL-1011', '2026-02-28 09:00:00', 'email',    'sent',              '{"template":"payment_failed","subject":"Payment failed on your Term Plan"}');

-- ─── ESCALATIONS ────────────────────────────────────────────────────────────

INSERT INTO escalations VALUES
  -- Rajesh Patel – lapsed endowment, HNI customer → critical
  ('ESC-001', 'POL-1007', '2026-02-01 10:00:00', 'HNI customer policy lapsed after 2 failed payments and declined renewal on call', 1, 'relationship_manager', 'in_progress'),

  -- Priya Singh – overdue term policy, failed payment
  ('ESC-002', 'POL-1005', '2026-02-18 10:00:00', 'Payment failed and customer requested callback – high-value customer at risk', 2, 'retention_team', 'queued'),

  -- Mohammed Farooq – lapsed term
  ('ESC-003', 'POL-1011', '2026-03-01 09:00:00', 'Policy lapsed after failed payment, customer unresponsive to WhatsApp', 2, 'retention_team', 'queued'),

  -- Kavita Sharma – payment failed, budget conscious
  ('ESC-004', 'POL-1016', '2026-03-08 14:00:00', 'Payment failed on due date, budget-conscious customer – explore instalment options', 3, 'customer_support', 'queued'),

  -- Ananya Iyer – requested cheaper options
  ('ESC-005', 'POL-1009', '2026-03-01 16:00:00', 'Customer replied on WhatsApp requesting cheaper premium options – may need plan restructure', 3, 'product_advisory', 'in_progress');

-- ─── AUDIT LOG ──────────────────────────────────────────────────────────────

INSERT INTO audit_log (ts, actor, action, request, response, pii_masked) VALUES
  ('2026-02-20 09:00:01', 'email_agent',    'send_email',      '{"policy_id":"POL-1001","template":"renewal_30d"}',                               '{"status":"delivered","message_id":"MSG-E001"}',                      1),
  ('2026-02-25 10:00:01', 'whatsapp_agent', 'send_whatsapp',   '{"policy_id":"POL-1001","template":"renewal_reminder"}',                          '{"status":"delivered","message_id":"MSG-W001"}',                      1),
  ('2026-03-03 11:00:01', 'voice_agent',    'initiate_call',   '{"policy_id":"POL-1001","phone":"***MASKED***"}',                                 '{"status":"answered","duration_sec":180}',                            1),
  ('2026-02-01 10:00:01', 'orchestrator',   'escalate',        '{"policy_id":"POL-1007","reason":"HNI lapsed","priority":1}',                     '{"escalation_id":"ESC-001","assigned_to":"relationship_manager"}',    1),
  ('2026-02-18 10:00:01', 'orchestrator',   'escalate',        '{"policy_id":"POL-1005","reason":"payment_failed_callback","priority":2}',         '{"escalation_id":"ESC-002","assigned_to":"retention_team"}',          1),
  ('2026-03-01 09:00:01', 'orchestrator',   'escalate',        '{"policy_id":"POL-1011","reason":"lapsed_unresponsive","priority":2}',             '{"escalation_id":"ESC-003","assigned_to":"retention_team"}',          1),
  ('2026-01-15 11:05:01', 'email_agent',    'track_click',     '{"event_id":"EVT-009","link":"pay_now"}',                                         '{"redirect_to":"/payment/POL-1005"}',                                 1),
  ('2026-02-14 16:20:01', 'system',         'payment_failed',  '{"policy_id":"POL-1005","txn_ref":"TXN-RZP-20260214-001","amount":15000}',         '{"failure_reason":"insufficient_funds"}',                             1),
  ('2026-01-10 09:15:01', 'system',         'payment_failed',  '{"policy_id":"POL-1007","txn_ref":"TXN-RZP-20260110-001","amount":100000}',        '{"failure_reason":"card_declined"}',                                  1),
  ('2026-03-08 13:15:01', 'system',         'payment_failed',  '{"policy_id":"POL-1016","txn_ref":"TXN-RZP-20260308-001","amount":10000}',         '{"failure_reason":"insufficient_funds"}',                             1),
  ('2026-03-01 16:00:01', 'orchestrator',   'escalate',        '{"policy_id":"POL-1009","reason":"customer_requested_cheaper_options","priority":3}', '{"escalation_id":"ESC-005","assigned_to":"product_advisory"}',      1),
  ('2026-03-05 09:00:00', 'system',         'daily_scan',      '{"scan_type":"due_policies","date":"2026-03-05"}',                                '{"due_count":5,"lapsed_count":2,"active_count":12}',                  1);
