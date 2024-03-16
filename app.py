from channels_dictionary import channels
import config
import googleapiclient.errors
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from googleapiclient.discovery import build
import re
import streamlit as st

# Set Streamlit page configuration
st.set_page_config(
    # Title of the page
    page_title='Youtube Analysis', 
    # Icon shown in the browser tab 
    page_icon=':bar_chart:',  
    # Wide layout for better visualization
    layout='wide'  
)

# Sidebar for user input
st.header('Keeping up with Youtubers')

# Create a list of channel names from the channels dictionary
channel_names = [channel_name for channel in channels for channel_name in channel.keys()]

# Selectbox for choosing a channel handle
selected_channel = st.selectbox("Choose a channel:", channel_names, index=0)

# Get the channel handle from the selected channel
user_input = next(iter(channel[selected_channel] for channel in channels if selected_channel in channel))

if user_input:
    # Check if user input is not empty
    api_key = config.youtube_api_key  
    # Build YouTube API client
    youtube = build('youtube', 'v3', developerKey=api_key)  
    search_response = youtube.search().list(
        # Query string obtained from user input
        q=user_input,  
        # Search for channels
        type='channel',  
        # Include only channel IDs in the response
        part='id'  
    ).execute()  # Execute the search request

    # Extract the channel ID from the search response
    channel_id = search_response['items'][0]['id']['channelId']

# Define a function to retrieve channel statistics using the YouTube API
def get_channel_stats(youtube, channel_id):
    # Create a request to fetch channel data including snippet, content details, and statistics
    request = youtube.channels().list(part="snippet,contentDetails,statistics", id=channel_id)
    # Execute the request and get the response
    response = request.execute()
    return response

# Call the function to get channel statistics for the specified channel ID
data = get_channel_stats(youtube, channel_id)

# Initialize an empty list to store channel data dictionaries
data_dict = []

# Iterate over each item in the response data
for i in data['items']:
    # Create a dictionary containing channel information
    data_dict.append(dict(
        Channel_Name=i['snippet']['title'],  # Channel name
        Description=i['snippet']['description'],  # Channel description
        subcribers=i['statistics']['subscriberCount'],  # Number of subscribers
        videoCount=i['statistics']['videoCount'],  # Number of videos
        viewCount=i['statistics']['viewCount'],  # Total view count
        uploads=i['contentDetails']['relatedPlaylists']['uploads'],  # ID of the uploads playlist
        thumbnail=i['snippet']['thumbnails']['default']['url'],  # URL of the default thumbnail
        localized=i['snippet']['country']  # Country code of the channel
    ))

# Create a DataFrame from the list of channel data dictionaries
df = pd.DataFrame(data_dict)

# Split the screen into three columns
col5, col6, col7 = st.columns(3)

# Display the channel thumbnail in the first column
with col5:
    st.image(df.iloc[0, 6], caption=None, width=200)

# Display the channel name and description in the second column
with col6:
    # Display channel name with larger font size
    st.markdown(f'<span style="font-size: 24px">{df.iloc[0, 0]}</span>', unsafe_allow_html=True)
    # Add an expander for the channel description
    with st.expander('Channel Description'):
        st.write(df.iloc[0, 1])

# Extract the uploads playlist ID from the DataFrame
playlistId = df.iloc[0, 5]

# Convert videoCount, viewCount, and subcribers columns to numeric data types
df['videoCount'] = pd.to_numeric(df['videoCount'])
df['viewCount'] = pd.to_numeric(df['viewCount'])
df['subcribers'] = pd.to_numeric(df['subcribers'])

# Define a function to retrieve video IDs from a given playlist using the YouTube API
def get_video_id(youtube, playlistId):
    # Create a request to fetch video IDs from the specified playlist
    request = youtube.playlistItems().list(part="contentDetails", playlistId=playlistId, maxResults=50)
    # Execute the request and get the response
    response = request.execute()
    # Initialize an empty list to store video IDs
    video_ids = []
    # Iterate over each item in the response data to extract video IDs
    for i in response['items']:
        video_ids.append(i['contentDetails']['videoId'])
    # Check if there are more pages of results available
    next_page_token = response.get('nextPageToken')
    more_pages = True
    # Continue fetching more pages until there are no more results
    while more_pages:
        # If there are no more pages, exit the loop
        if next_page_token is None:
            more_pages = False
        else:
            # Fetch the next page of results using the page token
            request = youtube.playlistItems().list(
                part='contentDetails',
                playlistId=playlistId,
                maxResults=50,
                pageToken=next_page_token
            )
            # Execute the request and get the response
            response = request.execute()
            # Iterate over each item in the response data to extract video IDs
            for i in range(len(response['items'])):
                video_ids.append(response['items'][i]['contentDetails']['videoId'])
            # Get the token for the next page, if available
            next_page_token = response.get('nextPageToken')
    # Return the list of video IDs
    return video_ids

