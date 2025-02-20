from app_instance import strava_client_id, strava_client_secret, weekday_mapping_dic, month_mapping_dic, dw
import requests
from loguru import logger
from datetime import datetime, timezone
from app_instance import db, sg_timezone
import json
import pandas as pd
from utils import custom_hash, format_week_year_to_readable_dates
from utils_datawrapper_config import hex_colour_lst, distance_category_lst, strava_activity_type_lst


def strava_onboarding(user_chat_id, weblink):
    # Takes in a message from onboarding (which is /start) and returns a set of instructions  #={weblink}/strava?
    # Note ?chat_id={chat_id} << Putting chat_id in the GET request does not return in mobile applications. We store it after / instead

    mobile_permission_url = (
        f"https://www.strava.com/oauth/mobile/authorize?scope=read,activity:read_all,profile:read_all,read_all"
        f"&client_id={strava_client_id}&response_type=code"
        f"&redirect_uri={weblink}/strava-auth/{user_chat_id}"
        f"&approval_prompt=force"
    )
    welcome_text = (
        f"I’m Kenny Bot and I provide analytics on your running data!\n\n"
        f"I need permission from Strava so that I can access your running data.\n\n"
        f"Click on the [link here]({mobile_permission_url}) to grant my bot permission if you are on mobile!\n\n"
        f"Go to /home to look at the full list of commands!"
    )
    return welcome_text


def retrieve_refresh_token(code):
    http_link = "https://www.strava.com/oauth/token"
    data = {"client_id": strava_client_id, "client_secret": strava_client_secret, "grant_type": "authorization_code", "code": code}
    response = requests.post(http_link, data)
    credentials_dic = response.json()
    return credentials_dic


def retrieve_access_token(special_refresh_token):
    http_link = "https://www.strava.com/oauth/token"
    data = {
        "client_id": strava_client_id,
        "grant_type": "refresh_token",
        "refresh_token": special_refresh_token,
        "client_secret": strava_client_secret,
    }
    response = requests.post(http_link, data)
    credentials_dic = response.json()
    special_access_token = credentials_dic["access_token"]
    return special_access_token


