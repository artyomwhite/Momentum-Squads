from fastapi import FastAPI,HTTPException,Header
from pydantic import BaseModel
from typing import Annotated
import asyncio
app=FastAPI(title="Idempotent Helpdesk Mock")
class Reply(BaseModel):
    ticket_id:str
    message:str
replies={}
@app.post("/tickets/{ticket_id}/replies",status_code=201)
async def create_reply(ticket_id:str,body:Reply,idempotency_key:Annotated[str,Header(alias="Idempotency-Key")],mode:str="ok"):
    if idempotency_key in replies:return replies[idempotency_key]
    if mode=="fail":raise HTTPException(500,"Simulated server error")
    if mode=="timeout":await asyncio.sleep(20)
    result={"ticket_id":ticket_id,"message":body.message,"idempotency_key":idempotency_key}
    replies[idempotency_key]=result
    return result
@app.get("/replies")
async def list_replies():return list(replies.values())