# Call the function to retrieve video IDs from the specified playlist
d = get_video_id(youtube, playlistId)

# Define a function to retrieve detailed information about videos using their IDs
def get_video_topic(youtube, d):
    # Initialize an empty list to store video data
    video_data = []
    # Loop through the list of video IDs, processing 50 at a time (due to YouTube API limitations)
    for j in range(0, len(d), 50):
        # Create a request to fetch video details for the current batch of IDs
        request = youtube.videos().list(part="snippet,statistics,topicDetails", id=",".join(d[j:j+50]))
        # Execute the request and get the response
        response = request.execute()
        # Extract relevant information from each video item in the response
        for i in response['items']:
            # Create a dictionary containing video details
            data = dict(
                Tilte=i['snippet']['title'],  # Video title
                Publishedat=i['snippet']['publishedAt'],  # Published date and time
                Views=i['statistics']['viewCount'] if 'viewCount' in i['statistics'] else 0,  # Number of views
                like=i['statistics']['likeCount'] if 'likeCount' in i['statistics'] else 0,  # Number of likes
                comment=i['statistics']['commentCount'] if 'commentCount' in i['statistics'] else 0,  # Number of comments
                topic=i['topicDetails']['topicCategories'] if 'topicDetails' in i else None  # Video topic categories
            )
            # Append the video data to the list
            video_data.append(data)
    # Return the list of video data
    return video_data

# Call the function to retrieve detailed information about the videos
whole_data = get_video_topic(youtube, d)
# Convert the list of video data into a DataFrame
whole_data = pd.DataFrame(whole_data)

# Convert 'Views', 'like', and 'comment' columns to numeric data types
whole_data['Views'] = pd.to_numeric(whole_data['Views'])
whole_data['like'] = pd.to_numeric(whole_data['like'])
whole_data['comment'] = pd.to_numeric(whole_data['comment'])

# Extract the 'Publishedat' column for further processing
extra_date = whole_data['Publishedat']
# Convert 'Publishedat' column to string format representing date (YYYY-MM-DD)
#whole_data['Publishedat'] = whole_data['Publishedat'].dt.strftime('%Y-%m-%d')
# Convert 'Publishedat' column to string format representing date (YYYY-MM-DD)
whole_data['Publishedat'] = pd.to_datetime(whole_data['Publishedat'])
# Rename the column header "Publishedat" as "Published"
#whole_data.rename(columns={'Publishedat': 'Published'}, inplace=True)

# Define a function to format large numbers into a more readable format
def million(value):
    # If the value is less than 1000, return as is or round if necessary
    if value < 1000:
        if '.0' in str(value):
            return str(round(value))
        return '{:.2f}'.format(value)
    # If the value is between 1000 and 1 million, convert to 'K' (thousands) format
    if value < 1000000 and value >= 1000:
        k = value / 1000
        if '.0' in str(k):
            return str(round(k)) + 'K'
        return '{:.2f}'.format(k) + 'K'
    # If the value is between 1 million and 1 billion, convert to 'M' (millions) format
    if value >= 1000000 and value < 1000000000:
        million = value / 1000000
        if '.0' in str(million):
            return str(round(million)) + 'M'
        return '{:.2f}'.format(million) + 'M'
    # If the value is 1 billion or more, convert to 'B' (billions) format
    if value >= 1000000000:
        billion = value / 1000000000
        if '.0' in str(billion):
            return str(round(billion)) + 'B'
        return '{:.2f}'.format(billion) + 'B'
    # If the value is not in any of the above ranges, return 's'
    return 's'