async def retrieve_full_data_from_strava(special_refresh_token):
    """
    Collects data from strava in chronlogical order, with the latest run on TOP (page 1).
    Usually every athlete will only have one page, more active runners will have more than 1 page (I will have 2 for example).

    Should not be called often, only during the onboarding process.
    asyncio.run(retrieve_full_data_from_strava(special_refresh_token))
    """
    access_token = retrieve_access_token(special_refresh_token)
    http_link = f"https://www.strava.com/api/v3/athlete/activities?access_token={access_token}&per_page=200&page=1"
    headers = {"Authorization": f"Bearer {access_token}"}
    all_activities, page = [], 1

    # Paginate through all activities
    try:
        while True:
            params = {"per_page": 200, "page": page}
            response = requests.get(http_link, headers=headers, params=params)
            activities = response.json()

            if not activities:  # No more activities
                break

            all_activities.extend(activities)
            page += 1

    except Exception as e:
        logger.error(f"Error while fetching Strava data: {str(e)}")
        return {"status": "error", "message": f"Unexpected error: {str(e)}"}

    # Prepare activities for database storage
    db_activities = []
    for activity in all_activities:
        # Convert activity to database format
        db_activity = {
            "strava_id": str(activity["athlete"]["id"]),
            "hashed_strava_id": custom_hash(str(activity["athlete"]["id"])),
            "activity_id": str(activity["id"]),
            "name": activity["name"],
            "distance": activity["distance"],
            "moving_time": activity["moving_time"],
            "elapsed_time": activity["elapsed_time"],
            "total_elevation_gain": activity["total_elevation_gain"],
            "type": activity["type"],
            "sport_type": activity.get("sport_type"),
            "workout_type": activity.get("workout_type"),
            "start_date": datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ"),
            "start_date_local": datetime.strptime(activity["start_date_local"], "%Y-%m-%dT%H:%M:%SZ"),
            "timezone": activity.get("timezone"),
            "utc_offset": activity.get("utc_offset"),
            "start_latlng": json.dumps(activity.get("start_latlng")),
            "end_latlng": json.dumps(activity.get("end_latlng")),
            "location_country": activity.get("location_country"),
            "achievement_count": activity.get("achievement_count", 0),
            "kudos_count": activity.get("kudos_count", 0),
            "comment_count": activity.get("comment_count", 0),
            "athlete_count": activity.get("athlete_count", 0),
            "photo_count": activity.get("photo_count", 0),
            "trainer": activity.get("trainer", False),
            "commute": activity.get("commute", False),
            "manual": activity.get("manual", False),
            "private": activity.get("private", False),
            "flagged": activity.get("flagged", False),
            "gear_id": activity.get("gear_id"),
            "average_speed": activity.get("average_speed"),
            "max_speed": activity.get("max_speed"),
            "average_cadence": activity.get("average_cadence"),
            "average_watts": activity.get("average_watts"),
            "weighted_average_watts": activity.get("weighted_average_watts"),
            "kilojoules": activity.get("kilojoules"),
            "device_watts": activity.get("device_watts", False),
            "has_heartrate": activity.get("has_heartrate", False),
            "average_heartrate": activity.get("average_heartrate"),
            "max_heartrate": activity.get("max_heartrate"),
            "max_watts": activity.get("max_watts"),
            "pr_count": activity.get("pr_count", 0),
            "total_photo_count": activity.get("total_photo_count", 0),
            "has_kudoed": activity.get("has_kudoed", False),
            "updated_at": datetime.now(timezone.utc).astimezone(sg_timezone),
        }
        db_activities.append(db_activity)

    # Bulk upsert activities into database
    # asyncio.run(db.connect())
    # asyncio.run(db.bulk_upsert(table='main.strava_activities', data=db_activities, constraint_columns=['strava_id', 'activity_id'], batch_size=100))
    await db.bulk_upsert(table="main.strava_activities", data=db_activities, constraint_columns=["strava_id", "activity_id"], batch_size=100)

    logger.info(
        f"Successfully upserted (updated) FULL {len(db_activities)} activities for user {activity['athlete']['id']} "
        f"at {datetime.now(timezone.utc).astimezone(sg_timezone)}"
    )

    return {"status": "success", "activities_count": len(db_activities), "data": all_activities}


