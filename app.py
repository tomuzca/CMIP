import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
import os

# Load environment variables from the .env file
load_dotenv()

# API configuration
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    st.error("The API key is not configured. Make sure to define 'API_KEY' in the .env file.")
    st.stop()

BASE_URL = "https://api.sam.gov/opportunities/v2/search"

# Application Title and Description
st.title("SAM.gov Search Engine")
st.write("This application allows you to search for opportunities on SAM.gov and export the results to an Excel file.")

# Search Parameters section in the sidebar
st.sidebar.header("Search Parameters")
posted_from = st.sidebar.date_input("Posted From Date (postedFrom)", value=None)
posted_to = st.sidebar.date_input("Posted To Date (postedTo)", value=None)

# Filter for NAICS starting with 23
include_naics_23 = st.sidebar.checkbox("Include NAICS Code Filter (Starts with 23)")

# Filter for "typeOfSetAside"
selected_set_asides = st.sidebar.multiselect(
    "Set-Aside Filter",
    options=['blank', 'SBA', 'SBP', '8A', '8AN', 'HZC', 'HZS', 'SDVOSBC', 'SDVOSBS', 'WOSB', 'WOSBSS', 'EDWOSB', 'EDWOSBSS', 'LAS', 'IEE', 'ISBEE', 'BICiv', 'VSA', 'VSS', 'NONE']
)

# Filter for "Response Deadline From"
due_date_from = st.sidebar.date_input("Response Deadline From", value=None)

# Button to start the search
if st.sidebar.button("Search Opportunities"):
    if not posted_from or not posted_to:
        st.error("Please select both a start date and an end date.")
    else:
        # Convert dates to "MM/DD/YYYY" string format
        posted_from_str = posted_from.strftime("%m/%d/%Y")
        posted_to_str = posted_to.strftime("%m/%d/%Y")

        # Define API request parameters
        # IMPORTANT: 'officeAddress' has been replaced by 'placeOfPerformance'
        params = {
            "api_key": API_KEY,
            "postedFrom": posted_from_str,
            "postedTo": posted_to_str,
            "limit": 1000, # Maximum limit of results per request
            "offset": 0,
            "ptype": "o", # Publication type (opportunities)
            # Expanded list of fields now includes 'placeOfPerformance'
            "fields": "postedDate,title,type,baseType,noticeId,naicsCode,description,originalPublishedDate,typeOfSetAside,fullParentPathName,uiLink,responseDeadLine,placeOfPerformance"
        }

        try:
            st.info("Making the API request...")
            # Make the HTTP GET request
            response = requests.get(BASE_URL, params=params)
            response.raise_for_status() # Raise an error for bad HTTP status codes
            
            data = response.json()
            results = data.get("opportunitiesData", [])

            if not results:
                st.warning("No results found matching the date criteria.")
                st.session_state.api_results = None
                st.session_state.dataframe = None
            else:
                # Store the results in the session state
                st.session_state.api_results = results
                
                # Process the results and create a DataFrame
                df = pd.DataFrame(results)

                # --- NAICS filtering logic ---
                if include_naics_23:
                    if 'naicsCode' in df.columns:
                        df['naicsCode'] = df['naicsCode'].astype(str)
                        df = df[df['naicsCode'].str.startswith('23', na=False)]
                        if df.empty:
                            st.warning("No opportunities found with a NAICS code starting with 23.")
                            st.session_state.dataframe = None
                            st.stop()
                    else:
                        st.warning("No NAICS data found to filter.")
                        st.stop()

                # --- Filtering logic for "typeOfSetAside" ---
                if selected_set_asides:
                    if 'typeOfSetAside' in df.columns:
                        # Create a filtering mask for selected values
                        mask = pd.Series(False, index=df.index)
                        
                        # Handle the 'blank' option
                        if 'blank' in selected_set_asides:
                            mask |= df['typeOfSetAside'].isnull() | (df['typeOfSetAside'] == '')
                            selected_set_asides.remove('blank')
                        
                        # Handle other selected values
                        if selected_set_asides:
                            mask |= df['typeOfSetAside'].isin(selected_set_asides)
                        
                        df = df[mask]
                        if df.empty:
                            st.warning("No opportunities found matching the selected set-aside types.")
                            st.session_state.dataframe = None
                            st.stop()
                    else:
                        st.warning("No 'typeOfSetAside' data found to filter.")
                        st.stop()

                # --- Filtering logic for "Response Deadline From" ---
                if due_date_from:
                    if 'responseDeadLine' in df.columns:
                        # Convert both the column and the input date to timezone-aware datetime objects for comparison
                        df['responseDeadLine_dt'] = pd.to_datetime(df['responseDeadLine'], errors='coerce', utc=True)
                        
                        # Convert due_date_from to a UTC timezone-aware timestamp
                        due_date_from_utc = pd.to_datetime(due_date_from).tz_localize('UTC')
                        
                        # Filter out rows where responseDeadLine is NaT (invalid date)
                        df = df[df['responseDeadLine_dt'].notna()]
                        
                        # Apply the filter: keep rows where the response date is >= the selected due date
                        df = df[df['responseDeadLine_dt'] >= due_date_from_utc]
                        
                        # Drop the temporary datetime column
                        df = df.drop(columns=['responseDeadLine_dt'])

                        if df.empty:
                            st.warning("No opportunities found with a response deadline on or after the selected date.")
                            st.session_state.dataframe = None
                            st.stop()
                    else:
                        st.warning("No 'responseDeadLine' data found to filter.")
                        st.stop()
                
                st.session_state.dataframe = df
                st.success(f"{len(df)} opportunities found matching the search criteria!")
        
        except requests.exceptions.RequestException as e:
            st.error(f"An error occurred while making the request: {e}")
            st.session_state.api_results = None
            st.session_state.dataframe = None

