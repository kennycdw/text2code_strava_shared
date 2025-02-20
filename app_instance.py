""" 
Have to be separate to avoid circular imports.
"""
from contextlib import asynccontextmanager
from telegram.ext import Application
from fastapi import FastAPI
from utils_db import Database
from loguru import logger
from pyngrok import ngrok
import os
import pytz
import nest_asyncio
from dotenv import load_dotenv
from utils_datawrapper import DataWrapper

# Load environment variables
load_dotenv()

# Environment settings
environment = os.getenv('ENVIRONMENT')
port = int(os.getenv('PORT'))

# Gemini Credentials
gemini_api_key = os.getenv('GEMINI_API_KEY')
gemini_model = os.getenv('GEMINI_MODEL')

# Strava Credentials
strava_client_id = int(os.getenv('STRAVA_CLIENT_ID'))
strava_client_secret = os.getenv('STRAVA_CLIENT_SECRET')

# Telegram Credentials
telegram_token = os.getenv('TELEGRAM_TOKEN')
logger_telegram_token = os.getenv('LOGGER_TELEGRAM_TOKEN')
kenny_chat_id = os.getenv('KENNY_CHAT_ID')

# PostgreSQL Credentials
DATABASE_URL = os.getenv('DATABASE_URL')

# DASH Credentials
dash_api = os.getenv('DASH_API')
dash_link_auth = os.getenv('DASH_LINK_AUTH')
dash_link_charts = os.getenv('DASH_LINK_CHARTS')

# ngrok
ngrok_token = os.getenv('NGROK_TOKEN')

# Directories
data_directory = os.getenv('DATA_DIRECTORY', 'data/')

sg_timezone = pytz.timezone('Asia/Singapore')

dw = DataWrapper(api_token=dash_api)

weekday_mapping_dic = {0: 'Monday', 1: 'Tuesday', 2: 'Wednesday', 3: 'Thursday', 4: 'Friday', 5: 'Saturday', 6: 'Sunday'}
month_mapping_dic = {1:'Jan', 2:'Feb', 3:'Mar', 4:'Apr', 5:'May', 6:'Jun', 
               7:'Jul', 8:'Aug', 9:'Sep', 10:'Oct', 11:'Nov', 12:'Dec'}

ngrok.set_auth_token(ngrok_token)
nest_asyncio.apply()
logger.add("logs/strava_bot.log", rotation="500 MB", compression="zip", retention= '100 days')

bot_app = Application.builder().token(telegram_token).build()
logger_bot_app = Application.builder().token(logger_telegram_token).build()
db = Database(DATABASE_URL)


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        if environment == "local":
            if "RUN_MAIN" not in os.environ:
                weblink = ngrok.connect(port).public_url
        else:
            weblink = "https://stravav2.kennyvectors.com"
        bot_app.bot_data['weblink'] = weblink
        logger.info(f"Weblink: {weblink}")
        logger.info(f"Connecting to database {db}")

        await db.connect()
        await bot_app.bot.setWebhook(f"{weblink}/incomingmsg")

        async with bot_app:
            await bot_app.start()
            yield # when application is running
            await bot_app.stop() # cleanup when shutting down
    except Exception as e:
        logger.exception(f"Startup error: {e}")
        raise
    finally:
        await db.disconnect()
        logger.info("All connections closed")