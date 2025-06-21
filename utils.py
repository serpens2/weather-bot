import asyncio
import aiohttp
from datetime import datetime, timezone
import matplotlib.pyplot as plt
import psycopg2
from functools import wraps
import os
import shutil
from dotenv import find_dotenv, load_dotenv
import logging
import traceback

load_dotenv( find_dotenv() )
log = logging.getLogger(__name__)
async def make_forecast(user_data):
    """
    Expects tuple with user data from the database.
    Requests data from (free) API, creates a graph (if not already exists)
    and stores it in 'graphs' folder with name given by user's chat_id,
    returns weather data as json.
    """
    chat_id = user_data[0]
    answer = {}
    try:
        lat, lon, offset = user_data[1:-1]
        url = f'https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&daily=sunrise,sunset&hourly=temperature_2m,precipitation_probability,wind_speed_10m,apparent_temperature&current=temperature_2m,relative_humidity_2m,is_day,rain,wind_speed_10m,cloud_cover,apparent_temperature&forecast_days=1'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                json = await response.json()
        answer["status"] = "OK"
        current_data = {
            "temp": json["current"]["temperature_2m"],
            "apparent_temp": json["current"]["apparent_temperature"],
            "hum": json["current"]["relative_humidity_2m"],
            "is_day": json["current"]["is_day"],
            "wind_speed": json["current"]["wind_speed_10m"],
            "clouds": json["current"]["cloud_cover"]
        }
        hourly_data = {
            "temp": json["hourly"]["temperature_2m"],
            "apparent_temp": json["hourly"]["apparent_temperature"],
            "precipitation_prob": json["hourly"]["precipitation_probability"],
            "wind": json["hourly"]["wind_speed_10m"]
        }
        sunrise_raw = json["daily"]["sunrise"][0].split("T")[1]
        h,m = sunrise_raw.split(":")
        sunrise = str( ( int(h) + offset ) % 24 ) + ":" + m
        sunset_raw = json["daily"]["sunset"][0].split("T")[1]
        h,m = sunset_raw.split(":")
        sunset = str( ( int(h) + offset ) % 24 ) + ":" + m
        answer["data"] = {
            "current": current_data,
            "hourly": hourly_data,
            "sunrise": sunrise,
            "sunset": sunset
        }
        if not os.path.isfile(os.path.join("graphs", f"{chat_id}.png")):
            hours = [i for i in range(0, 24)]
            plt.rcParams.update({'font.size': 14})
            plt.style.use('dark_background')
            fig, ax1 = plt.subplots(figsize=(16,9))
            graph1, = ax1.plot(hours, answer["data"]["hourly"]["temp"], 's-',
                     markersize=5, color='cyan', label = 'temperature', zorder=2)
            graph2, = ax1.plot(hours, answer["data"]["hourly"]["apparent_temp"], 'D-',
                     markersize=5, color='blueviolet', label = 'apparent temperature')
            ax2 = ax1.twinx()
            graph3, = ax2.plot(hours, answer["data"]["hourly"]["wind"], 'o-',
                     markersize=5, color='lime', label = 'wind')
            ax1.grid()
            ax1.set_xticks(hours)
            ax1.set_xlabel('Hours')
            ax1.set_xlim(-0.5,23.5)
            ax1.set_ylabel("°C")
            ax2.set_ylabel("km/h")
            ax2.spines['left'].set_position(('outward', 50))
            ax2.yaxis.set_label_position('left')
            ax2.yaxis.set_ticks_position('left')
            if max(answer["data"]["hourly"]["precipitation_prob"]) >= 5:
                ax3 = ax1.twinx()
                graph4 = ax3.bar(hours, answer["data"]["hourly"]["precipitation_prob"],
                                  color='coral', alpha=0.5,label="precipitation prob.")
                ax3.set_ylabel("%")
                ax3.spines['left'].set_position(('outward', 100))
                ax3.yaxis.set_label_position('left')
                ax3.yaxis.set_ticks_position('left')
                graphs = [graph1, graph2, graph3, graph4]
            else:
                graphs = [graph1, graph2, graph3]
            labels = [graph.get_label() for graph in graphs]
            ax1.legend(graphs, labels, loc="lower left")
            os.makedirs("graphs", exist_ok=True)
            plt.savefig(os.path.join("graphs", f"{chat_id}.png"), bbox_inches="tight")
    except Exception:
        answer["status"] = "not OK"
        answer["info"] =  traceback.format_exc()
    return answer

def clear_graphs():
    # Clears 'graphs' folder
    shutil.rmtree(os.path.abspath("graphs"), ignore_errors=True)
    os.makedirs("graphs", exist_ok=True)
    log.info("'graphs' folder cleared")

async def get_offset_by_loc(lat, lon):
    """
    Makes request to the API and returns user's timezone w.r.t. GMT
    """
    try:
        KEY_TIMEZONE = os.getenv('KEY_TIMEZONE')
        url = f"https://api.geoapify.com/v1/geocode/reverse?lat={lat}&lon={lon}&apiKey={KEY_TIMEZONE}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                json = await response.json()
                offset = int(json["features"][0]["properties"]["timezone"]["offset_STD"].split(":")[0])
                return {"status": "OK", "data": offset}
    except Exception:
        return {"status": "not OK", "info": traceback.format_exc()}

async def get_loc_by_city(city: str):
    """
    Makes request to the API and returns user's coordinates
    """
    try:
        KEY_COORDS = os.getenv('KEY_COORDS')
        url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&appid={KEY_COORDS}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                json = await response.json()
                lat, lon = float(json[0]["lat"]), float(json[0]["lon"])
                offset_response = await get_offset_by_loc(lat,lon)
        if offset_response["status"] == "not OK":
            return {"status": "not OK", "info": str(offset_response["info"])}
        offset = offset_response["data"]
        return {"status": "OK", "data": [lat, lon, offset]}
    except Exception:
        return {"status": "not OK", "info": traceback.format_exc()}

def get_my_offset() ->int:
    # System's timezone w.r.t. GMT
    return int(datetime.now().astimezone().utcoffset().total_seconds() / 3600)

DB_NAME = os.getenv('DB_NAME')
DB_USER = os.getenv('DB_USER')
DB_PASSWORD = os.getenv('DB_PASSWORD')
DB_HOST = os.getenv('DB_HOST') #change to localhost in .env when running outside docker container
def with_db(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=5432)
        cur = conn.cursor()
        try:
            result = func(cur,*args, **kwargs)
            conn.commit()
            return result
        except Exception as e:
            conn.rollback()
            log.error(str(e))
        finally:
            cur.close()
            conn.close()
    return wrapper

@with_db
def db_exists(cur, dbname: str)->bool:
    cur.execute("""
    SELECT EXISTS(SELECT * FROM information_schema.tables WHERE table_name = %s);
    """, (dbname,))
    exists = cur.fetchall()[0][0]
    return exists

@with_db
def add_user(cur, chat_id, coords, notify_time):
    lat, lon, offset = coords
    query = """
    INSERT INTO weatherbot (chat_id, lat, lon, tz_offset, notify)
    VALUES (%s, %s, %s, %s, %s);
    """
    cur.execute(query, (chat_id, lat, lon, offset, notify_time))

@with_db
def delete_user(cur, chat_id: str):
    query="""
    DELETE FROM weatherbot WHERE chat_id = %s;
    """
    cur.execute(query, (chat_id,))
    log.info("User deleted")

@with_db
def get_user(cur, chat_id: str):
    query="""
    SELECT * FROM weatherbot WHERE chat_id = %s
    """
    cur.execute(query, (chat_id,))
    return cur.fetchone()