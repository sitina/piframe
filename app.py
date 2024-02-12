"""
The application serves random photo from google photos album
"""
import os
import pickle
import json
import random
import requests
import time

from flask import Flask
from flask import render_template
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from datetime import datetime
from dateutil import parser
import matplotlib.pyplot as plt
import io
import random
from flask import Response
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.figure import Figure

album = ''
app = Flask(__name__, static_folder='static',)


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
        if weather_api_key:
            weather_url = f"http://api.openweathermap.org/data/2.5/weather?appid={weather_api_key}&q={weather_location}"
            weather_data = requests.get(weather_url).json()
            weather_cache['ts'] = ts
            weather_cache['data'] = weather_data
            return weather_data
    else:
        # print('using weather cache')
        return weather_cache['data']


def get_forecast():
    print('getting forecast')
    forecast_file = 'forecast.json'
    lon = 14.4936
    lat = 50.1267
    ts = time.time()
    if ts - weather_cache['forecast_ts'] > 300:
        if os.path.isfile(forecast_file):
            with open(forecast_file) as f:
                print('fetching weather data from file')
                return json.load(f)
        elif weather_api_key:
            print('getting forecast via api')
            weather_url = f"http://api.openweathermap.org/data/2.5/forecast?appid={weather_api_key}&lat={lat}&lon={lon}"
            weather_data = requests.get(weather_url).json()
            weather_cache['forecast_ts'] = ts
            weather_cache['forecast'] = weather_data
            return weather_data
    else:
        print('using weather cache')
        return weather_cache['forecast']


@app.route("/")
def home():
    return get_fullscreen()


def to_celsius(original):
    return round(original - 273.15, 1)


def process_forecast(forecast_data):
    # print(forecast_data)
    result = []
    for item in forecast_data['list']:
        temp = to_celsius(item['main']['temp'])
        feels_like = to_celsius(item['main']['feels_like'])
        humidity = item['main']['humidity']
        weather = item['weather'][0]['main']
        dt = item['dt_txt']
        tt = item['dt_txt'][11:]
        icon = '/static/images/' + item['weather'][0]['icon'] + '@2x.gif'
        result.append(
            {
                'dt': dt,
                'temp': temp,
                'feels_like': feels_like,
                'weather': weather,
                'humidity': humidity,
                'icon': icon,
                'time': tt[:2],
            }
        )
    return result


@app.route('/weather/forecast.png')
def plot_png():
    ts = time.time()
    if ts - weather_cache['forecast_ts'] > 300 or not('forecast_chart' in weather_cache):
        fig = create_figure()
        output = io.BytesIO()
        FigureCanvas(fig).print_png(output)
        weather_cache['forecast_chart'] = output.getvalue()

    return Response(weather_cache['forecast_chart'], mimetype='image/png')


def create_figure():
    fig = Figure()
    fig.patch.set_alpha(0.3)
    axis = fig.add_subplot(1, 1, 1, facecolor="none")

    forecast_data = get_forecast()
    forecast = process_forecast(forecast_data)

    # 2024-02-10 00:00:00
    # -> 10 00 (only date + hours)
    xs = [f['dt'][:13][8:] for f in forecast]
    # -> 00 (only hours)
    xticks = [f['dt'][:13][11:] for f in forecast]
    ys1 = [f['temp'] for f in forecast]
    ys2 = [f['feels_like'] for f in forecast]

    axis.plot(xs, ys1, color='red', label='forecast')
    axis.plot(xs, ys2, color='blue', label='feels like')
    axis.legend(loc='best')
    axis.set_xticks(xs)
    axis.set_xticklabels(xticks)
    axis.tick_params(axis='x', rotation=90)

    # make line for every new day
    for val in xs:
        if val[3:] == '00':
            axis.axvline(x=val, color='black')

    return fig


@app.route("/weather")
def weather_view():
    weather = get_weather()
    forecast_data = get_forecast()
    forecast = process_forecast(forecast_data)
    # print(forecast)
    temperature = to_celsius(weather['main']['temp'])
    feels_like = to_celsius(weather['main']['feels_like'])
    weather_type = weather['weather'][0]['main']

    return render_template(
        'weather.html',
        temperature=temperature,
        feels_like=feels_like,
        weather_type=weather_type,
        forecast=forecast[slice(6)]
    )


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
    forecast_data = get_forecast()
    forecast = process_forecast(forecast_data)
    # print(forecast)
    temperature = to_celsius(weather['main']['temp'])
    feels_like = to_celsius(weather['main']['feels_like'])
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
        weather_type=weather_type,
        forecast=forecast[slice(6)],
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
    if creds and creds.expired and creds.refresh_token:
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
        weather_cache = {'ts': 0, 'forecast_ts': 0}
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
