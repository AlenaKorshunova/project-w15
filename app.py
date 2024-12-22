import requests
import pandas as pd
import json
import os
from dotenv import load_dotenv
from enum import Enum, auto
from flask import Flask, render_template, request, redirect, session
from dash import Dash, dcc, html, Input, Output, callback_context, ctx
import dash_leaflet as dl
import plotly.graph_objs as go
from dash import ALL


# Загрузка переменных окружения
load_dotenv()
api_key = "UpvLidZdnGcQAhDJN6286dwoe7SZvSwJ"

# Глобальные переменные для хранения данных о местоположении и погоде
data_loc = {}
data_weather = {}

class Response(Enum):
    GOOD = auto()
    BAD = auto()
    USER_ERROR = auto()
    SERVER_ERROR = auto()


def get_location_key_and_coord(city: str):
    """Получить ключ местоположения и координаты по названию города."""
    url = 'http://dataservice.accuweather.com/locations/v1/cities/search'
    params = {'apikey': api_key, 'q': city}
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        try:
            data = response.json()[0]
            location_key = data['Key']
            coord = (data['GeoPosition']['Latitude'], data['GeoPosition']['Longitude'])
            return location_key, coord, response.status_code
        except (IndexError, KeyError):
            return None, None, Response.BAD
    else:
        print(f'Error: {response.status_code}')
        return None, None, Response.SERVER_ERROR


def get_forecast(location_key):
    """Получить информацию о прогнозе по ключу местоположения."""
    url = f'http://dataservice.accuweather.com/forecasts/v1/daily/5day/{location_key}'
    params = {'apikey': api_key, 'details': 'true', 'metric': 'true'}
    
    response = requests.get(url, params=params)
    data = {'date': [], 'temperature': [], 'wind_speed': [], 'humidity': []}

    if response.status_code == 200:
        try:
            daily_forecasts = response.json()['DailyForecasts']
            for day_forecast in daily_forecasts:
                data['date'].append(day_forecast['Date'])
                avg_temp = (day_forecast['Temperature']['Minimum']['Value'] + day_forecast['Temperature']['Maximum']['Value']) / 2
                data['temperature'].append(avg_temp)
                data['wind_speed'].append(day_forecast['Day']['Wind']['Speed']['Value'])
                data['humidity'].append(day_forecast['Day']['RelativeHumidity']['Average'])
            return data, response.status_code
        except KeyError:
            return None, Response.BAD
    else:
        print(f'Error: {response.status_code}')
        return None, Response.SERVER_ERROR

def get_weather_data(city, days):
    """Вернуть данные о погоде в виде DataFrame."""
    df = pd.DataFrame(data_weather[city])
    return df.head(days)

def get_city_coordinates(city_name):
    """Получить координаты города и данные о погоде."""
    if city_name in data_loc:
        return data_loc[city_name][1], Response.GOOD

    location_data = get_location_key_and_coord(city_name)
    
    if not location_data or location_data[2] == Response.BAD:
        return None, Response.BAD
    elif location_data[2] != 200:
        return None, Response.SERVER_ERROR
    
    data_loc[city_name] = (location_data[0], location_data[1])
    
    forecast_data = get_forecast(location_data[0])
    
    if not forecast_data or forecast_data[1] != 200:
        data_loc.pop(city_name)
        return None, Response.SERVER_ERROR
    
    data_weather[city_name] = forecast_data[0]
    
    return location_data[1], Response.GOOD

# Инициализация Flask и Dash приложений
web_app = Flask(__name__, static_folder='static')
web_app.secret_key = os.getenv('SECRET_KEY', 'default_secret_key')

app = Dash(__name__, server=web_app, url_base_pathname='/dash/')
cities = []

