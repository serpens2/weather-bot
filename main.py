# change DB_HOST to 'localhost' in .env when running outside of Docker
from utils import (get_loc_by_city, get_offset_by_loc, add_user,
                   delete_user, get_user, make_forecast, clear_graphs,
                   get_my_offset, with_db)
from init_db import init_db
from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.enums.parse_mode import ParseMode
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove, FSInputFile
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
import asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
import os
import sys
from dotenv import find_dotenv, load_dotenv
import logging
load_dotenv( find_dotenv() )

scheduler = AsyncIOScheduler()

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('KEY_BOT')
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

my_offset = get_my_offset()

# Text and keyboard used to start registration process.
# Defined globally, as they are referred to by multiple functions.
kb_loc_options = InlineKeyboardBuilder()
kb_loc_options.button(text='Send location🌐', callback_data='send_loc')
kb_loc_options.button(text='Type your city🏘️', callback_data='type_city')
kb_loc_options.button(text='Send coords manually✏️', callback_data = 'send_manually')
kb_loc_options.adjust(1)
start_text="""
To make forecasts, I need to know your location.
You can either send it directly (doesn't work on PC), or by typing a name of the city you're currently in.

Alternatively, you can send your coordinates manually via a helper site.
"""

class UserDataTypeCity(StatesGroup):
    city = State()

class UserPrefs(StatesGroup):
    coords = State()
    notify_time = State()

async def get_forecast(chat_id: str):
    # Generates forecast text
    data = get_user(chat_id)
    if data is None:
        response = {
            "status": "not OK",
            "info": "user_not_found"
        }
        return response
    else:
        forecast = await make_forecast(data)
        if forecast["status"] != "OK":
            response = {
                "status": "not OK",
                "info": forecast["info"]
            }
            return response
        else:
            forecast = forecast["data"]
            precipitation_prob = max(forecast["hourly"]["precipitation_prob"])
            forecast_text = f"""
temperature🌡️: {forecast["current"]["temp"]} °C 
apparent temperature🌡️🤔: {forecast["current"]["apparent_temp"]} °C
humidity💧: {forecast["current"]["hum"]} %
wind speed🌪️: {forecast["current"]["wind_speed"]} km/h
clouds⛅: {forecast["current"]["clouds"]} % 
precipitation🌧️🌨️ probability: {precipitation_prob} %"""
            if forecast["current"]["is_day"] == 1:
                forecast_text += f"""\nday🌞"""
            else:
                forecast_text += f"""\nnight🌚"""
            forecast_text += f"""
sunrise🕑: {forecast["sunrise"]}
sunset🕙: {forecast["sunset"]}     
                """
            response = {
                "status": "OK",
                "data": forecast_text
            }
            return response

@dp.message(Command('forecast'))
async def forecast_command(message: Message):
    chat_id = str(message.chat.id)
    response = await get_forecast(chat_id)
    if response["status"] != "OK":
        if response["info"] == "user_not_found":
            await message.answer("I don't see you in my database🔍 \n Type /start to register")
        else:
            await message.answer("Something went wrong☹️️")
            log.error(response["info"])
    else:
        await message.reply_photo(
            photo= FSInputFile(path=os.path.abspath(os.path.join("graphs", f"{chat_id}.png"))),
            caption= response["data"]
        )

async def notify_user(chat_id: str):
    """
    This function is used to assign a daily forecast task via apscheduler
    """
    response = await get_forecast(chat_id)
    if response["status"] != "OK":
        await bot.send_message(chat_id=int(chat_id), text="Couldn't make a daily forecast☹️️")
        log.error(response["info"])
    else:
        await bot.send_photo(chat_id=int(chat_id),
                             photo=FSInputFile(path=os.path.abspath(os.path.join("graphs", f"{chat_id}.png"))),
                             caption=response["data"]
                             )

