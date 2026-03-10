"""
RenewAI – ChromaDB Objection Library
=============================================
Semantic vector search over common insurance-renewal objections and their
grounded, IRDAI-compliant counter-responses.
"""

import os
import chromadb
from typing import List, Dict


class ObjectionLibrary:
    """ChromaDB-backed library for matching customer objections to responses."""

    SEED_OBJECTIONS = [
        {
            "id": "obj_price_hike",
            "text": "The premium has increased too much compared to last year",
            "response": (
                "I understand your concern about the premium change. Insurance premiums "
                "are calculated based on age brackets set by IRDAI guidelines. As we age, "
                "the risk factor adjusts accordingly. However, I can offer you a convenient "
                "EMI payment option to spread the cost. Your current coverage of ₹1Cr "
                "protects your family's future — would you like to explore monthly payments?"
            ),
            "category": "OBJECTION_PRICE",
        },
        {
            "id": "obj_too_expensive",
            "text": "I cannot afford this premium right now, it is too expensive",
            "response": (
                "I completely understand financial pressures can be challenging. "
                "You have two helpful options: First, you can pay via EMI — splitting your "
                "premium into easy monthly instalments. Second, remember you have a 30-day "
                "grace period after the due date during which your coverage remains fully active. "
                "Would either of these options help you maintain your coverage?"
            ),
            "category": "OBJECTION_PRICE",
        },
        {
            "id": "obj_coverage_doubt",
            "text": "I don't think I need this much coverage anymore",
            "response": (
                "I appreciate you thinking about your coverage needs. Your current sum assured "
                "was carefully calculated based on your family's financial needs, outstanding "
                "liabilities, and future goals. Before making any changes, I'd recommend a "
                "quick review with our advisor to ensure your family remains adequately protected. "
                "Should I connect you with a specialist who can review your coverage?"
            ),
            "category": "OBJECTION_COVERAGE",
        },
        {
            "id": "obj_already_paid",
            "text": "I already paid this premium through another channel or bank",
            "response": (
                "Thank you for letting me know! Payments made through other channels may take "
                "24-48 hours to reflect in our system. Could you please share the transaction "
                "reference number or UPI ID so I can verify your payment? Once confirmed, I'll "
                "immediately update your policy status. In the meantime, your coverage remains "
                "active during the 30-day grace period."
            ),
            "category": "ALREADY_PAID",
        },
        {
            "id": "obj_competitor_cheaper",
            "text": "Another insurance company is offering a cheaper plan with similar benefits",
            "response": (
                "I understand the appeal of a lower premium. When comparing policies, I'd "
                "encourage looking at the claim settlement ratio — Suraksha Life's ratio is "
                "among the highest in the industry. Additionally, your existing policy has "
                "accumulated bonuses and continuity benefits that would be lost if you switch. "
                "The tax benefits under Section 80C and 10(10D) also continue with renewal."
            ),
            "category": "OBJECTION_PRICE",
        },
        {
            "id": "obj_pay_later",
            "text": "Can I pay next month instead? I will pay later",
            "response": (
                "Of course! You have a grace period to complete your payment: 30 days for Term "
                "and Endowment plans, and 15 days for ULIP plans. During this period, your "
                "coverage remains fully active. If you'd prefer predictable payments, we also "
                "offer an EMI option to spread the cost over monthly instalments. "
                "Would you like me to set that up?"
            ),
            "category": "PAY_LATER",
        },
    ]

    def __init__(self, persist_directory: str = "./objection_db"):
        self.client = chromadb.PersistentClient(path=persist_directory)
        self.collection = self.client.get_or_create_collection(
            name="objections",
            metadata={"description": "Insurance renewal objection handling"},
        )
        self._seed_library()

    def _seed_library(self):
        """Seed the library if empty."""
        if self.collection.count() > 0:
            return
        self.collection.add(
            ids=[o["id"] for o in self.SEED_OBJECTIONS],
            documents=[o["text"] for o in self.SEED_OBJECTIONS],
            metadatas=[
                {"response": o["response"], "category": o["category"]}
                for o in self.SEED_OBJECTIONS
            ],
        )

    def query(self, text: str, n_results: int = 1) -> List[Dict]:
        """Search for the most relevant objection handling response."""
        results = self.collection.query(query_texts=[text], n_results=n_results)
        items = []
        for i in range(len(results["ids"][0])):
            items.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i],
                "response": results["metadatas"][0][i].get("response", ""),
                "category": results["metadatas"][0][i].get("category", ""),
                "distance": results["distances"][0][i] if results.get("distances") else None,
            })
        return items
