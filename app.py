import streamlit as st
import pandas as pd
from datetime import date
from streamlit_gsheets import GSheetsConnection

# --- APP SETUP & CSS ---
st.set_page_config(page_title="Bike Parts Inventory", layout="wide")

st.markdown("""
    <style>
        html, body, p, span, div, label, input, select, textarea, .stMarkdown, .stText { font-size: 18px !important; }
        .css-17lntkn { font-size: 18px !important; }
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
if 'last_discount' not in st.session_state:
    st.session_state.last_discount = 31.36
if 'clear_key' not in st.session_state:
    st.session_state.clear_key = 0

if st.session_state.flash_msg:
    st.markdown(f"<p class='success-text'>✨ {st.session_state.flash_msg}</p>", unsafe_allow_html=True)
    st.session_state.flash_msg = ""

# --- GOOGLE SHEETS CONNECTION ---
# Establish connection to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# Read the data from "Sheet1" (ttl=0 ensures it always pulls the freshest data)
# Read the data from "Sheet1" (ttl=0 ensures it always pulls the freshest data)
try:
    df = conn.read(worksheet="Sheet1", ttl=0)
    # Drop any completely empty rows that Google Sheets sometimes leaves behind
    df = df.dropna(how="all")
    
    # --- PYARROW MIXED TYPE FIX ---
    # Force columns that might mix numbers and text into pure strings
    text_columns = ["Invoice No", "Part No", "Description", "Date"]
    for col in text_columns:
        if col in df.columns:
            # Convert to string, and clean up any 'nan' values that get created from empty cells
            df[col] = df[col].astype(str).replace("nan", "")
            
except Exception as e:
    st.error(f"Could not read from Google Sheets. Error: {e}")
    # Fallback to an empty dataframe with correct columns so the app doesn't crash
    df = pd.DataFrame(columns=[
        "Date", "Invoice No", "Part No", "Description", "Qty", 
        "MRP", "Discount %", "CGST %", "SGST %", "Unit Landed Cost", "Total Landed Cost"
    ])

# Helper function to save back to Google Sheets
def save_data(updated_df):
    conn.update(worksheet="Sheet1", data=updated_df)
    st.cache_data.clear()

# --- SIDEBAR NAVIGATION ---
st.sidebar.title("🏍️ Parts Manager")
page = st.sidebar.radio("Navigation", [
    "Dashboard", "Add New Bill", "Manage Inventory", "Search / Database"
])

# --- PAGE 1: DASHBOARD ---
if page == "Dashboard":
    st.title("📊 Inventory Dashboard")
    
    if df.empty:
        st.info("No data in inventory yet.")
    else:
        total_parts = len(df)
        total_qty = pd.to_numeric(df['Qty'], errors='coerce').sum()
        total_value = pd.to_numeric(df['Total Landed Cost'], errors='coerce').sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("📦 Unique Part Entries", total_parts)
        col2.metric("⚙️ Total Items (Qty)", int(total_qty))
        col3.metric("💰 Total Inventory Value", f"₹ {total_value:,.2f}")
        
        st.markdown("---")
        
        col_dash1, col_dash2 = st.columns(2)
        
        with col_dash1:
            st.markdown("### 🧾 Recent Invoices (Last 5)")
            invoice_summary = df.groupby(['Date', 'Invoice No'])['Total Landed Cost'].sum().reset_index()
            invoice_summary = invoice_summary.sort_values(by='Date', ascending=False).head(5)
            invoice_summary['Total Landed Cost'] = invoice_summary['Total Landed Cost'].apply(lambda x: f"₹ {x:,.2f}")
            invoice_summary.rename(columns={'Total Landed Cost': 'Total Bill Value'}, inplace=True)
            st.dataframe(invoice_summary, use_container_width=True, hide_index=True)
            
        with col_dash2:
            st.markdown("### 💎 Top 5 High-Value Parts")
            top_parts = df.nlargest(5, 'Total Landed Cost')[['Part No', 'Description', 'Qty', 'Total Landed Cost']]
            top_parts['Total Landed Cost'] = top_parts['Total Landed Cost'].apply(lambda x: f"₹ {x:,.2f}")
            st.dataframe(top_parts, use_container_width=True, hide_index=True)

# --- PAGE 2: ADD NEW BILL ---
elif page == "Add New Bill":
    st.title("➕ Enter New Invoice")
    
    st.markdown("### 1. Invoice Details")
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        inv_date = st.date_input("Date", value=date.today())
    with col2:
        inv_no = st.text_input("Invoice No")
    with col3:
        cgst = st.number_input("CGST (%)", min_value=0.0, step=0.1, value=None, placeholder="9.0")
    with col4:
        sgst = st.number_input("SGST (%)", min_value=0.0, step=0.1, value=None, placeholder="9.0")
        
    st.markdown("---")
    
    st.markdown("### 2. Add Parts")
    col_a, col_b, col_c, col_d, col_e = st.columns([1.5, 2.5, 1, 1, 1])
    with col_a:
        part_no = st.text_input("Part No (Optional)", key=f"p_no_{st.session_state.clear_key}")
    with col_b:
        desc = st.text_input("Description", key=f"p_desc_{st.session_state.clear_key}")
    with col_c:
        qty = st.number_input("Qty", min_value=1, step=1, value=None, placeholder="1", key=f"p_qty_{st.session_state.clear_key}")
    with col_d:
        mrp = st.number_input("MRP (₹)", min_value=0.0, step=1.0, value=None, placeholder="0.00", key=f"p_mrp_{st.session_state.clear_key}")
    with col_e:
        discount = st.number_input("Discount (%)", min_value=0.0, step=0.1, value=None, placeholder=str(st.session_state.last_discount), key="p_disc")
        
    if st.button("Add Part to List", type="secondary"):
        if not inv_no or not desc or mrp is None or mrp <= 0:
            st.markdown("<p class='error-text'>Missing Info: Invoice No, Description, and valid MRP are required.</p>", unsafe_allow_html=True)
        else:
            final_qty = qty if qty is not None else 1
            final_cgst = cgst if cgst is not None else 9.0
            final_sgst = sgst if sgst is not None else 9.0
            final_disc = discount if discount is not None else st.session_state.last_discount
            
            st.session_state.last_discount = final_disc
            
            base_price = mrp * (1 - (final_disc / 100))
            gst_amount = base_price * ((final_cgst + final_sgst) / 100)
            unit_landed_cost = base_price + gst_amount
            total_landed_cost = unit_landed_cost * final_qty
            
            new_item = {
                "Date": inv_date,
                "Invoice No": str(inv_no).strip().upper(),
                "Part No": str(part_no).strip().upper() if part_no else "",
                "Description": str(desc).strip().upper(),
                "Qty": final_qty,
                "MRP": round(mrp, 2),
                "Discount %": final_disc,
                "CGST %": final_cgst,
                "SGST %": final_sgst,
                "Unit Landed Cost": round(unit_landed_cost, 2),
                "Total Landed Cost": round(total_landed_cost, 2)
            }
            st.session_state.current_bill_items.append(new_item)
            
            st.session_state.clear_key += 1
            st.rerun()

    if st.session_state.current_bill_items:
        st.markdown("### 3. Pending Bill Items")
        pending_df = pd.DataFrame(st.session_state.current_bill_items)
        st.dataframe(pending_df, use_container_width=True)
        
        col_s1, col_s2 = st.columns(2)
        with col_s1:
            if st.button("💾 Save Invoice to Database", type="primary"):
                # Append pending items to the dataframe fetched from Google Sheets
                updated_df = pd.concat([df, pending_df], ignore_index=True)
                save_data(updated_df)
                st.session_state.flash_msg = f"Invoice {inv_no.strip().upper()} saved successfully!"
                st.session_state.current_bill_items = []
                st.rerun()
        with col_s2:
            if st.button("❌ Clear Pending List"):
                st.session_state.current_bill_items = []
                st.rerun()

# --- PAGE 3: MANAGE INVENTORY (UPDATE/DELETE) ---
elif page == "Manage Inventory":
    st.title("🛠️ Update or Delete Records")
    
    if df.empty:
        st.markdown("**No records to manage.**")
    else:
        st.markdown("### Step 1: Search for the Record")
        search_term = st.text_input("Search by Date, Invoice No, Part No, or Description").strip().upper()
        
        if search_term:
            mask = (
                df['Date'].astype(str).str.contains(search_term, case=False) | 
                df['Invoice No'].astype(str).str.contains(search_term, case=False) | 
                df['Part No'].astype(str).str.contains(search_term, case=False) |
                df['Description'].astype(str).str.contains(search_term, case=False)
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
            
            options = results.index.astype(str) + " | " + results['Invoice No'] + " | " + results['Description']
            selected_record = st.selectbox("Choose a record from the list above:", options, index=None)
            
            if selected_record:
                idx_to_modify = int(selected_record.split(" | ")[0])
                record = df.loc[idx_to_modify]
                
                st.markdown("---")
                tab1, tab2 = st.tabs(["✏️ Update This Record", "🗑️ Delete This Record"])
                
                with tab1:
                    st.markdown(f"**Updating:** {record['Description']}")
                    
                    col_u1, col_u2, col_u3, col_u4 = st.columns(4)
                    with col_u1:
                        # Convert date string from GSheets back to date object if necessary for the widget
                        try:
                            date_val = pd.to_datetime(record['Date']).date()
                        except:
                            date_val = date.today()
                        upd_date = st.date_input("Date", value=date_val)
                        upd_inv = st.text_input("Invoice No", value=record['Invoice No'])
                        upd_part = st.text_input("Part No", value=record['Part No'])
                    with col_u2:
                        upd_desc = st.text_input("Description", value=record['Description'])
                        upd_qty = st.number_input("Qty", min_value=1, value=int(record['Qty']))
                    with col_u3:
                        upd_mrp = st.number_input("MRP (₹)", min_value=0.0, value=float(record['MRP']))
                        upd_disc = st.number_input("Discount (%)", min_value=0.0, value=float(record['Discount %']))
                    with col_u4:
                        upd_cgst = st.number_input("CGST (%)", min_value=0.0, value=float(record['CGST %']))
                        upd_sgst = st.number_input("SGST (%)", min_value=0.0, value=float(record['SGST %']))

                    preview_base = upd_mrp * (1 - (upd_disc / 100))
                    preview_gst = preview_base * ((upd_cgst + upd_sgst) / 100)
                    preview_unit = preview_base + preview_gst
                    preview_total = preview_unit * upd_qty
                    
                    st.info(f"**Live Cost Preview:** Unit Landed: ₹ {preview_unit:.2f} &nbsp;&nbsp;|&nbsp;&nbsp; Total Landed: ₹ {preview_total:.2f}")

                    if st.button("💾 Save Updates", type="primary"):
                        df.at[idx_to_modify, 'Date'] = upd_date
                        df.at[idx_to_modify, 'Invoice No'] = str(upd_inv).strip().upper()
                        df.at[idx_to_modify, 'Part No'] = str(upd_part).strip().upper()
                        df.at[idx_to_modify, 'Description'] = str(upd_desc).strip().upper()
                        df.at[idx_to_modify, 'Qty'] = upd_qty
                        df.at[idx_to_modify, 'MRP'] = round(upd_mrp, 2)
                        df.at[idx_to_modify, 'Discount %'] = upd_disc
                        df.at[idx_to_modify, 'CGST %'] = upd_cgst
                        df.at[idx_to_modify, 'SGST %'] = upd_sgst
                        df.at[idx_to_modify, 'Unit Landed Cost'] = round(preview_unit, 2)
                        df.at[idx_to_modify, 'Total Landed Cost'] = round(preview_total, 2)
                        
                        save_data(df)
                        st.session_state.flash_msg = "Record updated successfully!"
                        st.rerun()

                with tab2:
                    st.error(f"⚠️ Are you sure you want to delete **{record['Description']}** from Invoice **{record['Invoice No']}**?")
                    if st.button("🚨 Yes, Delete This Record"):
                        updated_df = df.drop(index=idx_to_modify).reset_index(drop=True)
                        save_data(updated_df)
                        st.session_state.flash_msg = "Record permanently deleted!"
                        st.rerun()

# --- PAGE 4: SEARCH & DATABASE ---
elif page == "Search / Database":
    st.title("🔍 Search & Full Database")
    
    search_term = st.text_input("Search by Date, Invoice No, Part No, or Description").strip().upper()
    
    if search_term:
        mask = (
            df['Date'].astype(str).str.contains(search_term, case=False) | 
            df['Invoice No'].astype(str).str.contains(search_term, case=False) | 
            df['Part No'].astype(str).str.contains(search_term, case=False) |
            df['Description'].astype(str).str.contains(search_term, case=False)
        )
        results = df[mask]
        
        if results.empty:
            st.markdown("**No records found.**")
        else:
            st.dataframe(results, use_container_width=True)
            
            subtotal = pd.to_numeric(results['Total Landed Cost'], errors='coerce').sum()
            st.success(f"Total Value of Filtered Results: ₹ {subtotal:,.2f}")
    else:
        st.markdown("### 📋 Complete Inventory")
        st.dataframe(df, use_container_width=True)
