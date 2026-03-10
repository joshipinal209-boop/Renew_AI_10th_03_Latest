# RenewAI: Project Design Workflow

This document visualizes the core orchestration logic, system architecture, and human-in-the-loop (HIL) escalation paths for the RenewAI platform.

## 1. System Architecture Diagram
The high-level interaction between the dashboard, orchestration engine, and channel agents.

```mermaid
graph TD
    A["Dashboard (frontend.html)"] <--> B["Flask API (backend.py)"]
    B <--> C["Renewal Orchestrator (orchestrator.py)"]
    C <--> D[("Customer Memory (database.py)")]
    C <--> E["Gemini AI (gemini_integration.py)"]
    
    C --> F["Email Agent"]
    C --> G["WhatsApp Agent"]
    C --> H["Voice Agent"]
    
    G <--> I[("Objection Library (ChromaDB)")]
    H --> J["ElevenLabs (AI Voice)"]
    
    F --> K["Policyholder"]
    G --> K
    H --> K
    
    K -- "Replies" --> B
```

## 2. Main Orchestration Lifecycle
The state machine managing a customer's renewal journey from T-45 days to maturity or lapse.

```mermaid
stateDiagram-v2
    [*] --> T45_AWARENESS : T-45 Days
    T45_AWARENESS --> T30_OFFER : Email Not Opened (48h)
    T45_AWARENESS --> WAIT : Email Opened
    
    T30_OFFER --> T20_REMINDER : WA Not Read (24h)
    
    T20_REMINDER --> T10_URGENCY : T-10 Days
    T10_URGENCY --> T5_FINAL : T-5 Days (High Risk)
    
    T5_FINAL --> T0_DUE : T-0 Days
    
    T0_DUE --> PAID : Payment Received
    T0_DUE --> GRACE_PERIOD : No Payment
    
    GRACE_PERIOD --> PAID : Late Payment
    GRACE_PERIOD --> LAPSED : Day 31+
    
    LAPSED --> REVIVAL_CAMPAIGN : Day 31-90
    REVIVAL_CAMPAIGN --> PAID : Penalty Waiver Used
    REVIVAL_CAMPAIGN --> [*] : Day 91+
    
    PAID --> [*] : Policy Renewed
```

## 3. Human-In-The-Loop (HIL) Escalation Flow
How the AI identifies and transfers complex cases to human specialists.

```mermaid
sequenceDiagram
    participant C as Customer
    participant A as Channel Agent (WA/Voice)
    participant O as Orchestrator
    participant G as Gemini AI
    participant H as Human Specialist
    
    C->>A: "I lost my job and cannot pay."
    A->>O: Forward Inbound Message
    O->>G: Classify Intent & Sentiment
    G-->>O: Intent: DISTRESS; Tone: Urgent
    O->>O: Create Escalation Table Entry (P0)
    O->>O: Generate Briefing Note
    O->>H: Notify Human Queue (HIL Interrupt)
    H->>C: Direct Calls/Negotiation
```

## 4. RAG-based Objection Handling
The retrieval mechanism for grounded, IRDAI-compliant counter-responses.

```mermaid
graph TD
    A["Customer Message: 'It is too expensive'"]
    B["Vector Search (ChromaDB)"]
    C["ID: obj_too_expensive"]
    D["Retrieved Fact: 'We offer EMI & Grace Period...'"]
    E["Gemini AI refinement"]
    F["Final Message: 'I understand, Priya. We can split your ₹24k into ₹2k EMIs...'"]
    
    A --> B
    B --> C
    C --> D
    D --> E
    E --> F
```

> [!NOTE]
> All automated decisions are logged in the **Audit Platform** (`database.py`) and are viewable in the **Audit Log** tab of the dashboard.
