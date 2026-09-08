import logging

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from api.routes import auth, calendar, committees, disposables, email, proposals, reminders, telegram_webhook, users

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Social Port Hub API")

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(committees.router)
app.include_router(proposals.router)
app.include_router(calendar.router)
app.include_router(disposables.router)
app.include_router(email.router)
app.include_router(reminders.router)
app.include_router(telegram_webhook.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}


# Serve the WebApp SPA as static files. Mounted last so it doesn't shadow /api routes.
app.mount("/", StaticFiles(directory="webapp", html=True), name="webapp")
