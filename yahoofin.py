import streamlit as st
import yfinance as yf
import datetime
import pandas as pd
import io
import zipfile

st.set_page_config(page_title="Yahoo Finance Equity Data Downloader", page_icon="📈", layout="wide")

st.title("📈 Stock Data Downloader")
st.markdown("Download historical daily OHLC (Open, High, Low, Close) stock market data using `yfinance`.")

# Helper function to round numerical data safely
def format_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    # Round numerical float columns to 2 decimals
    return df.round(2)

# Tabs for Single Symbol download vs Bulk CSV Batch download
tab1, tab2 = st.tabs(["Single Symbol Search", "Bulk Batch Download (CSV Upload)"])

today = datetime.date.today()
default_start = today - datetime.timedelta(days=365)

# ---------------- TAB 1: Single Symbol ----------------
with tab1:
    st.sidebar.header("Data Parameters (Single Symbol)")
    symbol = st.sidebar.text_input("Symbol Name", value="^NSEI", help="e.g. AAPL, MSFT, TSLA, ^NSEI, RELIANCE.NS")
    
    start_date = st.sidebar.date_input("Start Date", value=default_start, key="single_start")
    end_date = st.sidebar.date_input("End Date", value=today, key="single_end")

    if start_date > end_date:
        st.error("Error: End Date must be after Start Date.")
    else:
        fetch_btn = st.sidebar.button("Fetch Single Symbol Data", type="primary")

        if fetch_btn or 'df_data' in st.session_state:
            if fetch_btn:
                with st.spinner(f"Fetching data for **{symbol}**..."):
                    try:
                        df = yf.download(
                            symbol,
                            start=start_date.strftime("%Y-%m-%d"),
                            end=end_date.strftime("%Y-%m-%d"),
                            progress=False
                        )
                        df = format_dataframe(df)
                        st.session_state['df_data'] = df
                        st.session_state['fetched_symbol'] = symbol
                    except Exception as e:
                        st.error(f"Failed to fetch data: {e}")

            if 'df_data' in st.session_state and not st.session_state['df_data'].empty:
                df = st.session_state['df_data']
                current_symbol = st.session_state.get('fetched_symbol', symbol)

                st.subheader(f"Historical Data for {current_symbol}")
                st.write(f"Total Rows: {len(df)}")
                st.dataframe(df, width="stretch")

                csv_data = df.to_csv().encode('utf-8')
                clean_symbol = current_symbol.replace("^", "").replace(".", "_")

                st.download_button(
                    label="📥 Download CSV File",
                    data=csv_data,
                    file_name=f"{clean_symbol}_{start_date}_{end_date}.csv",
                    mime="text/csv",
                    type="primary"
                )
            elif 'df_data' in st.session_state and st.session_state['df_data'].empty:
                st.warning("No data found for the selected symbol and date range. Please check the ticker symbol.")

# ---------------- TAB 2: Bulk CSV Upload & ZIP Download ----------------
with tab2:
    st.header("Bulk Download via CSV File")
    st.write("Upload a CSV file containing a column named **`Symbol`** with stock scrip names.")

    col1, col2 = st.columns(2)
    with col1:
        bulk_start = st.date_input("Bulk Start Date", value=default_start, key="bulk_start")
    with col2:
        bulk_end = st.date_input("Bulk End Date", value=today, key="bulk_end")

    auto_append_ns = st.checkbox(
        "Automatically append `.NS` suffix to symbols (for NSE India stocks)",
        value=True,
        help="If checked, symbols like 'RELIANCE' will be automatically converted to 'RELIANCE.NS' before fetching."
    )

    uploaded_file = st.file_uploader("Upload CSV containing 'Symbol' column", type=["csv"])

    if uploaded_file is not None:
        try:
            input_df = pd.read_csv(uploaded_file)
            
            # Case-insensitive check for 'Symbol' column
            symbol_col = None
            for col in input_df.columns:
                if col.strip().lower() == "symbol":
                    symbol_col = col
                    break
            
            if symbol_col is None:
                st.error("Uploaded CSV must contain a column named **'Symbol'**.")
            else:
                raw_symbols = input_df[symbol_col].dropna().astype(str).str.strip().tolist()
                st.success(f"Loaded {len(raw_symbols)} symbols from CSV.")

                if st.button("Process & Generate ZIP File", type="primary"):
                    if bulk_start > bulk_end:
                        st.error("Error: End Date must be after Start Date.")
                    else:
                        progress_bar = st.progress(0)
                        status_text = st.empty()

                        zip_buffer = io.BytesIO()
                        successful_count = 0
                        failed_symbols = []

                        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                            for idx, raw_sym in enumerate(raw_symbols):
                                status_text.text(f"Fetching {idx+1}/{len(raw_symbols)}: {raw_sym}")
                                progress_bar.progress((idx + 1) / len(raw_symbols))

                                # Process symbol name
                                yf_sym = raw_sym
                                if auto_append_ns and not yf_sym.endswith(".NS") and not yf_sym.startswith("^"):
                                    yf_sym = f"{yf_sym}.NS"

                                try:
                                    stock_df = yf.download(
                                        yf_sym,
                                        start=bulk_start.strftime("%Y-%m-%d"),
                                        end=bulk_end.strftime("%Y-%m-%d"),
                                        progress=False
                                    )
                                    if not stock_df.empty:
                                        stock_df = format_dataframe(stock_df)
                                        csv_str = stock_df.to_csv()
                                        clean_fname = f"{raw_sym}_{bulk_start}_{bulk_end}.csv"
                                        zf.writestr(clean_fname, csv_str)
                                        successful_count += 1
                                    else:
                                        failed_symbols.append(raw_sym)
                                except Exception as e:
                                    failed_symbols.append(raw_sym)

                        status_text.text("Processing complete!")
                        st.success(f"Successfully fetched data for {successful_count}/{len(raw_symbols)} symbols.")
                        
                        if failed_symbols:
                            st.warning(f"Could not fetch data for the following symbols: {', '.join(failed_symbols)}")

                        zip_buffer.seek(0)
                        st.download_button(
                            label="📦 Download All CSVs (ZIP)",
                            data=zip_buffer,
                            file_name=f"stock_data_{bulk_start}_{bulk_end}.zip",
                            mime="application/zip",
                            type="primary"
                        )
        except Exception as e:
            st.error(f"Error reading CSV file: {e}")
