import streamlit as st
import pandas as pd
from datetime import date
from streamlit_gsheets import GSheetsConnection

# --- APP SETUP & CSS ---
st.set_page_config(page_title="Bike Parts Registry", layout="wide")

st.markdown("""
    <style>
        html, body, p, span, div, label, input, select, textarea, .stMarkdown, .stText { font-size: 18px !important; }
        h1 { font-size: 2.5rem !important; }
        .error-text { color: #ff4b4b; font-weight: bold; }
        .success-text { color: #00cc66; font-weight: bold; font-size: 20px;}
    </style>
""", unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION ---
if 'flash_msg' not in st.session_state:
    st.session_state.flash_msg = ""
if 'current_bill_items' not in st.session_state:
    st.session_state.current_bill_items = []
if 'clear_key' not in st.session_state:
    st.session_state.clear_key = 0

if st.session_state.flash_msg:
    st.markdown(f"<p class='success-text'>✨ {st.session_state.flash_msg}</p>", unsafe_allow_html=True)
    st.session_state.flash_msg = ""

# --- GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Target columns for the new simplified registry
target_columns = ["Date", "Invoice No", "Part Name", "Qty", "MRP", "Total Price"]

try:
    df = conn.read(worksheet="Sheet1", ttl=0)
    df = df.dropna(how="all")
    
    # Force text columns to string
    text_columns = ["Date", "Invoice No", "Part Name"]
    for col in text_columns:
        if col in df.columns:
            df[col] = df[col].astype(str).replace("nan", "")
            
except Exception as e:
    st.error(f"Could not read from Google Sheets. Error: {e}")
    df = pd.DataFrame(columns=target_columns)

# Helper function to save back to Google Sheets
def save_data(updated_df):
    conn.update(worksheet="Sheet1", data=updated_df)
    st.cache_data.clear()

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🏍️ Parts Registry")
page = st.sidebar.radio("Navigation", [
    "Dashboard", "Add Entries", "Manage Registry", "Search / Database"
])

# --- PAGE 1: DASHBOARD ---
if page == "Dashboard":
    st.title("📊 Registry Dashboard")
    
    if df.empty:
        st.info("No records in registry yet.")
    else:
        total_entries = len(df)
        total_qty = pd.to_numeric(df['Qty'], errors='coerce').sum()
        total_value = pd.to_numeric(df['Total Price'], errors='coerce').sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("📦 Unique Entries", total_entries)
        col2.metric("⚙️ Total Items (Qty)", int(total_qty) if not pd.isna(total_qty) else 0)
        col3.metric("💰 Total Registry Value", f"₹ {total_value:,.2f}")
        
        st.markdown("---")
        
        col_dash1, col_dash2 = st.columns(2)
        with col_dash1:
            st.markdown("### 🧾 Recent Invoices")
            if 'Date' in df.columns and 'Invoice No' in df.columns and 'Total Price' in df.columns:
                invoice_summary = df.groupby(['Date', 'Invoice No'])['Total Price'].sum().reset_index()
                invoice_summary = invoice_summary.sort_values(by='Date', ascending=False).head(5)
                invoice_summary['Total Price'] = invoice_summary['Total Price'].apply(lambda x: f"₹ {x:,.2f}")
                st.dataframe(invoice_summary, use_container_width=True, hide_index=True)
        
        with col_dash2:
            st.markdown("### 💎 Top 5 High-Value Entries")
            if 'Total Price' in df.columns:
                top_parts = df.nlargest(5, 'Total Price')[['Part Name', 'Qty', 'Total Price']]
                top_parts['Total Price'] = top_parts['Total Price'].apply(lambda x: f"₹ {x:,.2f}")
                st.dataframe(top_parts, use_container_width=True, hide_index=True)

# --- PAGE 2: ADD ENTRIES ---
elif page == "Add Entries":
    st.title("➕ Add Single-Line Entry")
    
    st.markdown("### 1. Item Information")
    col1, col2, col3, col4, col5 = st.columns([1.2, 1.5, 2.5, 1, 1.2])
    
    with col1:
        inv_date = st.date_input("Date", value=date.today())
    with col2:
        inv_no = st.text_input("Invoice No")
    with col3:
        part_name = st.text_input("Part Name", key=f"p_name_{st.session_state.clear_key}")
    with col4:
        qty = st.number_input("Qty", min_value=1, step=1, value=None, placeholder="1", key=f"p_qty_{st.session_state.clear_key}")
    with col5:
        mrp = st.number_input("MRP (₹)", min_value=0.0, step=1.0, value=None, placeholder="0.00", key=f"p_mrp_{st.session_state.clear_key}")
        
    if st.button("Add Item to List", type="secondary"):
        if not inv_no or not part_name or mrp is None or mrp <= 0:
            st.markdown("<p class='error-text'>Missing Info: Invoice No, Part Name, and valid MRP are required.</p>", unsafe_allow_html=True)
        else:
            final_qty = qty if qty is not None else 1
            total_price = final_qty * mrp
            
            new_item = {
                "Date": str(inv_date),
                "Invoice No": str(inv_no).strip().upper(),
                "Part Name": str(part_name).strip().upper(),
                "Qty": int(final_qty),
                "MRP": round(float(mrp), 2),
                "Total Price": round(float(total_price), 2)
            }
            st.session_state.current_bill_items.append(new_item)
            st.session_state.clear_key += 1
            st.rerun()

    if st.session_state.current_bill_items:
        st.markdown("### 2. Pending Additions")
        pending_df = pd.DataFrame(st.session_state.current_bill_items)
        st.dataframe(pending_df, use_container_width=True)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("💾 Save to Google Sheets", type="primary"):
                # Clean up existing df to ensure uniform column types before contact
                updated_df = pd.concat([df, pending_df], ignore_index=True)
                # Re-index to enforce strict column structure matching target_columns
                updated_df = updated_df.reindex(columns=target_columns)
                save_data(updated_df)
                st.session_state.flash_msg = "Items saved successfully!"
                st.session_state.current_bill_items = []
                st.rerun()
        with col_s2:
            if st.button("❌ Clear Pending List"):
                st.session_state.current_bill_items = []
                st.rerun()

# --- PAGE 3: MANAGE REGISTRY (UPDATE/DELETE) ---
elif page == "Manage Registry":
    st.title("🛠️ Update or Delete Records")
    
    if df.empty:
        st.markdown("**No records to manage.**")
    else:
        st.markdown("### Step 1: Search for the Record")
        search_term = st.text_input("Search by Date, Invoice, or Part Name").strip().upper()
        
        if search_term:
            mask = (
                df['Date'].astype(str).str.contains(search_term, case=False) | 
                df['Invoice No'].astype(str).str.contains(search_term, case=False) | 
                df['Part Name'].astype(str).str.contains(search_term, case=False)
            )
            results = df[mask]
        else:
            results = df

        if results.empty:
            st.warning("No records found matching your search.")
        else:
            st.dataframe(results, use_container_width=True)
            
            st.markdown("---")
            st.markdown("### Step 2: Select a Record to Modify")
            
            options = results.index.astype(str) + " | " + results['Invoice No'] + " | " + results['Part Name']
            selected_record = st.selectbox("Choose a record from the list above:", options, index=None)
            
            if selected_record:
                idx_to_modify = int(selected_record.split(" | ")[0])
                record = df.loc[idx_to_modify]
                
                st.markdown("---")
                tab1, tab2 = st.tabs(["✏️ Update Record", "🗑️ Delete Record"])
                
                with tab1:
                    st.markdown(f"**Updating:** {record['Part Name']}")
                    col_u1, col_u2, col_u3, col_u4 = st.columns(4)
                    
                    with col_u1:
                        try:
                            date_val = pd.to_datetime(record['Date']).date()
                        except:
                            date_val = date.today()
                        upd_date = st.date_input("Date", value=date_val)
                        upd_inv = st.text_input("Invoice No", value=record['Invoice No'])
                    with col_u2:
                        upd_name = st.text_input("Part Name", value=record['Part Name'])
                    with col_u3:
                        upd_qty = st.number_input("Qty", min_value=1, value=int(record['Qty']))
                    with col_u4:
                        upd_mrp = st.number_input("MRP (₹)", min_value=0.0, value=float(record['MRP']))

                    preview_total = upd_qty * upd_mrp
                    st.info(f"**Calculated Total Price:** ₹ {preview_total:.2f}")

                    if st.button("💾 Save Updates", type="primary"):
                        df.at[idx_to_modify, 'Date'] = str(upd_date)
                        df.at[idx_to_modify, 'Invoice No'] = str(upd_inv).strip().upper()
                        df.at[idx_to_modify, 'Part Name'] = str(upd_name).strip().upper()
                        df.at[idx_to_modify, 'Qty'] = int(upd_qty)
                        df.at[idx_to_modify, 'MRP'] = round(float(upd_mrp), 2)
                        df.at[idx_to_modify, 'Total Price'] = round(float(preview_total), 2)
                        
                        save_data(df)
                        st.session_state.flash_msg = "Record updated successfully!"
                        st.rerun()

                with tab2:
                    st.error(f"⚠️ Are you sure you want to delete **{record['Part Name']}** from Invoice **{record['Invoice No']}**?")
                    if st.button("🚨 Yes, Delete This Record"):
                        updated_df = df.drop(index=idx_to_modify).reset_index(drop=True)
                        save_data(updated_df)
                        st.session_state.flash_msg = "Record permanently deleted!"
                        st.rerun()

# --- PAGE 4: SEARCH & DATABASE ---
elif page == "Search / Database":
    st.title("🔍 Search & Full Registry")
    
    search_term = st.text_input("Search by Date, Invoice No, or Part Name").strip().upper()
    
    if search_term:
        mask = (
            df['Date'].astype(str).str.contains(search_term, case=False) | 
            df['Invoice No'].astype(str).str.contains(search_term, case=False) | 
            df['Part Name'].astype(str).str.contains(search_term, case=False)
        )
        results = df[mask]
        
        if results.empty:
            st.markdown("**No records found.**")
        else:
            st.dataframe(results, use_container_width=True)
            subtotal = pd.to_numeric(results['Total Price'], errors='coerce').sum()
            st.success(f"Total Value of Filtered Results: ₹ {subtotal:,.2f}")
    else:
        st.markdown("### 📋 Complete Inventory Registry")
        st.dataframe(df, use_container_width=True)
