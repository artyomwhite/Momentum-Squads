import asyncio
from app.db import SessionLocal,engine
from app.models import Base,Article
ARTICLES=[
("kb_001","Sign in and password reset","Accounts","Sign in with your workspace email. Use Forgot password to receive a time-limited reset link. Contact an administrator if locked.","/knowledge/kb_001"),
("kb_002","Update workspace settings","Workspace","Administrators can change workspace name, timezone, and default currency in Settings > Workspace. Changes apply to new reports.","/knowledge/kb_002"),
("kb_003","Create a project","Projects","Open Projects and select New project. Enter a name and workspace. Invite members after creation. Project creation permission is required.","/knowledge/kb_003"),
("kb_004","Invite and manage users","Users","Administrators can invite users from Settings > Members. Pending invitations expire after seven days. Remove access from the member menu.","/knowledge/kb_004"),
("kb_005","Export a report to PDF","Reports","Open a saved report, select Export, then choose PDF. Large reports may take a few minutes. Keep the browser tab open until the download begins.","/knowledge/kb_005"),
("kb_006","Export report data to CSV","Reports","Select Export > CSV from a report. CSV exports contain the selected date range and filters. Remove filters if expected rows are missing.","/knowledge/kb_006"),
("kb_007","Plans and usage limits","Billing","Starter supports up to five members and 10 projects. Team supports unlimited projects and scheduled exports. Check Billing for current usage.","/knowledge/kb_007"),
("kb_008","Connect integrations","Integrations","Administrators can connect supported services from Settings > Integrations. Follow provider authorization and verify the connection after returning.","/knowledge/kb_008"),
("kb_009","Troubleshoot PDF exports","Troubleshooting","If PDF export fails, retry with a smaller date range, confirm downloads are allowed, and check that the report finished loading. Contact support with the report URL if it continues.","/knowledge/kb_009")]
async def main():
    async with engine.begin() as c:await c.run_sync(Base.metadata.create_all)
    async with SessionLocal() as s:
        for id,title,category,content,url in ARTICLES:
            if not await s.get(Article,id):s.add(Article(id=id,title=title,category=category,content=content,url=url))
        await s.commit()
    await engine.dispose()
if __name__=="__main__":asyncio.run(main())
