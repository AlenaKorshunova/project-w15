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
