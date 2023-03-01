from fastapi import FastAPI, Request, Query
from enum import Enum


from worker import save_messages_task

# TODO: CORS

class Judge(str, Enum):
    lie = "lie"
    trust = "trust"

app = FastAPI()

@app.post("/save-messages")
async def save_messages(request: Request, judge: Judge=Query(...)):
    # requestから、channel_idを取得
    data = await request.form()
    channel_id = data["channel_id"]
    
    # 騙され役のuser_id
    customer_id = data["user_id"]
    
    task = save_messages_task.delay(channel_id, customer_id, judge)
    return {"message": f"Task submitted. {task.id}"}

