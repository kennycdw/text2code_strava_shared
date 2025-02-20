from fastapi import APIRouter, Query, HTTPException, Request, BackgroundTasks
from app_instance import bot_app, logger_bot_app
from utils_db import Database
from app_instance import (kenny_chat_id, strava_client_id, strava_client_secret, db, sg_timezone)
from utils_strava import (retrieve_refresh_token, delete_activity_from_strava, create_update_data_from_strava, retrieve_full_data_from_strava,
                         baseline_analytics, datawrapper_initiate_charts)
from datetime import datetime, timezone
from fastapi.responses import RedirectResponse, JSONResponse, Response, HTMLResponse
from http import HTTPStatus
from typing import Optional
import requests
from loguru import logger
from pydantic import BaseModel
import json
import os
from utils import get_nested_value, custom_hash
from chains.workflow_text2sql import app
import asyncio
from langchain_core.messages import HumanMessage
from uuid import uuid4


strava_router = APIRouter()


@strava_router.get("/strava-auth/{chat_string_id}")
async def strava_auth(chat_string_id: str, code: Optional[str] = None, error: Optional[str] = None, background_tasks: BackgroundTasks = BackgroundTasks()):
    """
    Strava oauth2 endpoint
    """
    if error == 'access_denied':
        await db.upsert(table = 'main.botdata_v2',
                        data = {'telegram_id': chat_string_id, 'strava_approval': False,'last_active_at': datetime.now(timezone.utc).astimezone(sg_timezone)},
                        constraint_columns = ['telegram_id'])
        await logger_bot_app.bot.send_message(chat_id=kenny_chat_id, text=f"Strava account has been denied access to telegram {chat_string_id}")
        await bot_app.bot.send_message(chat_id=int(chat_string_id), text=f"You have denied access to my bot.")
        return JSONResponse(status_code=403, content={"status": "error", "message": "Strava access was denied", "error_type": "permission_denied"})
    
    credentials_dic = retrieve_refresh_token(code)
    athlete = credentials_dic['athlete']
    await db.upsert(table='main.botdata_v2', data={'telegram_id': chat_string_id,'strava_id': str(athlete['id']),'strava_firstname': athlete['firstname'],
                                                    'strava_lastname': athlete['lastname'],'refresh_token': credentials_dic['refresh_token'],   
                                                    'strava_approval': True, 'last_active_at': datetime.now(timezone.utc).astimezone(sg_timezone)},
                                                    constraint_columns=['telegram_id'])

    hashed_strava_id = custom_hash(str(athlete['id']))
    weblink = bot_app.bot_data['weblink']
    background_tasks.add_task(retrieve_full_data_from_strava, credentials_dic['refresh_token'])
    background_tasks.add_task(baseline_analytics, athlete['id'], upload_to_file = True)
    background_tasks.add_task(datawrapper_initiate_charts, weblink, athlete['id'])
    background_tasks.add_task(bot_app.bot.send_message, chat_id=int(chat_string_id), text=f"Thank you for connecting! Your dashboard is ready at https://kennyvectors.com/running-strava-v2-dashboard?analytics={hashed_strava_id}")

    if credentials_dic['refresh_token'] != -1:
        await logger_bot_app.bot.send_message(chat_id=kenny_chat_id, text=f"Strava account has been connected to telegram {chat_string_id}")
        #TODO: share the user journey architecture diagram (picture)
        await bot_app.bot.send_message(chat_id=int(chat_string_id), text=f"Your account has been connected, wait a couple of minutes for me to load your dashboards and analytics")
        return RedirectResponse(url="https://kennyvectors.com/redirect/", status_code=303)
    else:
        return Response(status_code=HTTPStatus.BAD_REQUEST)
    
class StravaWebhookSetupRequest(BaseModel):
    client_id: str     # Required
    client_secret: str # Required
    push_subscription_id: Optional[str] = None

@strava_router.post('/set-strava-webhook')
def strava_set_webhook(request: StravaWebhookSetupRequest):
    """
    One time setup endpoint for strava webhook subscription - async not needed.
    """
    weblink = bot_app.bot_data['weblink']
    strava_webhook_url = "https://www.strava.com/api/v3/push_subscriptions"
    r = requests.post(url = strava_webhook_url, 
                      data = {'client_id': request.client_id,
                              "client_secret": request.client_secret,
                              'callback_url': f'{weblink}/strava-response',
                              'verify_token': 'STRAVA'})
    return {"status": "success", "response": r.json()}

@strava_router.post('/delete-strava-webhook')
def strava_delete_webhook(request: StravaWebhookSetupRequest):
    """
    One time setup endpoint for deleting strava webhook subscription - async not needed.
    To get the id, retrieve from strava_webhook_url in strava_config.py
    """
    strava_webhook_url = f"https://www.strava.com/api/v3/push_subscriptions/{request.push_subscription_id}"
    logger.info(f"Deleting Strava webhook: {strava_webhook_url}")
    r = requests.delete(url = strava_webhook_url, data = {'client_id': request.client_id, "client_secret": request.client_secret})
    return r.text