@dp.message(Command('deleteme'))
async def delete_command(message: Message):
    chat_id = str(message.chat.id)
    data = get_user(chat_id)
    if data is None:
        await message.answer("I don't see you in my database🔍 \nType /start to register")
    else:
        delete_user(chat_id)
        if data[-1]:
            scheduler.remove_job(chat_id)
        await message.answer("Deleted🗑")

@dp.message(Command('updateme'))
async def update_command(message: Message):
    chat_id = str(message.chat.id)
    data = get_user(chat_id)
    if data is None:
        await message.answer("I don't see you in my database🔍 \nType /start to register")
    else:
        delete_user(chat_id)
        if data[-1]:
            scheduler.remove_job(chat_id)
        await message.answer(text=start_text, reply_markup=kb_loc_options.as_markup())

@dp.message(Command('changetime'))
async def change_time_command(message: Message, state: FSMContext):
    chat_id = str(message.chat.id)
    data = get_user(chat_id)
    if data is None:
        await state.clear()
        await message.answer("I don't see you in my database🔍 \n Type /start to register")
    else:
        delete_user(chat_id)
        scheduler.remove_job(chat_id)
        await state.set_state(UserPrefs.coords)
        await state.update_data(coords=list(data[1:-1]))
        await get_notify_time(message, state)

@dp.message(CommandStart())
async def start_command(message: Message):
    chat_id = str(message.chat.id)
    data = get_user(chat_id)
    if data is None:
        await message.answer(text=start_text, reply_markup=kb_loc_options.as_markup())
    else:
        await message.answer(text="You're already registered.\n Type \deleteme to start anew.")

@dp.callback_query(F.data == 'send_loc')
async def handle_send_loc_1(cb: CallbackQuery):
    send_loc_kb = ReplyKeyboardBuilder()
    send_loc_kb.button(text="Send", request_location=True)
    await cb.message.answer(text="Turn on GPS and press the button",
                            reply_markup=send_loc_kb.as_markup(resize_keyboard=True))
@dp.message(F.location)
async def handle_send_loc_2(message: Message, state: FSMContext):
    try:
        await state.set_state(UserPrefs.coords)
        lat = message.location.latitude
        lon = message.location.longitude
        assert not (lat is None) and not (lon is None)
        offset = await get_offset_by_loc(lat, lon)
        if offset["status"] != "OK":
            await message.answer("Couldn't receive coordinates :c")
            await handle_failure(message, state)
            log.error(offset["info"])
        else:
            await state.update_data(coords = [lat, lon, offset["data"]])
            await get_notify_time(message, state)
    except Exception as e:
        await message.answer("Couldn't receive coordinates :c")
        await handle_failure(message, state)
        log.info(str(e))

@dp.callback_query(F.data == 'type_city')
async def handle_type_city_1(cb: CallbackQuery, state: FSMContext):
    await cb.message.answer("Type in the city's name")
    await state.set_state(UserDataTypeCity.city)

@dp.message(UserDataTypeCity.city, F.text)
async def handle_type_city_2(message: Message, state: FSMContext):
    response = await get_loc_by_city(message.text)
    if response["status"] == "OK":
        await state.set_state(UserPrefs.coords)
        await state.update_data(coords = response["data"])
        await get_notify_time(message, state)
    else:
        await message.answer("I don't know this city :c")
        await handle_failure(message, state)
        log.info( response["info"] )

@dp.callback_query(F.data == "send_manually")
async def handle_send_manually_1(cb: CallbackQuery, state: FSMContext):
    answer = """
    Send your latitude and longitude in one line, separated by coma (e.g. 51.320, -13.21).
    You can use <a href='https://www.latlong.net/'>this</a> helper site to find yourself on the map:
    """
    await state.set_state(UserPrefs.coords)
    await cb.message.answer(answer, parse_mode=ParseMode.HTML)

