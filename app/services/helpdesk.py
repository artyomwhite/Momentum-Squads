from urllib.parse import urlsplit
import os
import httpx
from app.config import get_settings
def validate_reply_url(value:str)->str:
    cfg=get_settings(); parsed=urlsplit(value)
    if not parsed.hostname or parsed.hostname.lower() not in cfg.allowed_helpdesk_hosts:
        raise ValueError("reply_url host is not allowlisted")
    if os.getenv("VERCEL") and parsed.hostname in {"localhost","127.0.0.1","mock-helpdesk"}:
        raise ValueError("local Helpdesk hosts are disabled in production")
    if parsed.scheme!="https" and parsed.hostname not in {"localhost","127.0.0.1","mock-helpdesk"}:
        raise ValueError("reply_url must use HTTPS")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("reply_url contains unsupported URL components")
    return value
async def send_reply(url:str,ticket_id:str,message:str,key:str):
    validate_reply_url(url)
    async with httpx.AsyncClient(timeout=httpx.Timeout(10,connect=3),follow_redirects=False) as client:
        response=await client.post(url,json={"ticket_id":ticket_id,"message":message},headers={"Idempotency-Key":key})
        response.raise_for_status()
        if response.status_code!=201: raise RuntimeError("Unexpected helpdesk response")
