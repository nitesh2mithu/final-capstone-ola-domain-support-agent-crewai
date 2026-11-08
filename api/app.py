"""HTTP endpoints and private-session WebSocket chat for one worker."""
import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4
from smoke_tests.runtime import prepare_runtime
from rag.config import ROOT,offline_settings
prepare_runtime();offline_settings()
from support.session import SupportSession
from support.models import SupportResponse
from fastapi import FastAPI,Request,WebSocket,WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from api.models import AskRequest,AskResponse,SessionRequest,ResetResponse,ChatRequest,APIError
from api.logging import JsonlWriter,RequestRecord,RequestAuditMiddleware,masked_payload,generated_id


class SupportService:
    def __init__(self,session):
        self.session=session
        self.lock=asyncio.Lock()
        self.connections=set()
        self.disconnects=0

    async def ask(self,query,session_id):
        # A global execution lock is intentionally conservative for pinned CrewAI
        # and shared model/history correctness. Waiters never block the event loop.
        async with self.lock:
            return await asyncio.to_thread(self.session.ask,query,session_id)

    async def reset(self,session_id,remove=False):
        async with self.lock:
            self.session.reset(session_id)
            if remove: self.session.histories.pop(session_id,None)


def create_app(log_path: Path=ROOT/'.runtime/api/requests.jsonl',session_factory=SupportSession):
    writer=JsonlWriter(Path(log_path))
    @asynccontextmanager
    async def lifespan(app):
        app.state.service=SupportService(session_factory())
        yield
        app.state.service.session.histories.clear()
        app.state.service.connections.clear()

    app=FastAPI(title='Ola Domain Support Agent API',lifespan=lifespan,docs_url=None,redoc_url=None)
    app.state.writer=writer
    app.add_middleware(RequestAuditMiddleware,writer=writer)

    @app.get('/')
    async def root():
        return {
            'name':'Ola Domain Support Agent',
            'mode':'MOCK_LLM',
            'endpoints':{'health':'/health','ask':'POST /ask','reset':'POST /reset-session','chat':'WS /ws/chat'},
        }

    @app.get('/health')
    async def health():
        return {'status':'ok','mode':'MOCK_LLM','api_keys_required':False}

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request,exc):
        # Omit exc.errors()/body entirely: FastAPI's default includes input values.
        record=request.state.audit
        record.outcome='validation_error';record.status_code=422
        return JSONResponse(status_code=422,content=APIError(trace_id=record.trace_id,error='validation_error').model_dump())

    @app.post('/ask',response_model=AskResponse,responses={422:{'model':APIError},500:{'model':APIError}})
    async def ask(payload: AskRequest,request: Request):
        record=request.state.audit;record.session_id=payload.session_id
        record.crew_executed=None  # Unknown until the crew/guardrail path returns.
        result=await app.state.service.ask(payload.query,'http-'+payload.session_id)
        response=SupportResponse.model_validate(result['response'])
        if record.phone_masked and 'phone_masked' not in response.guardrails:
            response.guardrails.append('phone_masked')
        record.outcome=response.outcome;record.crew_executed=result['kickoff_executed']
        return AskResponse(trace_id=record.trace_id,session_id=payload.session_id,response=response,
            crew_executed=result['kickoff_executed'],history_messages_before=result['history_messages_before'])

    @app.post('/reset-session',response_model=ResetResponse,responses={422:{'model':APIError},500:{'model':APIError}})
    async def reset(payload: SessionRequest,request: Request):
        record=request.state.audit;record.session_id=payload.session_id
        await app.state.service.reset('http-'+payload.session_id)
        record.outcome='session_reset'
        return ResetResponse(trace_id=record.trace_id,session_id=payload.session_id,reset=True)

    @app.websocket('/ws/chat')
    async def websocket_chat(websocket: WebSocket):
        service=app.state.service
        # Clients cannot inject HTTP or another connection's session ID.
        session_id='ws-'+generated_id()
        await websocket.accept()
        service.connections.add(session_id)
        try:
            while True:
                message=await websocket.receive()
                if message['type']=='websocket.disconnect':
                    raise WebSocketDisconnect(message.get('code',1000))
                record=RequestRecord('websocket','/ws/chat');record.session_id=session_id
                raw=message.get('text')
                raw_bytes=raw.encode('utf-8') if raw is not None else message.get('bytes',b'')
                safe,text,masked=masked_payload(raw_bytes)
                record.masked_request_text=text;record.phone_masked=masked
                try:
                    if raw is None: raise ValueError('Text JSON required')
                    payload=ChatRequest.model_validate_json(safe)
                except (ValidationError,ValueError):
                    record.outcome='validation_error';record.status_code=422
                    reply=APIError(trace_id=record.trace_id,error='validation_error').model_dump()
                else:
                    # A backend ValueError is an internal error, not bad JSON.
                    record.crew_executed=None
                    try:
                        result=await service.ask(payload.query,session_id)
                        response=SupportResponse.model_validate(result['response'])
                        if masked and 'phone_masked' not in response.guardrails: response.guardrails.append('phone_masked')
                        record.outcome=response.outcome;record.status_code=200
                        record.crew_executed=result['kickoff_executed']
                        reply=AskResponse(trace_id=record.trace_id,session_id=session_id,response=response,
                            crew_executed=result['kickoff_executed'],history_messages_before=result['history_messages_before']).model_dump()
                    except Exception:
                        record.outcome='internal_error';record.status_code=500
                        reply=APIError(trace_id=record.trace_id,error='internal_error').model_dump()
                try:
                    await websocket.send_json(reply)
                except WebSocketDisconnect:
                    record.outcome='client_disconnected';record.status_code=499
                    raise
                finally:
                    # One message entry even if peer disappears during processing.
                    writer.write(record.entry())
        except WebSocketDisconnect:
            service.disconnects+=1
        finally:
            service.connections.discard(session_id)
            await service.reset(session_id,remove=True)

    return app


app=create_app()
