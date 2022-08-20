"""
The application serves random photo from google photos album
"""
import os
import pickle
import json
import random
from jinja2 import TemplateAssertionError
import requests
import time

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
        results = google_photos.albums().list(
            pageSize=50, pageToken=nextpagetoken).execute()
        items = results.get('albums', [])
        albums.extend(items)
        nextpagetoken = results.get('nextPageToken', '')

    # print(albums)
    return albums


def is_picture(value):
    return 'photo' in value['mediaMetadata']


def get_random_picture():
    pictures = []
    ts = time.time()
    # cache pictures for one hour to save API calls
    if ts - pictures_cache['ts'] > 3600:
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

        pictures_cache['ts'] = ts
        pictures_cache['data'] = pictures
    else:
        pictures = pictures_cache['data']

    picture = random.choice(pictures)

    # print(picture)
    print(picture['mediaMetadata']['creationTime'])
    print(picture['mediaMetadata']['photo'].get('cameraMake', ''))
    print(picture['mediaMetadata']['photo'].get('cameraModel', ''))
    print(picture['filename'])
    return picture


def get_weather():
    ts = time.time()
    if ts - weather_cache['ts'] > 300:
        # print('fetching fresh weather data')
        if (weather_api_key):
            weather_url = f"http://api.openweathermap.org/data/2.5/weather?appid={weather_api_key}&q={weather_location}"
            weather_data = requests.get(weather_url).json()
            weather_cache['ts'] = ts
            weather_cache['data'] = weather_data
            return weather_data
    else:
        # print('using weather cache')
        return weather_cache['data']


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
    creation_date = creation_timestamp.strftime("%-d.%-m.%Y")
    creation_time = creation_timestamp.strftime("%H:%M:%S %Z")
    camera_make = picture['mediaMetadata']['photo'].get('cameraMake', '')
    camera_model = picture['mediaMetadata']['photo'].get('cameraModel', '')
    weather = get_weather()
    temperature = round(weather['main']['temp'] - 273.15, 0)
    feels_like = round(weather['main']['feels_like'] - 273.15, 0)
    weather_type = weather['weather'][0]['main']

    return render_template(
        'picture.html',
        picture=picture['baseUrl'] + '=w4096-h2048',
        creationDate=creation_date,
        creationTime=creation_time,
        cameraMake=camera_make,
        cameraModel=camera_model,
        filename=picture['filename'],
        temperature=temperature,
        feels_like=feels_like,
        weather_type=weather_type
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
        flow = InstalledAppFlow.from_client_secrets_file(
            'client_secret.json', SCOPES)
        creds = flow.run_local_server(port=0)
    with open("token.pickle", "wb") as tokenFile:
        pickle.dump(creds, tokenFile)
google_photos = build('photoslibrary', 'v1', credentials=creds)

try:
    with open("config.json", "r") as f:
        print('loading config')
        config = json.load(f)
        album = config['album']
        weather_api_key = config['weather_api_key']
        weather_location = config['weather_location']
        weather_cache = {'ts': 0}
        pictures_cache = {'ts': 0}
        print(album)
except FileNotFoundError:
    print('loading config failed')
    album = get_albums()[0]['id']
    print(album)
    config = {
        "album": album
    }
    config_json = json.dumps(config)

    with open("config.json", "w") as jsonfile:
        jsonfile.write(config_json)
        print("album written to config file")
