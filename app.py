"""
Shows basic usage of the Photos v1 API.

Creates a Photos v1 API service and prints the names and ids of the last 10 albums
the user has access to.
"""
from __future__ import print_function
from flask import Flask
from markupsafe import escape

import os
import pickle
import json
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import google_auth_httplib2  # This gotta be installed for build() to work
from statistics import mean
# import matplotlib.pyplot as plt
# import numpy as np
# %matplotlib inline

# Setup the Photo v1 API
SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
creds = None
if(os.path.exists("token.pickle")):
    with open("token.pickle", "rb") as tokenFile:
        creds = pickle.load(tokenFile)
if not creds or not creds.valid:
    if (creds and creds.expired and creds.refresh_token):
        creds.refresh(Request())
    else:
        flow = InstalledAppFlow.from_client_secrets_file('client_secret.json', SCOPES)
        creds = flow.run_local_server(port = 0)
    with open("token.pickle", "wb") as tokenFile:
        pickle.dump(creds, tokenFile)
service = build('photoslibrary', 'v1', credentials = creds)

google_photos = build('photoslibrary', 'v1', credentials = creds)


app = Flask(__name__)


@app.route("/")
def hello_world():
    return "<p>Hello, World!</p>"


@app.route("/<name>")
def hello(name):
    return f"Hello, {escape(name)}!"


@app.route("/picture")
def get_picture():
    day, month, year = ('27', '12', '2021')  # Day or month may be 0 => full month resp. year
    date_filter = [{"day": day, "month": month, "year": year}]  # No leading zeroes for day an month!
    nextpagetoken = 'Dummy'
    focalLengths = []
    baseUrls = []
    while nextpagetoken != '':
        nextpagetoken = '' if nextpagetoken == 'Dummy' else nextpagetoken
        results = google_photos.mediaItems().search(
                body={ "filters":  {"dateFilter": {"dates": [{"day": day, "month": month, "year": year}]}},
                      "pageSize": 100, "pageToken": nextpagetoken}).execute()
        # The default number of media items to return at a time is 25. The maximum pageSize is 100.
        items = results.get('mediaItems', [])
        nextpagetoken = results.get('nextPageToken', '')
        for item in items:
            if ('photo' in item['mediaMetadata']):
                if ('cameraMake' in item['mediaMetadata']['photo'] and item['mediaMetadata']['photo']['cameraMake'] == 'FUJIFILM'):
                    # print('{0}'.format(item['mediaMetadata']['photo']))
                    if ('focalLength' in item['mediaMetadata']['photo']):
                        print('{0}'.format(item['mediaMetadata']['photo']['focalLength']))
                        print(item)
                        print(item['baseUrl'])
                        baseUrls.append(item['baseUrl'])
                        focalLengths.append(item['mediaMetadata']['photo']['focalLength'])
                    else:
                        print('-')

    print(focalLengths)
    print(mean(focalLengths))
    return f"Hello, {escape(focalLengths)}, {escape(baseUrls)}!"