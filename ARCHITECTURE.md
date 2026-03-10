# RenewAI: Production Architecture Blueprint

RenewAI is built on a production-grade Azure cloud stack, specifically architected for financial services compliance (RBI data residency, ISO 27001, SOC 2 Type II).

## System Topology

| Layer | Component | Purpose | Implementation Status |
| :--- | :--- | :--- | :--- |
| **Agent Orchestration** | AI Workflow Engine | State machine managing the full renewal journey; HIL interrupt nodes. | `orchestrator.py` (Complete) |
| **Language AI** | Gemini LLM | Personalized generation, objection handling, intent/sentiment analysis. | `gemini_integration.py` (Complete) |
| **Email** | Content & Delivery | Tracking-enabled dispatch for awareness and reminders. | `email_agent.py` (Complete) |
| **WhatsApp** | Business API | Persistent conversational flows with QR/Intent detection. | `whatsapp_agent.py` (Complete) |
| **Voice** | AI Voice (ElevenLabs) | Outbound calls with real-time transcription and multilingual support. | `elevenlabs_agent.py` (Complete) |
| **Customer Memory** | Semantic Store | Customer intent history and policy context retrieval. | `database.py` (Complete) |
| **Document Processing**| AI IDP | Extracting data from scanned forms/receipts. | Partial (Intent-based) |
| **Safety & Guardrails** | Content Safety | Distress detection (Hardship/Illness) and PII masking. | `pii_masking.py` (Complete) |
| **Observability** | Audit Platform | IRDAI audit-ready traces of every agent action and decision. | `database.py` / `audit` (Complete) |
| **Human Interface** | Web Dashboard | Specialist workbench with briefing notes and case queues. | `frontend.html` (Complete) |
| **Strategy & Team** | [Business Case](file:///home/labuser/Renew%20ai%2006/BUSINESS_CASE.md) | Transformation from 120 to 20 specialized roles. | `BUSINESS_CASE.md` (New) |
| **Workflows** | [Design Workflow](file:///home/labuser/Renew%20ai%2006/DESIGN_WORKFLOW.md) | Visualized state machine and HIL escalation paths. | `DESIGN_WORKFLOW.md` (New) |
| **Design Spec** | [Technical Design Specification](file:///home/labuser/Renew%20ai%2006/DESIGN_SPEC.md) | Detailed documentation on RAG, schemas, and API. | `DESIGN_SPEC.md` (New) |
| **Presentation** | [Client-Ready Architecture](file:///home/labuser/Renew%20ai%2006/CLIENT_PRESENTATION.md) | High-level "Visual Block" diagram for stakeholders. | `CLIENT_PRESENTATION.md` (New) |
| **Flowchart** | [System Architecture Flowchart](file:///home/labuser/Renew%20ai%2006/SYSTEM_ARCHITECTURE_FLOWCHART.md) | Presentation-ready visual flow of data and logic. | `FLOWCHART.md` (New) |
| **Cloud Infra** | Azure India Region | Auto-scaling and zero-downtime deployment. | Infrastructure Spec |

## Compliance & Security
- **Data Residency**: All policyholder data is processed and stored within India regions per RBI guidelines.
- **Regulatory Guardrails**: Automated detection of distress (bereavement, hardship) triggers immediate human escalation to prevent non-compliant automated persistence.
- **Auditability**: Every decision made by an AI agent is logged with the underlying rationale and context for regulatory review.
