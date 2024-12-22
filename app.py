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

@web_app.route('/', methods=['GET', 'POST'])
def index():
    global cities
    if request.method == 'POST':
        start_point = request.form['start_point']
        end_point = request.form['end_point']
        intermediate_cities = request.form.getlist('intermediate_city')

        cities = [start_point] + intermediate_cities + [end_point]
        
        for city in cities:
            res_status = get_city_coordinates(city)[1]
            if res_status == Response.SERVER_ERROR:
                return render_template('message.html', message='Упс, проблемы с сервером')  
            elif res_status == Response.BAD:
                return render_template('message.html', message='Упс, перепроверьте написание городов')    
        
        session['selected_city'] = start_point   
        return redirect('/dash/')
    
    return render_template('main.html')

app.layout = html.Div([
    html.H1("Интерактивные данные о погоде"),
    
    dl.Map(center=[55.751244, 37.618423], zoom=4, children=[
        dl.TileLayer(),
        dl.LayerGroup(id="markers-layer"),
        dl.Polyline(id="route-line", positions=[])
    ], id="map", style={'width': '100%', 'height': '70vh'}),

    dcc.Dropdown(
        id='metric-dropdown',
        options=[
            {'label': 'Температура', 'value': 'temperature'},
            {'label': 'Скорость ветра', 'value': 'wind_speed'},
            {'label': 'Влажность', 'value': 'humidity'}
        ],
        value='temperature',
        clearable=False,
        style={'width': '50%'}
    ),
    
    dcc.Dropdown(
        id='days-dropdown',
        options=[
            {'label': '3 дня', 'value': 3},
            {'label': '5 дней', 'value': 5}
        ],
        value=3,
        clearable=False,
        style={'width': '50%'}
    ),

    html.Div(id='weather-graph-container')
])

@app.callback(
    [Output("markers-layer", "children"), Output("route-line", "positions")],
    Input('map', 'id')
)
def add_route_and_markers(_):
    city_markers = []
    route_positions = []
    
    for city in cities:
        coords_response = get_city_coordinates(city)
        
        coords = coords_response[0]
        
        if coords:
            route_positions.append(coords)
            marker_id = {'type': 'marker', 'index': city}
            marker = dl.Marker(position=coords, children=[
                dl.Tooltip(city),
                dl.Popup([html.H3(city), html.P("Нажмите для данных")])
            ], id=marker_id)
            city_markers.append(marker)
    
    return city_markers, route_positions

@app.callback(
    Output("weather-graph-container", "children"),
    [Input("metric-dropdown", "value"), Input("days-dropdown", "value")],
    Input({'type': 'marker', 'index': ALL}, 'n_clicks')
)
def update_graph(selected_metric, days, _):
    triggered_id = callback_context.triggered[0]['value']
    
    # Получаем имя города из сессии
    city_name = session.get('selected_city')

    if ctx.triggered_id and ctx.triggered_id != "metric-dropdown" and ctx.triggered_id != "days-dropdown":
        # Извлекаем имя города из идентификатора маркера
        try:
            city_name_json_str = callback_context.triggered[0]['prop_id'].split(".")[0]
            city_name_dict = json.loads(city_name_json_str)
            city_name = city_name_dict["index"]
            session['selected_city'] = city_name
        except (json.JSONDecodeError, KeyError) as e:
            print(f"Ошибка при извлечении имени города: {e}")
            return html.Div("Ошибка при извлечении данных о городе.")

    print(f"Triggered: {triggered_id}, City Name: {city_name}")

    if city_name:
        weather_data_df = get_weather_data(city_name, days=days)
        
        if not weather_data_df.empty:
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=weather_data_df['date'], y=weather_data_df[selected_metric], mode='lines', name=selected_metric))
            
            fig.update_layout(
                title=f'{selected_metric.capitalize()} в городе {city_name} за {days} дней',
                xaxis_title='Дата',
                yaxis_title='Значение',
                template='plotly_dark'
            )
            
            return dcc.Graph(figure=fig)

    return html.Div("Выберите город для отображения графика")

if __name__ == '__main__':
    web_app.run(host='0.0.0.0', port=5000, debug=True)