# Filter out rows with titles containing 'shorts' or 'short'
whole_data = whole_data[~whole_data['Tilte'].str.contains('shorts')]
whole_data = whole_data[~whole_data['Tilte'].str.contains('short')]

# Select the top 20 videos and reset index
top_10_videos = whole_data.head(20)
top_10_videos = top_10_videos.reset_index()
top_10_videos = top_10_videos.drop(['index'], axis=1)

# Display channel information metrics
st.markdown('### Channel Info :information_source:')
col1, col2, col3 = st.columns(3)
col1.metric("Subcribers", million(df.iloc[0, 2]))  # Display number of subscribers
col2.metric("Total Views", million(df.iloc[0, 4]))  # Display total views
col3.metric("Total Videos", str(df.iloc[0, 3]))  # Display total videos

# Calculate additional metrics
col8, col9, col10 = st.columns(3)
whole_data['Year'] = whole_data['Publishedat'].dt.year
whole_data['Month'] = whole_data['Publishedat'].dt.month
whole_data['Day'] = whole_data['Publishedat'].dt.day
z = whole_data.groupby('Year')['Views'].sum()  # Group views by year
z = z.reset_index()
average = (z['Views'].mean()) / 1000  # Calculate average views per video in thousands

# Display additional metrics
col8.metric("Average Likes", million(top_10_videos['like'].mean()))  # Display average likes
col9.metric('Country', df.iloc[0, 7])  # Display country
col10.metric('Yearly Revenue', million(round(average * 0.2)) + "-" + million(round(average * 4.5)))  # Display yearly revenue range

# Extracting 'topic' column from 'whole_data' and processing it
arr = np.array(whole_data['topic'])
l = []
for x in arr:
    if x is not None:
        # Extracting the first element of each non-null entry
        l.append(x[0])  
    else:
        # Replacing null values with 'NaN'
        l.append('NaN')  
whole_data['Category'] = l

# Extracting relevant information from 'Category' column using regular expressions
whole_data['Category'] = whole_data['Category'].str.extract('([$a-zA-Z0-9_\-\().]+$)')

# Selection widget options
options = ["Views", "Likes", "Comments"]
selected_option = st.selectbox("Overall ", options)
names = whole_data['Tilte']

# Plotting based on the selected option
if selected_option == "Views":
    # Creating a plot for Views
    plot = go.Figure()
    plot.add_trace(go.Scatter(
        name='Views',
        x=whole_data.iloc[:, 1],  # x-axis: Date
        y=whole_data.iloc[:, 2],  # y-axis: Views
        text=names,  # Text for hover
        hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Views: %{y}<extra></extra>',  # Hover template
        stackgroup='one'
    ))
    st.write(plot)  # Displaying the plot
    
    # Providing options for selecting the number of recent videos
    options = ['Last 20 Videos', 'Last 30 Videos']
    selectbox = st.selectbox('', options)
    if selectbox == options[0]:
        # Plotting Views for the last 20 videos
        plot = go.Figure()
        plot.add_trace(go.Scatter(
            name='Views',
            x=whole_data.iloc[0:20, 1],
            y=whole_data.iloc[0:20, 2],
            text=names,
            hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Views: %{y}<extra></extra>',
            stackgroup='one'
        ))
        dataframe = whole_data.iloc[0:20, [0, 1, 2, 3, 4]].reset_index(drop=True)
        st.write(plot)  # Displaying the plot
        st.dataframe(dataframe)  # Displaying the dataframe
    elif selectbox == options[1]:
        # Plotting Views for the last 30 videos
        plot = go.Figure()
        plot.add_trace(go.Scatter(
            name='Views',
            x=whole_data.iloc[0:30, 1],
            y=whole_data.iloc[0:30, 2],
            text=names,
            hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Views: %{y}<extra></extra>',
            stackgroup='one'
        ))
        dataframe = whole_data.iloc[0:30, [0, 1, 2, 3, 4]].reset_index(drop=True)
        st.write(plot)  # Displaying the plot
        st.dataframe(dataframe)  # Displaying the dataframe

    # Finding and displaying the top three categories based on Views
    top_views_categories = whole_data.groupby('Category')['Views'].sum().nlargest(3)
    st.markdown('### Top :three: Categories Based on Views')
    st.write(top_views_categories)

