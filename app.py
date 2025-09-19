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

# App title
st.title("SAM.gov Search Engine")
st.write("This app allows you to search for opportunities on SAM.gov and export the results to an Excel file.")

# Search parameters section in the sidebar
st.sidebar.header("Search Parameters")
posted_from = st.sidebar.date_input("Start Date (postedFrom)", value=None)
posted_to = st.sidebar.date_input("End Date (postedTo)", value=None)
# Filter for NAICS starting with 23
include_naics_23 = st.sidebar.checkbox("Include NAICS Code Filter (Starts with 23)")
# New filter for "typeOfSetAside"
selected_set_asides = st.sidebar.multiselect(
    "Set-Aside Filter",
    options=['blank', 'SBA', 'SBP', '8A', '8AN', 'HZC', 'HZS', 'SDVOSBC', 'SDVOSBS', 'WOSB', 'WOSBSS', 'EDWOSB', 'EDWOSBSS', 'LAS', 'IEE', 'ISBEE', 'BICiv', 'VSA', 'VSS', 'NONE']
)

# Button to start the search
if st.sidebar.button("Search Opportunities"):
    if not posted_from or not posted_to:
        st.error("Please select both a start date and an end date.")
    else:
        # Convert dates to "MM/DD/YYYY" string format
        posted_from_str = posted_from.strftime("%m/%d/%Y")
        posted_to_str = posted_to.strftime("%m/%d/%Y")

        # Define API request parameters
        params = {
            "api_key": API_KEY,
            "postedFrom": posted_from_str,
            "postedTo": posted_to_str,
            "limit": 1000, # Maximum limit of results per request
            "offset": 0,
            "ptype": "o", # Publication type (opportunities)
            "fields": "postedDate,title,type,baseType,noticeId,naicsCode,description,originalPublishedDate,typeOfSetAside,fullParentPathNAme,uiLink,responseDeadLine"
        }

        try:
            st.write("Making the API request...")
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

                # --- Improved NAICS filtering logic ---
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
                # --- End of filtering logic ---

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
                # --- End of "typeOfSetAside" filtering logic ---
                
                st.session_state.dataframe = df
                st.success(f"{len(df)} opportunities found matching the search criteria.")
        
        except requests.exceptions.RequestException as e:
            st.error(f"An error occurred while making the request: {e}")
            st.session_state.api_results = None
            st.session_state.dataframe = None

# Display the download button if data is available
if "dataframe" in st.session_state and st.session_state.dataframe is not None and not st.session_state.dataframe.empty:
    df = st.session_state.dataframe
    
    # Create a copy of the DataFrame to manipulate display columns
    df_display = df.copy()

    # Format the 'fullParentPathNAme' column to show only the initials
    if 'fullParentPathName' in df_display.columns:
        df_display['fullParentPathName'] = df_display['fullParentPathName'].apply(
            lambda x: ''.join([word[0].upper() for word in str(x).split()]) if isinstance(x, str) else ''
        )

    # Create a new column with links in HTML format for display
    if 'uiLink' in df_display.columns:
        df_display['Opportunity Link'] = df_display['uiLink'].apply(
            lambda x: f'<a href="{x}" target="_blank">View more</a>' if isinstance(x, str) else ''
        )

    # Define the columns to display and their order
    columns_to_display = ['fullParentPathName', 'title', 'Opportunity Link', 'responseDeadLine', 'naicsCode', 'typeOfSetAside']
    
    # Filter the DataFrame to show only the selected columns in the correct order
    existing_columns = [col for col in columns_to_display if col in df_display.columns]
    df_display = df_display[existing_columns]
    
    # --- Download button for visible columns (updated) ---
    output_display = BytesIO()
    # Create a new DataFrame for the download file to not include the HTML link
    df_download_display = df_display.copy()
    if 'Opportunity Link' in df_download_display.columns:
        df_download_display['Opportunity Link'] = df_download_display['Opportunity Link'].str.extract(r'href="([^"]+)"')

    with pd.ExcelWriter(output_display, engine='xlsxwriter') as writer:
        df_download_display.to_excel(writer, index=False, sheet_name='Opportunities')

    st.download_button(
        label="Download Displayed File (.xlsx)",
        data=output_display.getvalue(),
        file_name="samgov_opportunities_displayed.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # --- Download button for full file ---
    output_full = BytesIO()
    with pd.ExcelWriter(output_full, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='All Opportunities')
    
    st.download_button(
        label="Download Full File (.xlsx)",
        data=output_full.getvalue(),
        file_name="samgov_opportunities_full.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Display the DataFrame in the interface.
    st.markdown(df_display.to_html(escape=False), unsafe_allow_html=True)