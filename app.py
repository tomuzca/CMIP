import streamlit as st
import requests
import csv
import pandas as pd
from openpyxl import Workbook
from dotenv import load_dotenv
import os

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

        # Export to CSV
        csv_file = "samgov_opportunities_full.csv"
        with open(csv_file, mode="w", newline="", encoding="utf-8") as file:
            fieldnames = set()
            for result in processed_results:
                fieldnames.update(result.keys())
            fieldnames = sorted(fieldnames)  # Sort fields alphabetically

            writer = csv.DictWriter(file, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(processed_results)

        st.success(f"The results have been exported to {csv_file}")

        # Convert CSV to Excel
        xlsx_file = "samgov.xlsx"
        columns_to_include = [
            "postedDate",
            "solicitationNumber",
            "title",
            "responseDeadLine",
            "fullParentPathName",
            "naicsCode",
            "placeOfPerformance.state.code",
            "placeOfPerformance.state.name",
            "placeOfPerformance.city.name",
            "placeOfPerformance.city.code",
            "placeOfPerformance.zip",
            "placeOfPerformance.streetAddress",
            "uiLink"
        ]

        # Read the CSV file
        df = pd.read_csv(csv_file)

        # Filter the specified columns
        filtered_df = df[[col for col in columns_to_include if col in df.columns]]

        # Save the filtered DataFrame as an Excel file
        filtered_df.to_excel(xlsx_file, index=False, engine="openpyxl")

        st.success(f"The file {csv_file} has been successfully converted to {xlsx_file} with the specified columns.")

        # Display download links


        with open(xlsx_file, "rb") as f:
            st.download_button(
                label="Download Excel",
                data=f,
                file_name=xlsx_file,
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

    except requests.exceptions.RequestException as e:
        st.error(f"Error making the request: {e}")
    except Exception as e:
        st.error(f"An error occurred: {e}")