@strava_router.get('/strava-response')
async def strava_webhook_verify(hub_mode: str = Query(None, alias="hub.mode"),
                                hub_verify_token: str = Query(None, alias="hub.verify_token"),
                                hub_challenge: str = Query(None, alias="hub.challenge")
                                ):
    """Handle Strava webhook verification"""
    logger.info(f"Strava webhook verification attempt: {hub_mode} {hub_verify_token} {hub_challenge}")
    if hub_mode == "subscribe" and hub_verify_token == "STRAVA":
        logger.info("Strava webhook verified successfully")
        return {"hub.challenge": hub_challenge}
    else:
        logger.warning("Invalid webhook verification attempt")
        raise HTTPException(status_code=403, detail="Invalid verification token")

@strava_router.post('/strava-response')
async def strava_webhook_event(request: Request, background_tasks: BackgroundTasks):
    """
    Handle incoming Strava webhook events
    webhook_json = {"aspect_type": "create", "event_time": 1734361680, "object_id": 13127941701, "object_type": "activity", "owner_id": 28923822, "subscription_id": 143570, "updates": {}}
    webhook_json = {'aspect_type': 'create', 'event_time': 1735816641, 'object_id': 13244961091, 'object_type': 'activity', 'owner_id': 29260159, 'subscription_id': 270785, 'updates': {}}
    """
    try:
        webhook_json = await request.json()
        logger.info(f"Received Strava webhook event: {webhook_json}")
        await logger_bot_app.bot.send_message(chat_id=kenny_chat_id, text=webhook_json)

        if webhook_json['aspect_type'] in ('create', 'update'):
            status = await create_update_data_from_strava(webhook_json)
            if status:
                background_tasks.add_task(baseline_analytics, webhook_json['owner_id'], upload_to_file = True)
        elif webhook_json['aspect_type'] == 'delete':
            await delete_activity_from_strava(webhook_json)
            background_tasks.add_task(baseline_analytics, webhook_json['owner_id'], upload_to_file = True)
        else:
            logger.warning(f"Unknown aspect type: {webhook_json['aspect_type']}")
        return {"status": "success"}
    except Exception as e:
        logger.exception("Error processing webhook event")
        raise HTTPException(status_code=500, detail="Failed to process webhook event")