async def create_update_data_from_strava(webhook_json):
    """
    This function will be called from webhook (Create/Update)

    webhook_json = {"aspect_type": "update", "event_time": 1734080686, "object_id": 13105339270, "object_type": "activity", "owner_id": 28923822, "subscription_id": 143570, "updates": {"title": "spontaneous run with oliver"}}
    webhook_json = {"aspect_type": "create", "event_time": 1734361442, "object_id": 13127941701, "object_type": "activity", "owner_id": 28923822, "subscription_id": 143570, "updates": {}}
    """
    owner_id, activity_id = webhook_json["owner_id"], webhook_json["object_id"]
    # asyncio.run(db.connect())
    # special_refresh_token_output = asyncio.run(db.fetch_one(f"SELECT refresh_token FROM main.botdata_v2 WHERE strava_id = $1", str(owner_id)))
    special_refresh_token_output = await db.fetch_one("SELECT refresh_token FROM main.botdata_v2 WHERE strava_id = $1", str(owner_id))
    if special_refresh_token_output is None:
        logger.info(f"STRAVA WEBHOOK SKIP (strava webhook subscribed but didn't record data into DB). for webhook {webhook_json}")
        return False

    special_refresh_token = special_refresh_token_output["refresh_token"]
    access_token = retrieve_access_token(special_refresh_token)

    # Get activity details from Strava
    headers = {"Authorization": f"Bearer {access_token}"}
    activity_url = f"https://www.strava.com/api/v3/activities/{activity_id}"

    try:
        response = requests.get(activity_url, headers=headers)
        activity = response.json()

        # Convert activity to database format
        db_activity = {
            "strava_id": str(activity["athlete"]["id"]),
            "hashed_strava_id": custom_hash(str(activity["athlete"]["id"])),
            "activity_id": str(activity["id"]),
            "name": activity["name"],
            "distance": activity["distance"],
            "moving_time": activity["moving_time"],
            "elapsed_time": activity["elapsed_time"],
            "total_elevation_gain": activity["total_elevation_gain"],
            "type": activity["type"],
            "sport_type": activity.get("sport_type"),
            "workout_type": activity.get("workout_type"),
            "start_date": datetime.strptime(activity["start_date"], "%Y-%m-%dT%H:%M:%SZ"),
            "start_date_local": datetime.strptime(activity["start_date_local"], "%Y-%m-%dT%H:%M:%SZ"),
            "timezone": activity.get("timezone"),
            "utc_offset": activity.get("utc_offset"),
            "start_latlng": json.dumps(activity.get("start_latlng")),
            "end_latlng": json.dumps(activity.get("end_latlng")),
            "location_country": activity.get("location_country"),
            "achievement_count": activity.get("achievement_count", 0),
            "kudos_count": activity.get("kudos_count", 0),
            "comment_count": activity.get("comment_count", 0),
            "athlete_count": activity.get("athlete_count", 0),
            "photo_count": activity.get("photo_count", 0),
            "trainer": activity.get("trainer", False),
            "commute": activity.get("commute", False),
            "manual": activity.get("manual", False),
            "private": activity.get("private", False),
            "flagged": activity.get("flagged", False),
            "gear_id": activity.get("gear_id"),
            "average_speed": activity.get("average_speed"),
            "max_speed": activity.get("max_speed"),
            "average_cadence": activity.get("average_cadence"),
            "average_watts": activity.get("average_watts"),
            "weighted_average_watts": activity.get("weighted_average_watts"),
            "kilojoules": activity.get("kilojoules"),
            "device_watts": activity.get("device_watts", False),
            "has_heartrate": activity.get("has_heartrate", False),
            "average_heartrate": activity.get("average_heartrate"),
            "max_heartrate": activity.get("max_heartrate"),
            "max_watts": activity.get("max_watts"),
            "pr_count": activity.get("pr_count", 0),
            "total_photo_count": activity.get("total_photo_count", 0),
            "has_kudoed": activity.get("has_kudoed", False),
            "updated_at": datetime.now(timezone.utc).astimezone(sg_timezone),
        }

        # Upsert activity into database
        # asyncio.run(db.bulk_upsert(table='main.strava_activities', data=[db_activity], constraint_columns=['strava_id', 'activity_id']))
        await db.bulk_upsert(table="main.strava_activities", data=[db_activity], constraint_columns=["strava_id", "activity_id"])

        logger.info(f"Successfully upserted activity {activity_id} for user {owner_id}")
        return True
    except Exception as e:
        logger.error(f"Error processing webhookactivity {activity_id}: {str(e)}. webhook id {webhook_json} due to {str(e)}")
        return False


async def delete_activity_from_strava(webhook_json):
    """
    skipping the verification step (to strava), will just shift the is_deleted column to true
    webhook_json = {"aspect_type": "delete", "event_time": 1732594651, "object_id": 12984504969, "object_type": "activity", "owner_id": 28923822, "subscription_id": 143570, "updates": {}}
    webhook_json = {"aspect_type": "create", "event_time": 1733143575, "object_id": 13029871322, "object_type": "activity", "owner_id": 28923822, "subscription_id": 143570, "updates": {}}
    webhook_json = {"aspect_type": "delete", "event_time": 1734361628, "object_id": 13127941701, "object_type": "activity", "owner_id": 28923822, "subscription_id": 143570, "updates": {}}
    """
    owner_id, activity_id = webhook_json["owner_id"], webhook_json["object_id"]
    try:
        # asyncio.run(db.connect())
        # asyncio.run(db.update(f"UPDATE main.strava_activities SET is_deleted = TRUE WHERE strava_id = $1 AND activity_id = $2", str(owner_id), str(activity_id)))
        await db.update(
            "UPDATE main.strava_activities SET is_deleted = TRUE WHERE strava_id = $1 AND activity_id = $2", str(owner_id), str(activity_id)
        )
        logger.info(f"Successfully deleted activity {activity_id} for user {owner_id}")
        return True
    except Exception as e:
        logger.error(f"Error processing deleting webhookactivity {activity_id}: {str(e)}. webhook id {webhook_json}")
        return False


