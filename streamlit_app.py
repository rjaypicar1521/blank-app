# pos_client/streamlit_app.py

    # Save as app.py
import streamlit as st
import sqlite3
import pandas as pd

DB = "inventory.db"

def init_db():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS inventory(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product TEXT,
            stock_kg REAL,
            cost_per_kg REAL
        )
    """)
    conn.commit()
    conn.close()

def add_product(product, stock, cost):
    conn = sqlite3.connect(DB)
    cur = conn.cursor()
    cur.execute("INSERT INTO inventory(product, stock_kg, cost_per_kg) VALUES (?,?,?)",
                (product, stock, cost))
    conn.commit()
    conn.close()

def view_inventory():
    conn = sqlite3.connect(DB)
    df = pd.read_sql("SELECT * FROM inventory", conn)
    conn.close()
    return df

# Streamlit UI
st.title("🌾 Rice Business Inventory & Sales")

menu = ["Add Product", "View Inventory"]
choice = st.sidebar.selectbox("Menu", menu)

if choice == "Add Product":
    st.subheader("Add New Stock")
    product = st.text_input("Product Name")
    stock = st.number_input("Stock (kg)", min_value=0.0, step=1.0)
    cost = st.number_input("Cost per kg", min_value=0.0, step=0.1)
    if st.button("Add to Inventory"):
        add_product(product, stock, cost)
        st.success(f"{product} added successfully!")

elif choice == "View Inventory":
    st.subheader("📦 Current Inventory")
    df = view_inventory()
    st.dataframe(df)

# Initialize DB
init_db()
