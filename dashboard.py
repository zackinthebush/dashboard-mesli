import streamlit as st
from oauth2client.client import OAuth2WebServerFlow
from oauth2client.client import AccessTokenRefreshError
from googleapiclient.discovery import build
import webbrowser
from urllib.parse import parse_qs, urlparse
import socketserver
import threading
import http.server
import httplib2
import pandas as pd
import pickle
import os

CLIENT_ID = "1040351413672-nditroua07qnbrlh5q26gmf2gpdn61vd.apps.googleusercontent.com"
CLIENT_SECRET = "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"
OAUTH_SCOPE = "https://www.googleapis.com/auth/webmasters.readonly"
REDIRECT_URI = 'http://127.0.0.1:8000/'  # Should match the redirect URI used when setting up the API key

# Path to saved credentials file
credentials_path = 'credentials.pickle'

# Function to load credentials from a file
def load_credentials():
    if os.path.exists(credentials_path):
        with open(credentials_path, 'rb') as credentials_file:
            return pickle.load(credentials_file)
    return None

# Function to save credentials to a file
def save_credentials(creds):
    with open(credentials_path, 'wb') as credentials_file:
        pickle.dump(creds, credentials_file)

# Attempt to load credentials
credentials = load_credentials()

# Check if the credentials are valid, if they exist
if credentials:
    # Check if access token has expired and try to refresh it
    if credentials.access_token_expired:
        try:
            http = httplib2.Http()
            credentials.refresh(http)
            save_credentials(credentials)
        except AccessTokenRefreshError:
            # Handle the error, e.g., re-initiate the auth flow
            credentials = None

# If credentials are not valid or do not exist, initiate the auth flow
if not credentials:
    flow = OAuth2WebServerFlow(client_id=CLIENT_ID,
                               client_secret=CLIENT_SECRET,
                               scope=OAUTH_SCOPE,
                               redirect_uri=REDIRECT_URI)
    authorize_url = flow.step1_get_authorize_url()

    redirected_url = None

    class RedirectHandler(http.server.SimpleHTTPRequestHandler):
        def do_GET(self):
            global redirected_url
            redirected_url = self.path
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()
            self.wfile.write(b'Redirect URL captured. You can close this window now.')

    def start_server():
        with socketserver.TCPServer(('127.0.0.1', 8000), RedirectHandler) as httpd:
            httpd.handle_request()

    server_thread = threading.Thread(target=start_server)
    server_thread.daemon = True
    server_thread.start()

    webbrowser.open(authorize_url)
    server_thread.join()

    if redirected_url:
        parsed_url = urlparse(redirected_url)
        auth_code = parse_qs(parsed_url.query).get('code', [None])[0]
        credentials = flow.step2_exchange(auth_code)
        save_credentials(credentials)

http = credentials.authorize(httplib2.Http())
webmasters_service = build('searchconsole', 'v1', http=http)
st.write("Authentication successful. You can now access the Google Search Console API.")

# the website we want to get the data for
website = "https://www.mesli-consulting.com/"

# build a request body
request_body = {
    "startDate"	: '2023-03-07',
    "endDate" : '2024-03-14',
    "dimensions" : ['DATE','QUERY', 'PAGE' , 'country' ],
    "rowLimit" : 25000,
    "dataState" : "final"
}

# get the response using request body
response_data = webmasters_service.searchanalytics().query(siteUrl=website, body=request_body).execute()

formatted_data = [{
    'Date': row['keys'][0],  # This is assuming the first dimension you request is 'date'
    'Query': row['keys'][1],  # Adjust according to the actual response structure
    'Page': row['keys'][2],
    'Country': row['keys'][3],
    'Clicks': row['clicks'],
    'Impressions': row['impressions'],
    'CTR': row['ctr'],
    'Position': row['position']
} for row in response_data.get('rows', [])]

data = pd.DataFrame(formatted_data)
data['Date'] = pd.to_datetime(data['Date'])
data['Clicks'] = pd.to_numeric(data['Clicks'], errors='coerce')
data['Impressions'] = pd.to_numeric(data['Impressions'], errors='coerce')
data['CTR'] = pd.to_numeric(data['CTR'], errors='coerce')
data['Position'] = pd.to_numeric(data['Position'], errors='coerce')
unique_countries = data['Country'].unique().tolist()

 
st.title('Search Console Dashboard')
st.write("This is a simple dashboard showing data from Google Search Console.")