async def baseline_analytics(strava_id, upload_to_file=True):
    """
    Data Wrangling into an API
    strava_id = 28923822
    asyncio.run(db.connect())
    activities = asyncio.run(db.fetch_all(f"SELECT * FROM main.strava_activities "
                                    "LEFT JOIN main.botdata_v2 ON main.strava_activities.strava_id = main.botdata_v2.strava_id "
                                    "WHERE main.strava_activities.strava_id = $1 and main.strava_activities.is_deleted = false", str(strava_id)))


    ['id', 'strava_id', 'activity_id', 'name', 'distance', 'moving_time', 'elapsed_time', 'total_elevation_gain', 'type', 'sport_type',
    'workout_type', 'start_date', 'start_date_local', 'timezone', 'utc_offset', 'start_latlng', 'end_latlng', 'location_country',
    'achievement_count', 'kudos_count', 'comment_count', 'athlete_count', 'photo_count', 'trainer', 'commute', 'manual', 'private', 'flagged',
    'gear_id', 'average_speed', 'max_speed', 'average_cadence', 'average_watts', 'weighted_average_watts', 'kilojoules', 'device_watts',
    'has_heartrate', 'average_heartrate', 'max_heartrate', 'max_watts', 'pr_count', 'total_photo_count', 'has_kudoed', 'updated_at', 'is_deleted']
    """
    logger.info(f"Fetching baseline analytics for {strava_id}")
    activities = await db.fetch_all(
        "SELECT * FROM main.strava_activities "
        "LEFT JOIN main.botdata_v2 ON main.strava_activities.strava_id = main.botdata_v2.strava_id "
        "WHERE main.strava_activities.strava_id = $1 and main.strava_activities.is_deleted = false",
        str(strava_id),
    )
    full_df = pd.DataFrame(activities)

    # temp
    full_df = full_df.sort_values(by="start_date_local", ascending=False)

    # Basic Transformation
    full_df = (
        full_df.assign(
            start_date_local=pd.to_datetime(full_df["start_date_local"]),
            Weekday=lambda df: df["start_date_local"].dt.dayofweek.map(weekday_mapping_dic),
            Year=lambda df: df["start_date_local"].dt.year,
            IsoYear=lambda df: df["start_date_local"].dt.isocalendar().year,
            Month=lambda df: df["start_date_local"].dt.month,
            Day=lambda df: df["start_date_local"].dt.day,
            Week=lambda df: df["start_date_local"].dt.isocalendar().week,
            Hour=lambda df: df["start_date_local"].dt.hour,
            distance_km=lambda df: df["distance"] / 1000,
            moving_time_hours=lambda df: df["moving_time"] / 3600,
            DayofYear=lambda df: df["start_date_local"].dt.dayofyear,
        )
        .query("Year >= 2000")
        .assign(DayofYearBase=lambda df: (df["start_date_local"] - pd.Timestamp(f"{df['Year'].min()}-01-01")).dt.days)
    )

    # Workout Type Breakdown
    # workout_breakdown = full_df['type'].value_counts().reset_index().rename(columns={'type': 'Workout Type', 'count': 'Count'})
    workout_breakdown = pd.pivot_table(full_df, index="Year", columns="type", values="distance_km", aggfunc="count").fillna(0)
    workout_percentages = (workout_breakdown.div(workout_breakdown.sum(axis=1), axis=0) * 100).round(1)
    workout_activity_lst = workout_breakdown.columns.tolist()

    # Running-specific analytics
    running_df = full_df[full_df["type"].isin(["Run", "VirtualRun"])].copy()

    # Heatmap json
    current_year = datetime.now().year
    current_year_running_df = running_df[running_df["Year"] == current_year].copy()
    current_year_running_df["epoch_time"] = current_year_running_df["start_date"].apply(lambda x: str(int(x.timestamp())))
    current_year_running_df.index = current_year_running_df["epoch_time"]
    current_year_running_df["distance_km_round"] = current_year_running_df["distance_km"].apply(lambda x: int(x))

    # Calculate running streaks
    dates = running_df["start_date_local"].dt.date.sort_values().drop_duplicates()
    dates_df = pd.DataFrame({"date": dates})
    dates_df["diff"] = dates_df["date"].diff().dt.days
    dates_df["streak_group"] = (dates_df["diff"] != 1).cumsum()
    streak_lengths = dates_df.groupby("streak_group").size()

    # Distance categorization
    distance_bins = [0, 2.5, 5, 8, 10, 15, 21.0975, 25, 30, 42.195, 50, float("inf")]
    distance_labels = ["Under 2.5km", "2.5km", "5km", "8km", "10km", "15km", "Half Marathon", "25km", "30km", "Marathon", "50km+"]

    running_df["distance_type"] = pd.cut(running_df["distance_km"], bins=distance_bins, labels=distance_labels, right=False)
    distance_distribution = (
        pd.pivot_table(running_df, index="Year", columns="distance_type", values="distance_km", aggfunc="count", observed=False).fillna(0).transpose()
    )

    # Weekly and monthly aggregations
    # Get the latest date and create a range of the last 20 weeks
    max_year = running_df["IsoYear"].max()
    max_week = running_df[running_df["IsoYear"] == max_year]["Week"].max()
    latest_date = pd.to_datetime(f"{max_year}-{max_week:02d}-0", format="%Y-%U-%w")
    date_range = pd.date_range(end=latest_date, periods=20, freq="W-SUN")
    complete_weeks = pd.DataFrame({"IsoYear": date_range.year, "Week": date_range.isocalendar().week})

    weekly_stats = (
        running_df.groupby(["IsoYear", "Week"])
        .agg({"distance_km": "sum", "moving_time_hours": "sum"})
        .round(2)
        .rename(columns={"distance_km": "Distance (km)", "moving_time_hours": "Time (h)"})
        .reset_index()
        .merge(complete_weeks, on=["IsoYear", "Week"], how="right")
        .fillna(0)
        .sort_values(["IsoYear", "Week"])
    )
    weekly_stats["WeekFormat"] = weekly_stats.apply(format_week_year_to_readable_dates, axis=1)

    # Monthly Stats
    monthly_stats = running_df.groupby(["Year", "Month"]).agg({"distance_km": "sum"}).rename(columns={"distance_km": "Distance (km)"}).reset_index()
    pivoted_monthly_stats = (
        monthly_stats.pivot(index="Month", columns="Year", values="Distance (km)")
        .reindex(range(1, 13))  # ensure all months are present
        .fillna(0.0)  # Fill NaN with 0
        .round(1)
    )  # Round to 1 decimal place
    pivoted_monthly_stats.index = pivoted_monthly_stats.index.map(month_mapping_dic)

    # Time of day analysis
    time_of_day = running_df["Hour"].agg({"most_common_hour": lambda x: x.mode().iloc[0], "is_night_runner": lambda x: (x.mode().iloc[0] > 12)})

    # Pace calculations
    running_df = running_df.assign(
        pace=lambda df: (df["moving_time"] / 60) / df["distance_km"],
        pace_category=lambda df: pd.qcut(df["moving_time"] / df["distance_km"], q=5, labels=["Very Fast", "Fast", "Medium", "Slow", "Very Slow"]),
    )

    # Weekday analysis
    weekday_stats = (
        running_df.groupby("Weekday").agg({"distance_km": ["count", "mean", "sum"], "moving_time": "sum", "total_elevation_gain": "sum"}).round(2)
    )

    # Year-over-year comparisons
    monthly_stats_pivot = pd.pivot_table(monthly_stats, values="Distance (km)", columns="Month", index="Year", aggfunc="sum").fillna(0)
    yoy_comparison = (
        running_df.groupby("Year")
        .agg({"distance_km": "sum", "moving_time_hours": "sum", "kudos_count": "sum", "total_elevation_gain": "sum"})
        .rename(
            columns={
                "distance_km": "RunningDistance (km)",
                "moving_time_hours": "Time (h) spent running",
                "kudos_count": "Kudos",
                "total_elevation_gain": "Elevation (m)",
            }
        )
        .merge(monthly_stats_pivot, on=["Year"], how="left")
        .round(2)
    )

    # Compile results
    analytics_results = {
        "last_updated": datetime.now(timezone.utc).astimezone(sg_timezone).strftime("%d %B %Y, at %H:%M"),
        "first_name": full_df["strava_firstname"].iloc[0],
        "summary": {
            "total_activities": str(int(len(full_df))),
            "total_distance": f"{float(running_df['distance_km'].sum()):.2f}",
            "total_elevation": f"{float(running_df['total_elevation_gain'].sum()):.2f}",
            "total_time": str(int(running_df["moving_time"].sum())),
            "total_kudos": str(int(running_df["kudos_count"].sum())),
            "total_distance_current_year": f"{float(current_year_running_df['distance_km'].sum()):.2f}",
        },
        "streaks": {
            "running_max": int(streak_lengths.max()),
            "notrunning_max": int((dates_df["diff"] - 1).max()),
            "current_streak": int(streak_lengths.iloc[-1]),
        },
        "latest_activity": {
            "date": running_df["start_date_local"].iloc[0].strftime("%d %B %Y, at %H:%M"),  # "13 December 2024, at 16:06"
            "distance": f"{float(running_df['distance_km'].iloc[0]):.2f}",
            "type": running_df["type"].iloc[0],
        },
        "patterns": {
            "most_common_hour": str(int(time_of_day["most_common_hour"])),
            "favorite_day": running_df["Weekday"].mode().iloc[0],
            "workout_types": workout_activity_lst,
        },
        "records": {
            "longest_run": f"{float(running_df['distance_km'].max()):.2f}",
            "fastest_pace": f"{float(running_df['pace'].min()):.2f}",
            "highest_elevation": f"{float(running_df['total_elevation_gain'].max()):.2f}",
        },
        "aggregations": {
            "weekly_stats": weekly_stats[["WeekFormat", "Distance (km)", "Time (h)"]].to_csv(index=False),  # DONE
            "monthly_stats": pivoted_monthly_stats.to_csv(),  # DONE
            "weekday_stats": weekday_stats.to_csv(index=False),  # havent decided on visualization
            "distance_distribution": distance_distribution.to_csv(),
            "yearly_stats": yoy_comparison.to_csv(),  # DONE
            "workout_composition_count": workout_breakdown.to_csv(index=False),  # NOT USED
            "workout_composition_percentage": workout_percentages.to_csv(),  # DONE,
            "heatmap_json": current_year_running_df["distance_km_round"].to_json(orient="index"),
        },
    }

    hashed_strava_id = custom_hash(strava_id)
    if upload_to_file:
        with open(f"data/activity_data/{hashed_strava_id}.json", "w") as outfile:
            json.dump(analytics_results, outfile)
        logger.info(f"Analytics results uploaded to file for {strava_id}")

    return analytics_results


