"""
The application serves random photo from google photos album
"""
import os
import pickle
import json
import random

from flask import Flask
from flask import render_template
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from datetime import datetime
from dateutil import parser

album = ''
app = Flask(__name__)

def get_albums():
    # list albums
    albums = []
    nextpagetoken = 'Dummy'
    while nextpagetoken != '':
        nextpagetoken = '' if nextpagetoken == 'Dummy' else nextpagetoken
        results = google_photos.albums().list(pageSize=50, pageToken = nextpagetoken).execute()
        items = results.get('albums', [])
        albums.extend(items)
        nextpagetoken = results.get('nextPageToken', '')

    # print(albums)
    return albums

def is_picture(value):
    return 'photo' in value['mediaMetadata']

def get_random_picture():
    pictures = []
    nextpagetoken = 'Dummy'
    while nextpagetoken != '':
        nextpagetoken = '' if nextpagetoken == 'Dummy' else nextpagetoken
        results = google_photos.mediaItems().search(
            body={
                "albumId": album,
                "pageSize": 100,
                "pageToken": nextpagetoken
                }).execute()
        items = results.get('mediaItems', [])
        pictures.extend(list(filter(is_picture, items)))
        nextpagetoken = results.get('nextPageToken', '')

    picture = random.choice(pictures)

    # print(picture)
    print(picture['mediaMetadata']['creationTime'])
    print(picture['mediaMetadata']['photo'].get('cameraMake', ''))
    print(picture['mediaMetadata']['photo'].get('cameraModel', ''))
    print(picture['filename'])
    return picture

@app.route("/")
def home():
    return get_fullscreen()

@app.route("/albums")
def list_albums():
    albums = get_albums()
    albums_list = []
    for a in albums:
        albums_list.append(a['title'] + ' / ' + a['id'])

    return render_template('albums.html', list=albums_list)

@app.route("/picture")
def get_picture():
    picture = get_random_picture()
    creation_timestamp = parser.parse(picture['mediaMetadata']['creationTime'])
    creation_date = creation_timestamp.strftime("%d.%m.%Y")
    creation_time = creation_timestamp.strftime("%H:%M:%S %Z")
    camera_make = picture['mediaMetadata']['photo'].get('cameraMake', '')
    camera_model = picture['mediaMetadata']['photo'].get('cameraModel', '')

    return render_template(
        'picture.html',
        picture = picture['baseUrl'] + '=w4096-h2048',
        creationDate = creation_date,
        creationTime = creation_time,
        cameraMake = camera_make,
        cameraModel = camera_model,
        filename = picture['filename']
        )

@app.route("/fullscreen")
def get_fullscreen():
    return render_template('fullscreen.html')


SCOPES = ['https://www.googleapis.com/auth/photoslibrary.readonly']
creds = None
if os.path.exists("token.pickle"):
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
google_photos = build('photoslibrary', 'v1', credentials = creds)

try:
    with open("config.json", "r") as f:
        print('loading config')
        config = json.load(f)
        album = config['album']
        print(album)
except FileNotFoundError:
    print('loading config failed')
    album = get_albums()[0]['id']
    print(album)
    config = {
        "album" : album
    }
    config_json = json.dumps(config)

    with open("config.json", "w") as jsonfile:
        jsonfile.write(config_json)
        print("album written to config file")
