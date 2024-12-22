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