async def datawrapper_initiate_charts(weblink, strava_id):
    """
    Initiate Datawrapper charts for a given Strava ID, meant to be called just once as we are getting data from a dynamic API.
    https://www.datawrapper.de/_/QWieq/

    Step 1 - Prepare the data from baseline_analytics
    Step 2 - Create the charts with the /stravajson API in the datawrapper interface (probably the easiest way)
    Step 3 - Export the configurations with the chart IDs with the get_chart_metadata function
    Step 4 - Create the charts with the create_and_publish_chart function in this function

    chart_data = dw.get_chart_metadata("nbA7s")
    strava_id = 28923822
    weblink = "https://stravav2.kennyvectors.com"

    asyncio.run(db.connect())
    asyncio.run(db.upsert(table='main.strava_charts', data={'strava_id': str(strava_id), 'strava_hashed_id': hashed_strava_id, 'chart_id': chart1_id,
            'chart_title': "Monthly Running Stats", 'web_link': f"{weblink}/stravajson/aggregations-monthly_stats?id={hashed_strava_id}",
            'embed_code_responsive': embed_code_responsive, 'embed_code_web_component': embed_code_web_component,
            'updated_at': datetime.now(timezone.utc).astimezone(sg_timezone)}, constraint_columns=['strava_id', 'chart_id']))
    """
    hashed_strava_id = custom_hash(strava_id)
    # Chart 1 - Month + Year Running Data (Table) TODO, make it dynamic
    year_lst = [str(year) for year in range(2018, 2031)]
    year_color_map = {year: hex_colour_lst[i % len(hex_colour_lst)] for i, year in enumerate(year_lst)}
    success, chart1_id, embed_code_responsive, embed_code_web_component = dw.create_and_publish_chart(
        title="Monthly Running Stats",
        chart_type="d3-bars-split",
        web_link=f"{weblink}/stravajson/aggregations-monthly_stats?id={hashed_strava_id}",
        visualization_settings={
            "color-category": {"map": year_color_map, "categoryOrder": year_lst, "categoryLabels": {}},
            "show-color-key": True,
            "color-by-column": True,
            "date-label-format": "MMMM",
        },
        publish_settings={"embed-width": 700, "embed-height": 400},
    )

    if success:
        await db.upsert(
            table="main.strava_charts",
            data={
                "strava_id": str(strava_id),
                "strava_hashed_id": hashed_strava_id,
                "chart_identifier_id": "chart1",
                "chart_id": chart1_id,
                "web_link": f"{weblink}/stravajson/aggregations-monthly_stats?id={hashed_strava_id}",
                "chart_title": "Monthly Running Stats",
                "embed_code_responsive": embed_code_responsive,
                "embed_code_web_component": embed_code_web_component,
                "updated_at": datetime.now(timezone.utc).astimezone(sg_timezone),
            },
            constraint_columns=["strava_id", "chart_identifier_id"],
        )

    # Chart 2 - Weekly Running Data (Line)
    success, chart2_id, embed_code_responsive, embed_code_web_component = dw.create_and_publish_chart(
        title="Weekly Mileage (past 20 weeks from latest activity)",
        chart_type="column-chart",
        web_link=f"{weblink}/stravajson/aggregations-weekly_stats?id={hashed_strava_id}",
        visualization_settings={
            "base-color": "#ea503f",
            "valueLabels": {"show": "always"},
            "disable-tabs": False,
            "chart-type-set": True,
            "plotHeightFixed": 200,
            "plotHeightRatio": 0.5,
        },
        describe_settings={"intro": "Distance and Time Spent on Running by Week"},
        publish_settings={"embed-width": 700, "embed-height": 500, "blocks": {"get-the-data": True}},
    )
    if success:
        await db.upsert(
            table="main.strava_charts",
            data={
                "strava_id": str(strava_id),
                "strava_hashed_id": hashed_strava_id,
                "chart_identifier_id": "chart2",
                "chart_id": chart2_id,
                "web_link": f"{weblink}/stravajson/aggregations-weekly_stats?id={hashed_strava_id}",
                "chart_title": "Weekly Mileage (past 20 weeks from latest activity)",
                "embed_code_responsive": embed_code_responsive,
                "embed_code_web_component": embed_code_web_component,
                "updated_at": datetime.now(timezone.utc).astimezone(sg_timezone),
            },
            constraint_columns=["strava_id", "chart_identifier_id"],
        )

    # Chart 3 - Yearly Comparison data
    from utils_datawrapper_config import visualization_chart_3_settings

    success, chart3_id, embed_code_responsive, embed_code_web_component = dw.create_and_publish_chart(
        title="Year-on-year Comparison Data",
        chart_type="tables",
        web_link=f"{weblink}/stravajson/aggregations-yearly_stats?id={hashed_strava_id}",
        visualization_settings=visualization_chart_3_settings,
        publish_settings={"embed-width": 900, "embed-height": 500},
    )
    if success:
        await db.upsert(
            table="main.strava_charts",
            data={
                "strava_id": str(strava_id),
                "strava_hashed_id": hashed_strava_id,
                "chart_identifier_id": "chart3",
                "chart_id": chart3_id,
                "chart_title": "Year-on-year Comparison Data",
                "web_link": f"{weblink}/stravajson/aggregations-yearly_stats?id={hashed_strava_id}",
                "embed_code_responsive": embed_code_responsive,
                "embed_code_web_component": embed_code_web_component,
                "updated_at": datetime.now(timezone.utc).astimezone(sg_timezone),
            },
            constraint_columns=["strava_id", "chart_identifier_id"],
        )

    # Chart 4 - Running composition using stacked bars https://workout.kennyvectors.com/stacktableexport
    activity_type_color_map = {activity_type: hex_colour_lst[i % len(hex_colour_lst)] for i, activity_type in enumerate(strava_activity_type_lst)}
    success, chart4_id, embed_code_responsive, embed_code_web_component = dw.create_and_publish_chart(
        title="Running Composition",
        chart_type="d3-bars-stacked",
        web_link=f"{weblink}/stravajson/aggregations-workout_composition_percentage?id={hashed_strava_id}",
        visualization_settings={
            "color-category": {"map": activity_type_color_map, "categoryLabels": {}},
            "show-color-key": True,
            "color-by-column": True,
        },
        publish_settings={"embed-width": 800, "embed-height": 400},
    )
    if success:
        await db.upsert(
            table="main.strava_charts",
            data={
                "strava_id": str(strava_id),
                "strava_hashed_id": hashed_strava_id,
                "chart_identifier_id": "chart4",
                "chart_id": chart4_id,
                "chart_title": "Running Composition",
                "web_link": f"{weblink}/stravajson/aggregations-workout_composition_percentage?id={hashed_strava_id}",
                "embed_code_responsive": embed_code_responsive,
                "embed_code_web_component": embed_code_web_component,
                "updated_at": datetime.now(timezone.utc).astimezone(sg_timezone),
            },
            constraint_columns=["strava_id", "chart_identifier_id"],
        )

    # Chart 5 - Running Distance Distribution
    year_color_map = {year: hex_colour_lst[i % len(hex_colour_lst)] for i, year in enumerate(distance_category_lst)}
    success, chart5_id, embed_code_responsive, embed_code_web_component = dw.create_and_publish_chart(
        title="Running Distance Distribution",
        chart_type="d3-bars-split",
        web_link=f"{weblink}/stravajson/aggregations-distance_distribution?id={hashed_strava_id}",
        visualization_settings={
            "color-category": {"map": year_color_map, "categoryOrder": distance_category_lst, "categoryLabels": {}},
            "show-color-key": True,
            "color-by-column": True,
        },
        publish_settings={"embed-width": 700, "embed-height": 400},
    )
    if success:
        await db.upsert(
            table="main.strava_charts",
            data={
                "strava_id": str(strava_id),
                "strava_hashed_id": hashed_strava_id,
                "chart_identifier_id": "chart5",
                "chart_id": chart5_id,
                "chart_title": "Running Distance Distribution",
                "web_link": f"{weblink}/stravajson/aggregations-distance_distribution?id={hashed_strava_id}",
                "embed_code_responsive": embed_code_responsive,
                "embed_code_web_component": embed_code_web_component,
                "updated_at": datetime.now(timezone.utc).astimezone(sg_timezone),
            },
            constraint_columns=["strava_id", "chart_identifier_id"],
        )

    # TODO Other charts to consider - look at 1) heart rate data, 2) ten percent (weekly rule) - but this rule does not really apply for low mileage runners - think about this.
    logger.info(f"Datawrapper charts completed for {strava_id}")
    return chart1_id, chart2_id, chart3_id, chart4_id, chart5_id
