import sqlite3
import random
import uuid
from datetime import datetime, timedelta

# Configuration
DB_PATH = "renewai.db"
NUM_NEW_CUSTOMERS = 25

# Data Pools
FIRST_NAMES = ["Amit", "Sunita", "Vikram", "Neha", "Arjun", "Deepika", "Rohan", "Sonal", "Karan", "Pooja", "Rahul", "Anjali", "Sanjay", "Meera", "Aditya", "Ishani", "Vijay", "Tanvi", "Abhishek", "Ritu", "Manoj", "Shweta", "Gaurav", "Divya", "Prateek"]
LAST_NAMES = ["Sharma", "Verma", "Gupta", "Malhotra", "Joshi", "Kapoor", "Trivedi", "Reddy", "Patel", "Singh", "Nair", "Iyer", "Choudhury", "Bose", "Das", "Kulkarni", "Desai", "Rao", "Shetty", "Pillai", "Aggarwal", "Bansal", "Mehta", "Shah", "Ghadge"]
LANGUAGES = ["en-IN", "hi-IN", "gu-IN", "ta-IN", "te-IN", "ml-IN", "bn-IN", "mr-IN", "kn-IN"]
SEGMENTS = ["Mass Affluent", "Wealth Builder", "HNI", "Budget Conscious"]
WINDOWS = ["morning", "afternoon", "evening", "weekend"]
PRODUCTS = ["term", "endowment", "ulip"]
STATUSES = ["active", "due", "lapsed"]
CHANNELS = ["email", "whatsapp", "voice"]

def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def generate_data():
    conn = get_db()
    cursor = conn.cursor()

    print(f"Generating {NUM_NEW_CUSTOMERS} new customers...")

    for i in range(1, NUM_NEW_CUSTOMERS + 1):
        # 1. Create Customer
        cust_id = f"CUST-{100 + i}"
        name = f"{random.choice(FIRST_NAMES)} {random.choice(LAST_NAMES)}"
        age = random.randint(25, 65)
        lang = random.choice(LANGUAGES)
        opt_in = 1 if random.random() > 0.1 else 0
        email = f"{name.lower().replace(' ', '.')}@example.com"
        phone = f"+91{random.randint(7000000000, 9999999999)}"
        segment = random.choice(SEGMENTS)
        window = random.choice(WINDOWS)

        cursor.execute("INSERT OR IGNORE INTO customers (customer_id, full_name, age, language_pref, whatsapp_opt_in, email, phone, segment, preferred_contact_window) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       (cust_id, name, age, lang, opt_in, email, phone, segment, window))

        # 2. Create Policy (1-2 per customer)
        num_policies = random.randint(1, 2)
        for j in range(num_policies):
            pol_id = f"POL-{2000 + (i * 10) + j}"
            product = random.choice(PRODUCTS)
            premium = random.randint(5000, 50000)
            if segment == "HNI":
                premium = random.randint(100000, 500000)
            elif segment == "Mass Affluent":
                premium = random.randint(25000, 100000)
            
            # Due date within +/- 60 days
            days_offset = random.randint(-45, 60)
            due_date = (datetime(2026, 3, 5) + timedelta(days=days_offset)).strftime("%Y-%m-%d")
            
            status = "active"
            if days_offset <= 0:
                status = "lapsed" if days_offset < -30 else "due"
            elif days_offset < 30:
                status = "due"
            
            risk_score = round(random.uniform(0.0, 0.8), 2)
            if status == "lapsed":
                risk_score = round(random.uniform(0.6, 0.95), 2)
            
            created_at = (datetime.now() - timedelta(days=random.randint(365, 1000))).isoformat()

            cursor.execute("INSERT OR IGNORE INTO policies (policy_id, customer_id, product, premium_amount, due_date, status, risk_score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                           (pol_id, cust_id, product, premium, due_date, status, risk_score, created_at))

            # 3. Create Payments
            # Record last year's payment
            cursor.execute("INSERT OR IGNORE INTO payments (payment_id, policy_id, amount, status, txn_ref, paid_at) VALUES (?, ?, ?, ?, ?, ?)",
                           (f"PAY-SYN-{pol_id}-LAST", pol_id, premium, "paid", f"TXN-SYN-{uuid.uuid4().hex[:8].upper()}", (datetime.strptime(due_date, "%Y-%m-%d") - timedelta(days=365)).isoformat()))

            # If due or lapsed, record pending/failed payment
            if status in ["due", "lapsed"]:
                pay_status = "pending" if status == "due" and random.random() > 0.3 else "failed"
                cursor.execute("INSERT OR IGNORE INTO payments (payment_id, policy_id, amount, status, txn_ref, paid_at) VALUES (?, ?, ?, ?, ?, ?)",
                               (f"PAY-SYN-{pol_id}-NOW", pol_id, premium, pay_status, None, None))

            # 4. Journey Events (2-5 events)
            num_events = random.randint(2, 5)
            for k in range(num_events):
                event_id = f"EVT-SYN-{pol_id}-{k}"
                channel = random.choice(CHANNELS)
                event_type = random.choice(["sent", "opened", "clicked", "replied"])
                ts = (datetime.strptime(due_date, "%Y-%m-%d") - timedelta(days=random.randint(1, 30))).isoformat()
                payload = {"synthetic": True, "note": "Generated for testing"}
                
                cursor.execute("INSERT OR IGNORE INTO journey_events (event_id, policy_id, timestamp, channel, event_type, payload) VALUES (?, ?, ?, ?, ?, ?)",
                               (event_id, pol_id, ts, channel, event_type, str(payload)))

    conn.commit()

    # 5. Specific Record: Vijay Shrimali
    print("Adding specific record: Vijay Shrimali...")
    cust_id = "CUST-VIJAY"
    pol_id = "POL-VIJAY"
    due_date = (datetime(2026, 3, 6) + timedelta(days=19)).strftime("%Y-%m-%d")
    
    cursor.execute("""
        INSERT OR REPLACE INTO customers 
        (customer_id, full_name, age, language_pref, whatsapp_opt_in, email, phone, segment, preferred_contact_window) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (cust_id, "Vijay Shrimali", 42, 'gu-IN', 1, 'vijay.shrimali@example.com', '9723603045', 'Wealth Builder', 'morning'))

    cursor.execute("""
        INSERT OR REPLACE INTO policies 
        (policy_id, customer_id, product, premium_amount, due_date, status, risk_score) 
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (pol_id, cust_id, 'term', 28000, due_date, 'due', 0.12))

    conn.commit()
    conn.close()
    print("Successfully added synthetic data.")

if __name__ == "__main__":
    generate_data()
