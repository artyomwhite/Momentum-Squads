from fastapi import Request,HTTPException
def require_operator(request:Request):
    if not request.session.get("operator"):raise HTTPException(401,"Operator authentication required")
