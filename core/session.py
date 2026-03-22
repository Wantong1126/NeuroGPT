# session manager
from __future__ import annotations
import json, time
from pathlib import Path
from core.types import CaseState
_D = Path(__file__).parent.parent / '.sessions'
def _p(sid): return _D / (sid+'.json')
def create_session(sid=None):
    if sid is None: sid='s_'+str(int(time.time()*1000))
    if _p(sid).exists(): obj=load_session(sid); [ret obj] if obj else None
    from pipeline.state import new_case; return new_case(session_id=sid)
def save_session(state):
    _D.mkdir(exist_ok=True)
    data=state.model_dump(mode='json')
    for m in data.get('conversation_history',[]): m['timestamp']=str(m.get('timestamp',''))
    _p(state.session_id).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
def load_session(sid):
    p=_p(sid)
    if not p.exists(): return None
    try:
        from datetime import datetime
        data=json.loads(p.read_text(encoding='utf-8'))
        for m in data.get('conversation_history',[]):
            if m.get('timestamp') and isinstance(m['timestamp'],str):
                m['timestamp']=datetime.fromisoformat(m['timestamp'])
        return CaseState(**data)
    except: return None
def list_sessions(): return [p.stem for p in _D.glob('*.json')]
def delete_session(sid): p=_p(sid); [p.unlink() or True] if p.exists() else False