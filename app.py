import streamlit as st
import requests
import pandas as pd
from io import BytesIO
from dotenv import load_dotenv
import os
from openpyxl import Workbook
from openpyxl.utils.dataframe import dataframe_to_rows
from openpyxl.worksheet.filters import AutoFilter

# Load environment variables from the .env file
load_dotenv()

# Configuration
API_KEY = os.getenv("API_KEY")  # Load the API key from the .env file
if not API_KEY:
    st.error("The API key is not configured. Make sure to define 'API_KEY' in the .env file.")
    st.stop()

BASE_URL = "https://api.sam.gov/opportunities/v2/search"  # Updated endpoint

# App title
st.title("SAM.gov Opportunities Generator")
st.write("This app allows you to search for opportunities on SAM.gov and export the results to Excel files.")

# User inputs
st.sidebar.header("Search Parameters")
posted_from = st.sidebar.date_input("Start Date (postedFrom)", value=None, min_value=None, max_value=None)
posted_to = st.sidebar.date_input("End Date (postedTo)", value=None, min_value=None, max_value=None)
limit = st.sidebar.number_input("Results Limit (limit)", min_value=1, max_value=1000, value=100, step=1)

# Convert dates to MM/dd/yyyy format
if posted_from and posted_to:
    posted_from_str = posted_from.strftime("%m/%d/%Y")
    posted_to_str = posted_to.strftime("%m/%d/%Y")
else:
    st.error("Please select both start and end dates.")
    st.stop()

# Button to execute the search
if st.sidebar.button("Search Opportunities"):
    # Search parameters
    params = {
        "api_key": API_KEY,
        "typeOfSetAside": "SBA",  # Total Small Business Set-Aside
        "postedFrom": posted_from_str,
        "postedTo": posted_to_str,
        "limit": limit,  # Number of results per page
        "offset": 0,  # Pagination
        "ptype": "o",  # Procurement type (solicitation)
    }

    # Make the request
    try:
        st.write("Making the request to the API...")
        response = requests.get(BASE_URL, params=params)
        response.raise_for_status()  # Raise an exception for HTTP errors
        data = response.json()  # Parse the JSON response

        # Process the results
        results = data.get("opportunitiesData", [])
        if not results:
            st.warning("No results found.")
            st.stop()

        # Dynamically extract all available fields
        processed_results = []
        for idx, opportunity in enumerate(results, start=1):
            flattened_opportunity = {}

            def flatten_dict(d, parent_key=""):
                """Recursive function to flatten a nested dictionary."""
                for k, v in d.items():
                    new_key = f"{parent_key}.{k}" if parent_key else k
                    if isinstance(v, dict):
                        flatten_dict(v, new_key)
                    else:
                        flattened_opportunity[new_key] = v

            flatten_dict(opportunity)
            processed_results.append(flattened_opportunity)

        # Convert results to a DataFrame
        df = pd.DataFrame(processed_results)

        # Exclude the "archiveType" column if it exists
        if "archiveType" in df.columns:
            df = df.drop(columns=["archiveType", "naicsCodes", "pointOfContact", "description", "organizationType","additionalInfoLink", "award.awardee.manual", "fullParentPathCode", "noticeId", "typeOfSetAsideDescription", "pointOfContact", ])

        # Save the DataFrame to an Excel file with filters and frozen header
        output = BytesIO()
        wb = Workbook()
        ws = wb.active
        ws.title = "Opportunities"

        # Write the DataFrame to the worksheet
        for r_idx, row in enumerate(dataframe_to_rows(df, index=False, header=True), start=1):
            ws.append(row)
            if r_idx == 1:
                # Apply filters to the first row
                ws.auto_filter.ref = ws.dimensions

        # Freeze the first row
        ws.freeze_panes = "A2"

        # Save the workbook to the BytesIO object
        wb.save(output)
        output.seek(0)

        # Provide a download button for the Excel file
        st.success("The data has been successfully processed!")
        st.download_button(
            label="Download Excel File",
            data=output,
            file_name="samgov_opportunities.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Display the DataFrame in the app
        st.dataframe(df)

    except requests.exceptions.RequestException as e:
        st.error(f"An error occurred while making the request: {e}")