# Custom function to format the 'placeOfPerformance' dictionary into a clean address string
def format_performance_place(pop_data):
    # Check if the data is a dictionary (the expected nested structure)
    if isinstance(pop_data, dict):
        city = pop_data.get('city', {}).get('name', 'N/A')
        state = pop_data.get('state', {}).get('code', 'N/A')
        zip_code = pop_data.get('zip', 'N/A')
        
        # Format as "City, State Zip"
        if city != 'N/A' or state != 'N/A' or zip_code != 'N/A':
            return f"{city}, {state} {zip_code}".strip(", ")
        else:
            return "Address Unavailable"
    # If the data is missing (e.g., NaN from Pandas or empty string), return a clean marker
    return "N/A"

# Custom function to format the 'responseDeadLine' string into a clean date/time string
def format_deadline(date_str):
    if not isinstance(date_str, str) or not date_str:
        return "N/A"
    try:
        # Parse the date string, which is typically ISO format
        dt_obj = pd.to_datetime(date_str, errors='coerce', utc=True)
        if pd.isna(dt_obj):
            return "Invalid Date"
            
        # Format as: YYYY-MM-DD HH:MM UTC
        return dt_obj.strftime("%Y-%m-%d %H:%M UTC") 
    except Exception:
        return "Invalid Date Format"


# Display the download buttons and results if data is available
if "dataframe" in st.session_state and st.session_state.dataframe is not None and not st.session_state.dataframe.empty:
    df = st.session_state.dataframe.copy() # Use a copy for display transformations
    
    # --- Preparation for Display ---
    df_display = df.copy()

    # 1. Format the 'placeOfPerformance' column
    if 'placeOfPerformance' in df_display.columns:
        df_display['placeOfPerformance'] = df_display['placeOfPerformance'].apply(format_performance_place)
        # Rename the column for display clarity (optional, but helpful)
        df_display.rename(columns={'placeOfPerformance': 'Place of Performance'}, inplace=True)

    # 2. Format the 'responseDeadLine' column
    if 'responseDeadLine' in df_display.columns:
        df_display['responseDeadLine'] = df_display['responseDeadLine'].apply(format_deadline)
        # Rename the column for display clarity
        df_display.rename(columns={'responseDeadLine': 'Response Deadline'}, inplace=True)


    # 3. Format the 'fullParentPathName' column to show only the initials
    if 'fullParentPathName' in df_display.columns:
        df_display['fullParentPathName'] = df_display['fullParentPathName'].apply(
            lambda x: ''.join([word[0].upper() for word in str(x).split()]) if isinstance(x, str) else ''
        )

    # 4. Create a new column with links in HTML format for display (better UX)
    if 'uiLink' in df_display.columns:
        # This column contains the HTML link string
        df_display['Opportunity Link'] = df_display['uiLink'].apply(
            lambda x: f'<a href="{x}" target="_blank">View more</a>' if isinstance(x, str) else ''
        )
        # Drop the original uiLink column
        df_display = df_display.drop(columns=['uiLink'], errors='ignore')

    # Define the columns to display and their REQUIRED ORDER
    columns_to_display = [
        'Place of Performance', 
        'fullParentPathName', 
        'title', 
        'Response Deadline', # Updated name
        'Opportunity Link', 
        'naicsCode', 
        'typeOfSetAside'
    ]
    
    # Filter the DataFrame to show only the selected columns in the correct order
    existing_columns = [col for col in columns_to_display if col in df_display.columns]
    
    # Ensure the display DataFrame is ordered correctly
    df_display = df_display[existing_columns]
    
    # --- Download button for Displayed Columns ---
    st.subheader("Search Results")
    
    # Prepare the download DataFrame: extract pure URL from HTML link
    df_download_display = df_display.copy()
    if 'Opportunity Link' in df_download_display.columns:
        # Extract only the URL from the HTML link for the Excel file
        df_download_display['Opportunity Link'] = df_download_display['Opportunity Link'].str.extract(r'href="([^"]+)"')
        # Rename the column for clarity in Excel
        df_download_display.rename(columns={'Opportunity Link': 'uiLink (Opportunity URL)'}, inplace=True)


    output_display = BytesIO()
    with pd.ExcelWriter(output_display, engine='xlsxwriter') as writer:
        df_download_display.to_excel(writer, index=False, sheet_name='Visible_Opportunities')

    st.download_button(
        label="Download Displayed File (.xlsx)",
        data=output_display.getvalue(),
        file_name="samgov_visible_opportunities.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Download button for Full File (all original fields) ---
    output_full = BytesIO()
    with pd.ExcelWriter(output_full, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='All_Opportunities')
    
    st.download_button(
        label="Download Full File (.xlsx)",
        data=output_full.getvalue(),
        file_name="samgov_all_opportunities.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Display the DataFrame in the interface using HTML to allow clickable links
    st.markdown("---")
    st.write(f"Showing {len(df_display)} results:")
    # Using st.markdown with to_html(escape=False) to ensure links are clickable
    st.markdown(df_display.to_html(escape=False, index=False), unsafe_allow_html=True)