@dp.message(UserPrefs.coords, F.text)
async def handle_send_manually_2(message: Message, state: FSMContext):
    try:
        lat, lon = [ float(num) for num in message.text.split(",")]
        offset_response = await get_offset_by_loc(lat,lon)
        if offset_response["status"] == "OK":
            await state.update_data(coords = [lat, lon, offset_response["data"]])
            await get_notify_time(message, state)
        else:
            await message.answer("Something went wrong☹️")
            log.error(offset_response["info"])
    except Exception as e:
        await message.answer("Invalid coordinates :c")
        await handle_failure(message, state)
        log.info(str(e))

async def handle_failure(message: Message, state: FSMContext):
    await state.clear()
    await message.answer(text="Let's try again", reply_markup=kb_loc_options.as_markup())

async def get_notify_time(message: Message, state: FSMContext):
    await message.answer(text="Got it!", reply_markup=ReplyKeyboardRemove())
    await state.set_state(UserPrefs.notify_time)
    kb_notify_time = InlineKeyboardBuilder()
    kb_notify_time.button(text="Yes✅", callback_data="yes_notify")
    kb_notify_time.button(text="No❌", callback_data="no_notify")
    kb_notify_time.adjust(1)
    await message.answer(text="Would you like to receive daily forecasts?",
                         reply_markup=kb_notify_time.as_markup())

@dp.callback_query(F.data == "no_notify")
async def handle_no_notify(cb: CallbackQuery, state: FSMContext):
    await state.update_data(notify_time = None)
    await complete_registration(cb.message, state)

@dp.callback_query(F.data == "yes_notify")
async def handle_yes_notify_1(cb: CallbackQuery):
    await cb.message.answer("At what time?⏰")

@dp.message(UserPrefs.notify_time)
async def handle_yes_notify_2(message: Message, state: FSMContext):
    try:
        h,m = message.text.split(":")
        h,m = int(h), int(m)
        assert 0 <= h <= 23
        assert 0 <= m <= 59
        await state.update_data(notify_time = message.text)
        await complete_registration(message, state)
    except Exception as e:
        log.info(str(e))
        await message.answer("Invalid time☹️ \n Try again. For example, 14:00")

async def complete_registration(message: Message, state: FSMContext):
    data = await state.get_data()
    answer_text="""
Registration completed🫡
You can use the following commands:
/forecast - make a forecast
/updateme - update your info
/changetime - change the time of daily forecast
/deleteme - delete yourself from database
/start - start registration process
    """
    await message.answer(answer_text)
    await state.clear()
    chat_id = str(message.chat.id)
    if data["notify_time"]:
        h,m = data["notify_time"].split(":")
        h,m = int(h), int(m)
        offset = data["coords"][2]
        h = ( h - offset + my_offset ) % 24
        scheduler.add_job(notify_user, 'cron', hour=h, minute=m, id=chat_id, args=[chat_id])
    add_user(chat_id, **data)
    log.info("User inserted")

@dp.message()
async def reply_to_nonsense(message: Message):
    await message.answer("🤔")

@with_db
def init_notifications(cur):
    """
    This function is used to add daily forecast tasks
    for all the users in the database via apscheduler
    """
    query="""
    SELECT chat_id, tz_offset, notify FROM weatherbot
    WHERE notify IS NOT NULL;
    """
    cur.execute(query)
    users = cur.fetchall()
    for user in users:
        h,m = user[2].split(":")
        h = int(h)
        m = int(m)
        h = (h - int(user[1]) + my_offset) % 24
        scheduler.add_job(notify_user, 'cron', hour=h, minute=m, id=user[0], args=[user[0]])

async def main():
    init_db()
    # clears all graphs at midnight w.r.t. GMT
    scheduler.add_job(clear_graphs, 'cron', hour=my_offset, minute=0)
    init_notifications()
    scheduler.start()
    await dp.start_polling(bot)

if __name__ == '__main__':
    if sys.platform.startswith('win'):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())