if st.button('Activate Script'):
    st.markdown("""
        <style>
        .stMultiSelect > div > div > div {
            display: none !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
if st.button('Deactivate Script'):
    st.markdown("""
        <style>
        .stMultiSelect > div > div > div {
            display: block !important;
        }
        </style>
        """, unsafe_allow_html=True)


start_date = st.date_input('Start date', value=pd.to_datetime('2023-03-07'))
end_date = st.date_input('End date', value=pd.to_datetime('today').date())



filtered_data = data[(data['Date'] >= pd.to_datetime(start_date)) & (data['Date'] <= pd.to_datetime(end_date))]


selected_countries = st.multiselect('Select countries to plot', unique_countries, default=unique_countries)

filtered_data_by_country = filtered_data[filtered_data['Country'].isin(selected_countries)]


query_input = st.text_input("Search queries")


if query_input:

    matching_queries = data[data['Query'].str.contains(query_input, case=False, na=False)]['Query'].unique().tolist()
else:
    # If no input, consider all queries
    matching_queries = data['Query'].unique().tolist()

selected_queries = st.multiselect("Select queries", options=matching_queries, default=matching_queries)

# Display a summary of selections instead of listing all
if selected_queries:
    st.write(f"{len(selected_queries)} queries selected.")
filtered_data_by_query = filtered_data_by_country[filtered_data_by_country['Query'].isin(selected_queries)]

options = st.multiselect(
    'Select the metrics you want to plot',
    ['Clicks', 'Impressions', 'CTR', 'Position'],  # Options based on your dataframe columns
    ['Clicks', 'Impressions']  # Default selected values
)


# Update columns_to_plot based on the selection
columns_to_plot = options if options else ['Clicks', 'Impressions']  # Fallback to defaults if nothing is selected

# Plot the selected data
aggregated_data = filtered_data_by_query.groupby('Date').agg({
    'Clicks': 'sum',
    'Impressions': 'sum',
    'CTR': 'mean',
    'Position': 'mean'
}).reset_index()

# Ensure 'Date' is the index for plotting
aggregated_data.set_index('Date', inplace=True)
# Determine which columns to based on user selection
columns_to_plot = options if options else ['Clicks', 'Impressions']  # Default fallback

# Plot the selected data using the aggregated DataFrame
st.line_chart(aggregated_data[columns_to_plot])

#plot a bar chart to show the number of clicks by country
selected_column = st.multiselect('Select column to plot', ['Clicks', 'Impressions', 'Position', 'CTR'], default=['Clicks'], key='unique_key')

if selected_column:
    if 'Position' in selected_column or 'CTR' in selected_column:
        agg_dict = {col: 'mean' if col in ['Position', 'CTR'] else 'sum' for col in selected_column}
        data_to_plot = filtered_data_by_query.groupby('Country')[selected_column].agg(agg_dict).sort_values(by=selected_column, ascending=False)
    else:
        data_to_plot = filtered_data_by_query.groupby('Country')[selected_column].sum().sort_values(by=selected_column, ascending=False)
    st.bar_chart(data_to_plot)  

    # Plot a bar chart to show the number of clicks by page
selected_columns = st.multiselect('Select column to plot', ['Clicks', 'Impressions', 'Position', 'CTR'], default=['Clicks'], key='unique_keys')

if selected_columns:
    if 'Position' in selected_columns or 'CTR' in selected_columns:
        agg_dict = {col: 'mean' if col in ['Position', 'CTR'] else 'sum' for col in selected_columns}
        data_to_plot = filtered_data_by_query.groupby('Page')[selected_columns].agg(agg_dict).sort_values(by=selected_columns, ascending=False)
    else:
        data_to_plot = filtered_data_by_query.groupby('Page')[selected_columns].sum().sort_values(by=selected_columns, ascending=False)
    st.bar_chart(data_to_plot)


# Optionally, display the filtered dataframe
st.dataframe(aggregated_data)