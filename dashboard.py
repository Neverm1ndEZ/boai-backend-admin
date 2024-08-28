from fastapi import FastAPI, HTTPException, Query, Body, APIRouter, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Optional, Dict, Union
from datetime import datetime, timedelta
from collections import defaultdict
from db import get_db
import logging
from bson.objectid import ObjectId

from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader, OAuth2PasswordRequestForm
from auth import create_access_token, get_current_admin, super_admin_required
from db_operations import create_admin, verify_admin, get_db

app = FastAPI()



# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# CORS middleware setup
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

db = get_db()

# --- Models ---

class User(BaseModel):
    email: str
    username: str
    signup_date: Optional[datetime]

class Video(BaseModel):
    video_id: str
    workspace_id: str
    creation_date: Optional[datetime]
    user_location: Optional[str]
    user_industry: Optional[str]

class WorkspaceContent(BaseModel):
    workspace_id: str
    name: Optional[str]
    screenplay_ids: List[str]
    lineup_ids: List[str]

class UserWorkspaceContent(BaseModel):
    user_email: str
    workspaces: List[WorkspaceContent]

class CreditUpdate(BaseModel):
    credits: int

class VideoTrend(BaseModel):
    date: str
    count: int

class AdminCreate(BaseModel):
    email: str
    password: str
    is_super_admin: bool = False

# --- API Endpoints ---


api_key_header = APIKeyHeader(name="Authorization", auto_error=False)

async def get_current_admin_from_token(api_key: str = Security(api_key_header)):
    if not api_key or not api_key.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid or missing API Key")
    token = api_key.split()[1]
    return await get_current_admin(token)


@app.post("/admin/login")
async def admin_login(form_data: OAuth2PasswordRequestForm = Depends()):
    admin = verify_admin(form_data.username, form_data.password)
    if not admin:
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    access_token = create_access_token(data={"sub": admin['email']})
    return {"access_token": access_token, "token_type": "bearer"}

