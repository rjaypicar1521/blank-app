# pos_client/streamlit_app.py
import streamlit as st
import requests
import sqlite3
import os
import json
from datetime import datetime
from typing import List

BACKEND_URL = os.environ.get("POS_BACKEND", "http://localhost:8000")

# Local queue DB for offline / retry
LOCAL_DB = "pos_local_queue.db"

def init_local_db():
    conn = sqlite3.connect(LOCAL_DB)
    cur = conn.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS queue (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        client_txn_id TEXT,
        payload TEXT,
        status TEXT DEFAULT 'pending',
        created_at TEXT
    )
    """)
    conn.commit()
    conn.close()

def enqueue_sale(payload: dict):
    conn = sqlite3.connect(LOCAL_DB)
    cur = conn.cursor()
    cur.execute("INSERT INTO queue(client_txn_id, payload, status, created_at) VALUES (?,?,?,?)",
                (payload["client_txn_id"], json.dumps(payload), "pending", datetime.utcnow().isoformat()))
    conn.commit()
    conn.close()

def try_post_sale(payload: dict):
    try:
        r = requests.post(f"{BACKEND_URL}/sales/", json=payload, timeout=5)
        if r.ok:
            return r.json()
    except Exception as e:
        print("Post failed:", e)
    return None

# UI
st.title("🌾 POS — Streamlit Cashier")

init_local_db()

# sidebar configuration
store_id = st.sidebar.text_input("Store ID", value="TANAY_01")
backend_url = st.sidebar.text_input("Backend URL", value=BACKEND_URL)

st.sidebar.markdown("**Sync**")
if st.sidebar.button("Sync Pending Sales"):
    # try sync pending
    conn = sqlite3.connect(LOCAL_DB)
    cur = conn.cursor()
    rows = cur.execute("SELECT id, payload FROM queue WHERE status='pending'").fetchall()
    synced = 0
    for r in rows:
        pid, payload_json = r
        payload = json.loads(payload_json)
        resp = try_post_sale(payload)
        if resp:
            cur.execute("UPDATE queue SET status='synced' WHERE id=?", (pid,))
            synced += 1
    conn.commit()
    conn.close()
    st.sidebar.success(f"Synced {synced} sales (or attempted)")

# scanning / product lookup
st.subheader("Scan or enter barcode / SKU")
barcode = st.text_input("Barcode / SKU (press Enter after scanning)")

if st.button("Lookup"):
    if barcode.strip() == "":
        st.error("Please provide barcode/SKU")
    else:
        # try backend product lookup
        try:
            r = requests.get(f"{backend_url}/products/by-barcode/{barcode}", timeout=3)
            if r.ok:
                p = r.json()
                st.success(f"Found: {p['name']} — ₱{p['price']:.2f}")
                st.session_state["current_product"] = p
            else:
                st.warning("Product not found on backend.")
        except Exception as e:
            st.warning("Backend unavailable. You can still add sale to queue.")
            st.session_state["current_product"] = {"sku": barcode, "name": barcode, "price": 0.0}

# quick sale form
st.subheader("Create Sale")
if "current_product" in st.session_state:
    prod = st.session_state["current_product"]
    st.write(f"Selected: {prod.get('name')} (SKU: {prod.get('sku')})")
    qty = st.number_input("Quantity", value=1.0, step=1.0)
    unit_price = st.number_input("Unit price", value=float(prod.get('price', 0.0)))
    if st.button("Add Sale (send now / queue if offline)"):
        client_txn_id = f"{store_id}-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        item = {"sku": prod.get("sku"), "qty": qty, "unit_price": unit_price}
        subtotal = qty * unit_price
        payload = {
            "client_txn_id": client_txn_id,
            "store_id": store_id,
            "items": [item],
            "subtotal": subtotal,
            "tax": 0.0,
            "total": subtotal,
            "payment_status": "paid"
        }
        resp = try_post_sale(payload)
        if resp:
            st.success("Sale posted to server.")
            st.code(resp.get("receipt_text", "No receipt"))
            # optionally send to printer client endpoint if you have one
        else:
            enqueue_sale(payload)
            st.warning("Backend unreachable — sale queued locally for sync.")

# view pending queue
st.subheader("Pending Queue")
conn = sqlite3.connect(LOCAL_DB)
qdf = conn.execute("SELECT id, client_txn_id, status, created_at FROM queue ORDER BY created_at DESC").fetchall()
conn.close()
for row in qdf:
    st.write(f"{row[0]} | {row[1]} | {row[2]} | {row[3]}")
