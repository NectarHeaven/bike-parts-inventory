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
if 'clear_key' not in st.session_state:
    st.session_state.clear_key = 0

if st.session_state.flash_msg:
    st.markdown(f"<p class='success-text'>✨ {st.session_state.flash_msg}</p>", unsafe_allow_html=True)
    st.session_state.flash_msg = ""

# --- GOOGLE SHEETS CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

# Target strict columns matching the new GSheet layout
target_columns = ["Date", "Invoice No", "Part No", "Part Name", "Qty", "MRP", "Total Price"]

try:
    df = conn.read(worksheet="Sheet1", ttl=0)
    df = df.dropna(how="all")
    
    # Force text columns to string format to prevent PyArrow crashes
    text_columns = ["Date", "Invoice No", "Part No", "Part Name"]
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
    "Dashboard", "Add Entries (Direct Commit)", "Manage Registry", "Search / Database"
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

# --- PAGE 2: ADD ENTRIES (DIRECT COMMIT) ---
elif page == "Add Entries (Direct Commit)":
    st.title("➕ Direct Commit Registry Entry")
    
    col1, col2, col3, col4, col5, col6 = st.columns([1.2, 1.5, 1.5, 2.5, 1, 1.2])
    
    with col1:
        inv_date = st.date_input("Date", value=date.today())
    with col2:
        # Using placeholder makes it directly changeable without manual deleting!
        inv_no_input = st.text_input("Invoice No", placeholder="CASH-BILL", key=f"p_inv_{st.session_state.clear_key}")
    with col3:
        part_no = st.text_input("Part No", key=f"p_no_{st.session_state.clear_key}")
    with col4:
        part_name = st.text_input("Part Name", key=f"p_name_{st.session_state.clear_key}")
    with col5:
        qty = st.number_input("Qty", min_value=1, step=1, value=None, placeholder="1", key=f"p_qty_{st.session_state.clear_key}")
    with col6:
        mrp = st.number_input("MRP (₹)", min_value=0.0, step=1.0, value=None, placeholder="0.00", key=f"p_mrp_{st.session_state.clear_key}")
        
    st.markdown("---")
    
    if st.button("💾 Commit directly to Google Sheets", type="primary"):
        # If the user left Invoice No empty, automatically fall back to "CASH-BILL"
        final_inv_no = inv_no_input.strip() if inv_no_input.strip() != "" else "CASH-BILL"
        
        if not part_name or mrp is None or mrp <= 0:
            st.markdown("<p class='error-text'>Missing Info: Part Name and valid MRP are required.</p>", unsafe_allow_html=True)
        else:
            final_qty = qty if qty is not None else 1
            total_price = final_qty * mrp
            
            # Format single item into a dictionary record
            new_item = {
                "Date": str(inv_date),
                "Invoice No": str(final_inv_no).upper(),
                "Part No": str(part_no).strip().upper(),
                "Part Name": str(part_name).strip().upper(),
                "Qty": int(final_qty),
                "MRP": round(float(mrp), 2),
                "Total Price": round(float(total_price), 2)
            }
            
            # Convert single dictionary directly to DataFrame row
            new_row_df = pd.DataFrame([new_item])
            
            # Combine directly with existing data
            updated_df = pd.concat([df, new_row_df], ignore_index=True)
            updated_df = updated_df.reindex(columns=target_columns)
            
            # Write immediately to Google Sheets
            save_data(updated_df)
            
            st.session_state.flash_msg = f"Successfully saved entry for {new_item['Part Name']}!"
            st.session_state.clear_key += 1
            st.rerun()