@app.post("/admin/create")
async def create_new_admin(
    admin_data: AdminCreate,
    current_admin: dict = Depends(super_admin_required)
):
    try:
        create_admin(admin_data.email, admin_data.password, admin_data.is_super_admin)
        return {"message": "Admin created successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))





@app.get("/users", response_model=List[User], operation_id="list_users")
async def list_users():
    """List all registered users with their email, username, and signup date"""
    try:
        users = db.users.find({}, {"email": 1, "username": 1, "registered_at": 1})
        user_list = [User(
            email=user.get("email", "No email"),
            username=user.get("username", "No username"),
            signup_date=user.get("registered_at")
        ) for user in users]
        logger.info(f"Retrieved {len(user_list)} users")
        return user_list
    except Exception as e:
        logger.error(f"Error fetching registered users: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/users/{email}/videos", response_model=List[Dict], operation_id="get_user_videos")
async def user_videos(user_email: str):
    """List all videos for a user with detailed information"""
    try:
        user = db.users.find_one({"email": user_email})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        user_location = user.get("location", "Unknown")
        user_industry = user.get("industry", "Unknown")
        user_workspaces = user.get("workspaces", [])
        
        video_list = []
        for workspace_id in user_workspaces:
            workspace = db.workspaces.find_one({"_id": workspace_id})
            if workspace:
                lineups = workspace.get("lineups", {})
                for video_id, video_data in lineups.items():
                    complete_video_data = db.lineups.find_one({"_id": ObjectId(video_id)})
                    if complete_video_data:
                        creation_date = (
                            complete_video_data.get("created_at") or
                            complete_video_data.get("createdAt") or
                            complete_video_data.get("creation_date") or
                            video_data.get("created_at") or
                            video_data.get("createdAt") or
                            video_data.get("creation_date")
                        )
                        
                        video_info = {
                            "video_id": str(complete_video_data["_id"]),
                            "workspace_id": str(workspace_id),
                            "creation_date": creation_date,
                            "user_location": user_location,
                            "user_industry": user_industry,
                            "clips": complete_video_data.get("clips", []),
                            "audio": complete_video_data.get("audio", {}),
                            "output": complete_video_data.get("output"),
                            "speed": complete_video_data.get("speed"),
                            "style": complete_video_data.get("style"),
                            "xml": complete_video_data.get("xml")
                        }
                        video_list.append(video_info)
        
        logger.info(f"Retrieved {len(video_list)} videos for user {user_email}")
        return video_list
    except Exception as e:
        logger.error(f"Error fetching videos for user {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/users/{email}/workspaces", response_model=UserWorkspaceContent, operation_id="get_user_workspaces")
async def user_workspaces(user_email: str):
    """Get workspace content (screenplay and lineup IDs) for a user"""
    try:
        user = db.users.find_one({"email": user_email})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        workspace_ids = user.get("workspaces", [])
        
        workspaces_content = []
        for workspace_id in workspace_ids:
            workspace = db.workspaces.find_one({"_id": workspace_id})
            if workspace:
                screenplay_ids = list(workspace.get("screenplays", {}).keys())
                lineup_ids = list(workspace.get("lineups", {}).keys())
                workspaces_content.append(WorkspaceContent(
                    workspace_id=str(workspace_id),
                    name=workspace.get("name"),
                    screenplay_ids=screenplay_ids,
                    lineup_ids=lineup_ids
                ))
        
        logger.info(f"Retrieved content for {len(workspaces_content)} workspaces for user {user_email}")
        return UserWorkspaceContent(user_email=user_email, workspaces=workspaces_content)
    except Exception as e:
        logger.error(f"Error fetching workspace content for user {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/users/{email}/credits", response_model=dict, operation_id="get_user_credits")
async def user_credits(user_email: str):
    """Get the credits associated with a user's email ID"""
    try:
        user = db.users.find_one({"email": user_email})
        if not user:
            raise HTTPException(status_code=404, detail="User not found")
        
        credits = user.get("credits")
        
        if credits is None:
            raise HTTPException(status_code=404, detail="Credits not found for this user")
        
        logger.info(f"Retrieved credits for user {user_email}: {credits}")
        return {
            "user_email": user_email,
            "credits": credits
        }
    except Exception as e:
        logger.error(f"Error retrieving credits for user {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/analytics/video-trend", operation_id="get_video_trend")
async def video_trend(user_email: str, days: int = Query(30, description="Number of days to analyze")):
    """Get the trend of video creation for a specific user over a specified number of days"""
    try:
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days)
        
        videos = await user_videos(user_email)
        
        # Filter videos within the date range and count by date
        video_counts = {}
        for video in videos:
            creation_date = video.get('creation_date')
            if creation_date:
                if isinstance(creation_date, str):
                    creation_date = datetime.fromisoformat(creation_date.rstrip('Z'))
                if start_date <= creation_date <= end_date:
                    date_str = creation_date.strftime("%Y-%m-%d")
                    video_counts[date_str] = video_counts.get(date_str, 0) + 1
        
        # Generate all dates in the range
        all_dates = [(start_date + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        
        # Create the trend data
        trend_data = [{"date": date, "video_count": video_counts.get(date, 0)} for date in all_dates]
        
        return {
            "user_email": user_email,
            "video_creation_trend": trend_data
        }
    except Exception as e:
        logger.error(f"Error fetching video creation trend for user {user_email}: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/analytics/workspace-usage", operation_id="get_workspace_usage")
async def workspace_usage(
    start_date: str = Query(..., description="Start date (YYYY-MM-DD)"),
    end_date: str = Query(..., description="End date (YYYY-MM-DD)"),
    granularity: str = Query("daily", description="Data granularity: hourly, daily, weekly, or monthly")
):
    """Get detailed workspace usage and video creation trend for a specified date range and granularity"""
    try:
        start_datetime = datetime.strptime(start_date, "%Y-%m-%d")
        end_datetime = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)
        
        # Validate granularity
        valid_granularities = ["hourly", "daily", "weekly", "monthly"]
        if granularity not in valid_granularities:
            raise HTTPException(status_code=400, detail=f"Invalid granularity. Choose from {', '.join(valid_granularities)}")
        
        # MongoDB aggregation pipeline
        pipeline = [
            {
                "$project": {
                    "name": 1,
                    "videos": {
                        "$objectToArray": "$lineups"
                    }
                }
            },
            {
                "$unwind": "$videos"
            },
            {
                "$match": {
                    "videos.v.created_at": {
                        "$gte": start_datetime,
                        "$lt": end_datetime
                    }
                }
            },
            {
                "$group": {
                    "_id": {
                        "workspace_id": "$_id",
                        "workspace_name": "$name",
                        "date": {"$dateToString": {"format": "%Y-%m-%d %H:00:00", "date": "$videos.v.created_at"}}
                    },
                    "video_count": {"$sum": 1}
                }
            },
            {
                "$sort": {"_id.date": 1}
            }
        ]
        
        results = list(db.workspaces.aggregate(pipeline))
        
        workspace_summary = {}
        hourly_trend = {}
        total_videos = 0
        
        for result in results:
            workspace_id = str(result["_id"]["workspace_id"])
            date_hour = result["_id"]["date"]
            count = result["video_count"]
            
            if workspace_id not in workspace_summary:
                workspace_summary[workspace_id] = {
                    "workspace_id": workspace_id,
                    "workspace_name": result["_id"]["workspace_name"],
                    "total_videos": 0,
                    "active_periods": 0
                }
            
            workspace_summary[workspace_id]["total_videos"] += count
            workspace_summary[workspace_id]["active_periods"] += 1
            total_videos += count
            
            key = date_hour if granularity == "hourly" else date_hour.split()[0]
            hourly_trend[key] = hourly_trend.get(key, 0) + count
        
        # Aggregate data based on granularity
        trend_data = aggregate_trend_data(hourly_trend, granularity, start_datetime, end_datetime)
        
        # Calculate additional statistics
        total_hours = int((end_datetime - start_datetime).total_seconds() / 3600)
        avg_videos_per_hour = total_videos / total_hours if total_hours > 0 else 0
        
        max_videos = max((item["count"] for item in trend_data), default=0)
        min_videos = min((item["count"] for item in trend_data), default=0)
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            "granularity": granularity,
            "total_workspaces": len(workspace_summary),
            "total_videos": total_videos,
            "workspace_summary": list(workspace_summary.values()),
            "trend_data": trend_data,
            "avg_videos_per_hour": round(avg_videos_per_hour, 2),
            "max_videos_in_period": max_videos,
            "min_videos_in_period": min_videos,
            "total_active_hours": len(hourly_trend),
            "workspace_utilization": round(len(hourly_trend) / total_hours * 100, 2) if total_hours > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error fetching workspace usage: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

# --- Helper Functions ---

def aggregate_trend_data(hourly_data: Dict[str, int], granularity: str, start_date: datetime, end_date: datetime) -> List[Dict[str, Union[str, int]]]:
    """Aggregate trend data based on the specified granularity"""
    if granularity == "hourly":
        return [{"date": date, "count": count} for date, count in hourly_data.items()]
    elif granularity == "daily":
        return aggregate_by_day(hourly_data)
    elif granularity == "weekly":
        return aggregate_by_week(hourly_data, start_date, end_date)
    elif granularity == "monthly":
        return aggregate_by_month(hourly_data)
    else:
        raise ValueError("Invalid granularity. Choose 'hourly', 'daily', 'weekly', or 'monthly'.")

def aggregate_by_day(hourly_data):
    """Aggregate hourly data to daily"""
    daily_data = defaultdict(int)
    for date_hour, count in hourly_data.items():
        day = date_hour.split()[0]
        daily_data[day] += count
    return [{"date": date, "count": count} for date, count in sorted(daily_data.items())]

def aggregate_by_week(hourly_data, start_date, end_date):
    """Aggregate hourly data to weekly"""
    weekly_data = defaultdict(int)
    for date_hour, count in hourly_data.items():
        date = datetime.strptime(date_hour.split()[0], "%Y-%m-%d")
        week_start = (date - timedelta(days=date.weekday())).strftime("%Y-%m-%d")
        weekly_data[week_start] += count
    return [{"date": date, "count": count} for date, count in sorted(weekly_data.items())]

def aggregate_by_month(hourly_data):
    """Aggregate hourly data to monthly"""
    monthly_data = defaultdict(int)
    for date_hour, count in hourly_data.items():
        month = date_hour[:7]  # YYYY-MM
        monthly_data[month] += count
    return [{"date": date, "count": count} for date, count in sorted(monthly_data.items())]

def daterange(start_date, end_date):
    """Generate a range of dates"""
    for n in range(int((end_date - start_date).days) + 1):
        yield start_date + timedelta(n)

# --- Main Execution ---

if __name__ == "__main__":
    import uvicorn
    
    # Run the FastAPI application using uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)