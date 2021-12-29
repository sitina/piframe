"""
Shows basic usage of the Photos v1 API.

Creates a Photos v1 API service and prints the names and ids of the last 10 albums
the user has access to.
"""
from __future__ import print_function
from flask import Flask
from flask import render_template

import os
import pickle
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
import google_auth_httplib2  # This gotta be installed for build() to work
import random
from datetime import datetime

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
google_photos = build('photoslibrary', 'v1', credentials = creds)

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
    # Fotorámeček
    album_id = "AF4UkVii43j_DjJwWvR-pJsQBNdK-Tgr-Qo4Xy4IevSyDLEU8dXLOzZwc0qfKNWcCuhxfXPStRqo"

    # list albums
    # albums = google_photos.albums().list().execute()
    # print(albums)

    # get album details
    # album = google_photos.albums().get(albumId = album_id).execute()
    # print(album)

    pictures = []
    nextpagetoken = 'Dummy'
    while nextpagetoken != '':
        nextpagetoken = '' if nextpagetoken == 'Dummy' else nextpagetoken
        results = google_photos.mediaItems().search(
            body={
                "albumId": album_id,
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
def albums_list():
    albums = get_albums()
    albums_list = []
    for album in albums:
        albums_list.append(album['title'] + ' / ' + album['id'])

    return render_template('albums.html', list=albums_list)


@app.route("/picture")
def get_picture():
    picture = get_random_picture()
    creation_time = datetime.strptime(
        picture['mediaMetadata']['creationTime'], "%Y-%m-%dT%H:%M:%SZ")
    creation_time_string = creation_time.strftime("%d.%m.%Y, %H:%M:%S")
    camera_make = picture['mediaMetadata']['photo'].get('cameraMake', '')
    camera_model = picture['mediaMetadata']['photo'].get('cameraModel', '')

    return render_template(
        'picture.html',
        picture = picture['baseUrl'] + '=w4096-h2048',
        creationTime = creation_time_string,
        cameraMake = camera_make,
        cameraModel = camera_model,
        filename = picture['filename']
        )


@app.route("/fullscreen")
def get_fullscreen():
    return render_template('fullscreen.html')
