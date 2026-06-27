from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.user import User
from app.services.auth_service import get_current_user
from app.services.nl_query_service import NLQueryError, ask_question

router = APIRouter(tags=["nl-query"])
templates = Jinja2Templates(directory="app/templates")


async def get_session():
    async with async_session_factory() as session:
        async with session.begin():
            yield session


@router.post("/ask", response_class=HTMLResponse)
async def ask_endpoint(
    request: Request,
    question: str = Form(...),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    try:
        answer = await ask_question(session, user.company_id, question)
    except NLQueryError as e:
        answer = f"Nelze zpracovat dotaz: {e}"

    return templates.TemplateResponse(
        "partials/ask_response.html", {"request": request, "answer": answer}
    )