elif selected_option == "Likes":
    # Plotting Likes over time
    plot = go.Figure()
    plot.add_trace(go.Scatter(
        name='like',
        x=whole_data['Publishedat'],  # x-axis: Published Date
        y=whole_data['like'],  # y-axis: Likes
        text=names,  # Text for hover
        hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Likes: %{y}<extra></extra>',  # Hover template
        stackgroup='one'
    ))
    st.write(plot)  # Displaying the plot
    
    # Providing options for selecting the number of recent videos
    options = ['Last 20 Videos', 'Last 30 Videos']
    selectbox = st.selectbox('', options)
    if selectbox == options[0]:
        # Plotting Likes for the last 20 videos
        plot = go.Figure()
        plot.add_trace(go.Scatter(
            name='like',
            x=whole_data.iloc[0:20, 1],
            y=whole_data.iloc[0:20, 3],
            text=names,
            hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Likes: %{y}<extra></extra>',
            stackgroup='one'
        ))
        dataframe = whole_data.iloc[0:20, [0, 1, 2, 3, 4]].reset_index(drop=True)
        st.write(plot)  # Displaying the plot
        st.dataframe(dataframe)  # Displaying the dataframe
    elif selectbox == options[1]:
        # Plotting Likes for the last 30 videos
        plot = go.Figure()
        plot.add_trace(go.Scatter(
            name='like',
            x=whole_data.iloc[0:30, 1],
            y=whole_data.iloc[0:30, 3],
            text=names,
            hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Likes: %{y}<extra></extra>',
            stackgroup='one'
        ))
        dataframe = whole_data.iloc[0:30, [0, 1, 2, 3, 4]].reset_index(drop=True)
        st.write(plot)  # Displaying the plot
        st.dataframe(dataframe)  # Displaying the dataframe

    # Finding and displaying the top three categories based on Likes
    top_like_categories = whole_data.groupby('Category')['like'].sum().nlargest(3)
    st.markdown('### Top :three: Categories Based on Likes')
    st.write(top_like_categories)

elif selected_option == "Comments":
    # Plotting Comments over time
    plot = go.Figure()
    plot.add_trace(go.Scatter(
        name='comment',
        x=whole_data['Publishedat'],  # x-axis: Published Date
        y=whole_data['comment'],  # y-axis: Comments
        stackgroup='one'
    ))
    st.write(plot)  # Displaying the plot
    
    # Providing options for selecting the number of recent videos
    options = ['Last 20 Videos', 'Last 30 Videos']
    selectbox = st.selectbox('', options)
    if selectbox == options[0]:
        # Plotting Comments for the last 20 videos
        plot = go.Figure()
        plot.add_trace(go.Scatter(
            name='like',
            x=whole_data.iloc[0:20, 1],
            y=whole_data.iloc[0:20, 4],
            text=names,
            hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Comments: %{y}<extra></extra>',
            stackgroup='one'
        ))
        dataframe = whole_data.iloc[0:20, [0, 1, 2, 3, 4]].reset_index(drop=True)
        st.write(plot)  # Displaying the plot
        st.dataframe(dataframe)  # Displaying the dataframe
    elif selectbox == options[1]:
        # Plotting Comments for the last 30 videos
        plot = go.Figure()
        plot.add_trace(go.Scatter(
            name='Comment',
            x=whole_data.iloc[0:30, 1],
            y=whole_data.iloc[0:30, 4],
            text=names,
            hovertemplate='<b>%{text}</b><br>Date: %{x}<br>Comments: %{y}<extra></extra>',
            stackgroup='one'
        ))
        dataframe = whole_data.iloc[0:30, [0, 1, 2, 3, 4]].reset_index(drop=True)
        st.write(plot)  # Displaying the plot
        st.dataframe(dataframe)  # Displaying the dataframe

    # Finding and displaying the top three categories based on Comments
    top_comment_categories = whole_data.groupby('Category')['comment'].sum().nlargest(3)
    st.markdown('### Top :three: Categories Based on Comments')
    st.write(top_comment_categories)

# Displaying all-time favorite videos
st.markdown('### All Time Favorites :sparkling_heart:')
all_time_favorites = whole_data.sort_values(by=['Views'], ascending=False).iloc[:6, [0, 1, 2, 3, 4, 9]]
st.dataframe(all_time_favorites)
