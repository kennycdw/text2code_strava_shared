from fastapi import APIRouter, Request, Response
from telegram import Update
from http import HTTPStatus
from app_instance import bot_app
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from telegram.constants import ParseMode
from utils_strava import strava_onboarding

telegram_router = APIRouter()


@telegram_router.post("/incomingmsg")
async def process_update(request: Request):
    req = await request.json()
    update = Update.de_json(req, bot_app.bot)
    await bot_app.process_update(update)
    return Response(status_code=HTTPStatus.OK)

async def start(update, context):
    weblink = bot_app.bot_data['weblink']
    await update.message.reply_text(strava_onboarding(update.message.chat_id, weblink), parse_mode=ParseMode.MARKDOWN)

async def respond(update, context):
    user = update.message.from_user
    chat_id = update.message.chat_id
    weblink = bot_app.bot_data['weblink']
    response_text = f"Hello {user.first_name}! Your chat ID is: {chat_id}"
    await update.message.reply_text(strava_onboarding(update.message.chat_id, weblink), parse_mode=ParseMode.MARKDOWN)

async def analytics(update, context):
    await update.message.reply_text("Analytics function is not available yet, stay tuned!")


async def delete(update, context):
    await update.message.reply_text("Functionality to delete your user data is not available yet, "
                                    "contact Kenny for more information!")

async def text2sql(update, context):
    #TODO: make sure that db connected only has read access.
    await update.message.reply_text("Functionality to convert text to SQL is not available yet, "
                                    "contact Kenny for more information!")

async def onboarding(update, context):
    #TODO: need to check if user has already onboarded
    #TODO: need to check if user has already connected to Strava
    weblink = bot_app.bot_data['weblink']
    await update.message.reply_text(strava_onboarding(update.message.chat_id, weblink), parse_mode=ParseMode.MARKDOWN)


bot_app.add_handler(CommandHandler("start" , start))
bot_app.add_handler(CommandHandler("analytics" , analytics))
bot_app.add_handler(CommandHandler("onboarding" , onboarding))
bot_app.add_handler(CommandHandler("delete" , delete))
bot_app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, respond))
bot_app.add_handler(MessageHandler(filters.COMMAND, respond))