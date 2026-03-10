# RenewAI: Client Presentation (System Architecture)

This document provides a high-level, "Visual Block" overview of the RenewAI ecosystem, designed for client presentations and stakeholder walkthroughs.

## 🌟 Visual Architecture (System Flow)

```mermaid
graph TD
    %% Styling
    classDef brain fill:#e1f5fe,stroke:#01579b,stroke-width:2px;
    classDef channel fill:#fff3e0,stroke:#e65100,stroke-width:2px;
    classDef human fill:#f1f8e9,stroke:#33691e,stroke-width:2px;
    classDef data fill:#f3e5f5,stroke:#4a148c,stroke-width:2px;

    subgraph "The Intelligence Hub (NLU/NLG)"
        BO["Orchestration Engine"]:::brain
        GE["Gemini 2.5 AI Brain"]:::brain
        OL["Objection Library (RAG)"]:::brain
    end

    subgraph "Omni-Channel Outreach"
        EA["Email Integration"]:::channel
        WA["WhatsApp Bot"]:::channel
        VA["Voice AI (Telephony)"]:::channel
    end

    subgraph "Human Excellence Layer"
        DB["Specialist Dashboard"]:::human
        HIL["Human-in-the-Loop Queue"]:::human
    end

    subgraph "Secure Data & Audit"
        SQL[("Customer Memory")]:::data
        AL[("Audit & Compliance Logs")]:::data
    end

    %% Flows
    SQL <--> BO
    BO <--> GE
    GE <--> OL
    
    BO --> EA
    BO --> WA
    BO --> VA
    
    WA -- "Customer Reply" --> BO
    VA -- "Voice Input" --> BO
    
    BO -- "Escalation" --> HIL
    HIL --> DB
    
    BO -.-> AL
    GE -.-> AL
```

## 🚀 Key System Components

### 1. The Intelligence Hub
*   **Gemini 2.5 Flash**: The cognitive engine that understands customer intent, tone, and sentiment.
*   **Objection Library (RAG)**: A vector-based retrieval system ensuring every response is grounded in IRDAI-compliant facts and vetted insurance templates.

### 2. Omni-Channel Engagement
*   **Elastic Communications**: The system intelligently switches between Email, WhatsApp, and Voice depending on customer responsiveness and urgency (T-45 to T+90).
*   **Voice AI**: High-fidelity, multi-lingual voice synthesis for real-time renewal calls.

### 3. Human Excellence (HIL)
*   **Bridge to Specialist**: Not a replacement, but an enhancer. AI handles 85% of routine follow-ups, escalating high-value or emotionally complex cases to human experts via a structured Dashboard.
*   **Briefing Notes**: Automatically generated summaries for human agents so they join a call with full context and "next step" recommendations.

### 4. Enterprise Compliance
*   **Audit-Ready Traces**: 100% of AI decisions are logged with their underlying rationale.
*   **PII Security**: Integrated masking logic ensures customer privacy is maintained across all logs and cloud API calls.