@strava_router.post('/reload-full-data')
async def strava_reload_full_data(request: Request, background_tasks: BackgroundTasks):
    """
    Reload full data from Strava
    
    json_output = asyncio.run(db.fetch_one(f"SELECT refresh_token, strava_id FROM main.botdata_v2 WHERE telegram_id = $1", str(telegram_id)))

    #TODO: this guy should not be asyncio but multi-threaded (use def instead of async def?), check the bottleneck of the background tasks.
    #https://stackoverflow.com/questions/67599119/fastapi-asynchronous-background-tasks-blocks-other-requests
    #from fastapi.concurrency import run_in_threadpool (option 3)
    #Note - this makes sense because our computation is not that computational heavy actually, main bottleneck is mainly the database.
    """
    try:
        json_output  = await request.json()
        weblink = bot_app.bot_data['weblink']
        telegram_id = json_output['telegram_id']
        logger.info(f"Received request to reload full data for {telegram_id} [{json_output}]")
        json_output = await db.fetch_one(f"SELECT refresh_token, strava_id FROM main.botdata_v2 WHERE telegram_id = $1", str(telegram_id))
        if json_output is None:
            logger.info(f"telegram_id {telegram_id} not found in DB")
            return {"status": "failed", "message": f"telegram_id {telegram_id} not found in DB"}    
        special_refresh_token = json_output['refresh_token']
        strava_id = json_output['strava_id']
        background_tasks.add_task(retrieve_full_data_from_strava, special_refresh_token)
        background_tasks.add_task(baseline_analytics, strava_id, upload_to_file = True)
        background_tasks.add_task(datawrapper_initiate_charts, weblink, strava_id)
        background_tasks.add_task(logger_bot_app.bot.send_message, chat_id=int(kenny_chat_id), text=f"Strava data for {telegram_id} has been reloaded (reload-full-data)")

        return {"status": "processing", "message": "Data reload started in background"}
    except Exception as e:
        logger.exception(f"Error processing Strava reload request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )

@strava_router.get('/stravajson')
async def strava_json(id: str):
    """
    Get Strava JSON data for a given Strava ID
    """
    try:
        file_path = f"data/activity_data/{id}.json"
        if not os.path.exists(file_path):
            return {"status": "failed", "message": f"File {file_path} does not exist"}

         # Read and return JSON data
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                return JSONResponse(content=data)
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in file: {file_path}")
            raise HTTPException(
                status_code=500,
                detail="Error reading activity data"
            )
    except Exception as e:
        logger.exception(f"Error processing Strava JSON request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )

@strava_router.get("/stravajson/{path}")
async def get_strava_data(id: str, path: str):
    """
    Get Strava analytics data. Use hyphen-separated paths to access nested values.
    
    Examples:
    - /stravajson/summary-total_activities  >> dic['summary']['total_activities']
    - /stravajson/latest_activity-distance  >> dic['latest_activity']['distance']
    - /stravajson/streaks-current_streak  >> dic['streaks']['current_streak']
    """
    try:
        file_path = f"data/activity_data/{id}.json"
        if not os.path.exists(file_path):
            return {"status": "failed", "message": f"File {file_path} does not exist"}

        try:
            with open(file_path, 'r') as f:
                data = json.load(f)

                nested_data = get_nested_value(data, path)
                if nested_data is None:
                    raise HTTPException(status_code=404, detail=f"Path '{path}' not found")
                return HTMLResponse(content=nested_data)

        except json.JSONDecodeError:
            logger.error(f"Invalid JSON in file: {file_path}")
            raise HTTPException(
                status_code=500,
                detail="Error reading activity data"
            )


    except Exception as e:
        logger.exception(f"Error processing Strava JSON request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )

@strava_router.get('/strava-charts')
async def strava_charts(id: str):
    """
    Get Strava charts for a given Strava ID

    import asyncio
    asyncio.run(db.connect())
    id = "4ik41YnN0F"
    json_output = asyncio.run(db.fetch_all(f"SELECT strava_id, chart_identifier_id, chart_id, chart_title, web_link, embed_code_responsive, embed_code_web_component FROM main.strava_charts WHERE strava_hashed_id = $1", str(id)))
    """
    try:
        json_output = await db.fetch_all(f"SELECT strava_id, chart_identifier_id, chart_id, chart_title, web_link, embed_code_responsive, embed_code_web_component FROM main.strava_charts WHERE strava_hashed_id = $1", str(id))
        dic = {}
        for row in json_output: 
            dic[row['chart_identifier_id']] = {'embed_code_responsive': row['embed_code_responsive'], 'embed_code_web_component': row['embed_code_web_component']}
        return JSONResponse(content=dic)
    except Exception as e:
        logger.exception(f"Error processing Strava charts request: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error"
        )
    
@strava_router.post('/text2sql')
async def text2sql(request: Request):
    """
    Text2SQL endpoint

    final_state = asyncio.run(app.ainvoke({"messages": [HumanMessage(content="what is the weather in sf")]}, config = thread))
    final_state.get('response_agent_result', "")
    """
    try:
        json_output  = await request.json()
        # TODO: make sure we capture the strava_id
        #weblink = bot_app.bot_data['weblink']
        hashed_strava_id = json_output.get('analytics', None)
        if hashed_strava_id is None:
            return {"status": "failed", "response": "No hashed_strava_id found in the request",
                    "sql_query": "No hashed_strava_id found in the request",
                    "question_type": "No hashed_strava_id found in the request",
                    "execute_sql_result": "No hashed_strava_id found in the request",
                    "debug_counter": "No hashed_strava_id found in the request"}

        query = json_output['query'].encode('ascii', 'ignore').decode('ascii')

        thread = {"configurable": {"thread_id": str(uuid4())}}
        final_state = await app.ainvoke({"messages": [HumanMessage(content=query)],
                                         "hashed_strava_id" : hashed_strava_id
                                         },
                                         config = thread,
                                        )
        response_agent_result = final_state.get('response_agent_result', "No response from agent")
        sql_query = final_state.get('sql_query', "No SQL query from agent")
        execute_sql_status = final_state.get('execute_sql_status', "No SQL status from agent")
        visualization_type = final_state.get('visualization_type', "No visualization type from agent")
        visualization_agent_code = final_state.get('visualization_agent_code', "No visualization agent code from agent")
        retrieval_agent_result = final_state.get('retrieval_agent_result', "No retrieval agent result from agent")

        # for debugging purposes
        question_type = final_state.get('question_type', "No question type from agent")
        execute_sql_result = final_state.get('execute_sql_result', "No SQL result from agent")
        debug_counter = final_state.get('debug_counter', "No debug counter from agent")

        return {"status": "success", "response": response_agent_result,
                "sql_query": sql_query, "question_type": question_type,
                "execute_sql_status": execute_sql_status, "execute_sql_result": execute_sql_result, "debug_counter": debug_counter,
                "visualization_type": visualization_type, "visualization_agent_code": visualization_agent_code,
                "retrieval_agent_result": retrieval_agent_result}
    except Exception as e:
        logger.exception(f"Error processing Strava text2sql request: {str(e)}")
        return {"status": "failed", "response": f"Internal server error due to {str(e)}",
                "sql_query": "", "question_type": "",
                "execute_sql_status": "", "execute_sql_result": "", "debug_counter": "",
                "visualization_type": "", "visualization_agent_code": "",
                "retrieval_agent_result": ""}