# --- PAGE 3: MANAGE REGISTRY (UPDATE/DELETE) ---
elif page == "Manage Registry":
    st.title("🛠️ Update or Delete Records")
    
    if df.empty:
        st.markdown("**No records to manage.**")
    else:
        st.markdown("### Step 1: Filter & Search for the Record")
        
        # Create side-by-side filters
        col_f1, col_f2 = st.columns([1.5, 2.5])
        
        with col_f1:
            # Safely handle minimum and maximum dates from your existing data
            try:
                df['Parsed_Date'] = pd.to_datetime(df['Date']).dt.date
                min_date = df['Parsed_Date'].min()
                max_date = df['Parsed_Date'].max()
                if pd.isna(min_date): min_date = date.today()
                if pd.isna(max_date): max_date = date.today()
            except:
                min_date = date.today()
                max_date = date.today()
                df['Parsed_Date'] = date.today()

            date_range = st.date_input(
                "Filter by Date Range (From - To)",
                value=(min_date, max_date),
                max_value=date.today()
            )
            
        with col_f2:
            search_term = st.text_input("Search by Invoice No, Part No, or Part Name").strip().upper()
        
        # --- APPLY FILTERS ---
        results = df.copy()
        
        # Apply date range filter (ensuring user completed selecting both start & end dates)
        if isinstance(date_range, tuple) and len(date_range) == 2:
            start_date, end_date = date_range
            results = results[(results['Parsed_Date'] >= start_date) & (results['Parsed_Date'] <= end_date)]
            
        # Apply text search filter
        if search_term:
            mask = (
                results['Invoice No'].astype(str).str.contains(search_term, case=False) | 
                results['Part No'].astype(str).str.contains(search_term, case=False) | 
                results['Part Name'].astype(str).str.contains(search_term, case=False)
            )
            results = results[mask]
            
        # Drop temporary parsing column before rendering
        if 'Parsed_Date' in results.columns:
            results = results.drop(columns=['Parsed_Date'])

        # --- DISPLAY RESULTS & MODIFY ---
        if results.empty:
            st.warning("No records found matching your filters.")
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
                    col_u1, col_u2, col_u3, col_u4, col_u5 = st.columns(5)
                    
                    with col_u1:
                        try:
                            date_val = pd.to_datetime(record['Date']).date()
                        except:
                            date_val = date.today()
                        upd_date = st.date_input("Date", value=date_val, key="upd_d")
                        upd_inv = st.text_input("Invoice No", value=record['Invoice No'])
                    with col_u2:
                        upd_no = st.text_input("Part No", value=record['Part No'])
                    with col_u3:
                        upd_name = st.text_input("Part Name", value=record['Part Name'])
                    with col_u4:
                        upd_qty = st.number_input("Qty", min_value=1, value=int(record['Qty']))
                    with col_u5:
                        upd_mrp = st.number_input("MRP (₹)", min_value=0.0, value=float(record['MRP']))

                    preview_total = upd_qty * upd_mrp
                    st.info(f"**Calculated Total Price:** ₹ {preview_total:.2f}")

                    if st.button("💾 Save Updates", type="primary"):
                        df.at[idx_to_modify, 'Date'] = str(upd_date)
                        df.at[idx_to_modify, 'Invoice No'] = str(upd_inv).strip().upper()
                        df.at[idx_to_modify, 'Part No'] = str(upd_no).strip().upper()
                        df.at[idx_to_modify, 'Part Name'] = str(upd_name).strip().upper()
                        df.at[idx_to_modify, 'Qty'] = int(upd_qty)
                        df.at[idx_to_modify, 'MRP'] = round(float(upd_mrp), 2)
                        df.at[idx_to_modify, 'Total Price'] = round(float(preview_total), 2)
                        
                        # Strip parsing column before global file sync
                        if 'Parsed_Date' in df.columns:
                            df = df.drop(columns=['Parsed_Date'])
                            
                        save_data(df)
                        st.session_state.flash_msg = "Record updated successfully!"
                        st.rerun()

                with tab2:
                    st.error(f"⚠️ Are you sure you want to delete **{record['Part Name']}** from Invoice **{record['Invoice No']}**?")
                    if st.button("🚨 Yes, Delete This Record"):
                        # Ensure parsing column is missing so schema stays standard
                        clean_df = df.drop(index=idx_to_modify).reset_index(drop=True)
                        if 'Parsed_Date' in clean_df.columns:
                            clean_df = clean_df.drop(columns=['Parsed_Date'])
                        save_data(clean_df)
                        st.session_state.flash_msg = "Record permanently deleted!"
                        st.rerun()
# --- PAGE 4: SEARCH & DATABASE ---
elif page == "Search / Database":
    st.title("🔍 Advanced Search & Full Registry")
    
    # Create side-by-side filters
    col_f1, col_f2 = st.columns([1.5, 2.5])
    
    with col_f1:
        try:
            df['Parsed_Date'] = pd.to_datetime(df['Date']).dt.date
            min_date = df['Parsed_Date'].min()
            max_date = df['Parsed_Date'].max()
            if pd.isna(min_date): min_date = date.today()
            if pd.isna(max_date): max_date = date.today()
        except:
            min_date = date.today()
            max_date = date.today()
            df['Parsed_Date'] = date.today()

        date_range = st.date_input(
            "Filter by Date Range (From - To)",
            value=(min_date, max_date),
            max_value=date.today(),
            key="search_date_range"
        )
        
    with col_f2:
        search_term = st.text_input("Search by Invoice No, Part No, or Part Name", key="search_text_term").strip().upper()
    
    # --- APPLY FILTERS ---
    results = df.copy()
    
    # Apply date range filter
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        results = results[(results['Parsed_Date'] >= start_date) & (results['Parsed_Date'] <= end_date)]
        
    # Apply text search filter
    if search_term:
        mask = (
            results['Invoice No'].astype(str).str.contains(search_term, case=False) | 
            results['Part No'].astype(str).str.contains(search_term, case=False) | 
            results['Part Name'].astype(str).str.contains(search_term, case=False)
        )
        results = results[mask]
        
    # Clean up calculation column
    if 'Parsed_Date' in results.columns:
        results = results.drop(columns=['Parsed_Date'])

    # --- DISPLAY DATA ---
    st.markdown("### 📋 Filtered Inventory Results")
    if results.empty:
        st.markdown("**No records match the active criteria.**")
    else:
        st.dataframe(results, use_container_width=True)
        subtotal = pd.to_numeric(results['Total Price'], errors='coerce').sum()
        st.success(f"Total Value of Displayed Results: ₹ {subtotal:,.2f}")
