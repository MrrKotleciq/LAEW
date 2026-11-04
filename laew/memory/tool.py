"""Scoped active-memory searches and reviewable memory proposals."""
from laew.tools.base import Tool, ToolResult, ErrorCode
from .store import validate_record
from .categories import category_schema, category_guidance, normalize_category, InvalidMemoryCategory


class MemoryTool(Tool):
    description = ('When the user explicitly asks to remember a durable fact, prepare a memory proposal immediately. '
                   'The user approves it in Settings > Memory. Do not claim it was saved as active memory. '
                   'Recall searches active Long-Term Memory in the current conversation scope. '
                   'Use a focused query if automatic recall did not supply enough evidence. '
                   + category_guidance())
    operations={'propose':{'description':'Prepare a reviewable memory proposal from an explicit user request.',
        'params':['content','category','scope'],'required':['content','category','scope'],
        'properties':{'content':{'type':'string'},'category':category_schema(),'scope':{'type':'string','enum':['user','project']}}},
        'recall': {
            'description': 'Search active User Memory and, in Project Chat, this project’s active Memory. '
                           'Returns matching IDs and stored evidence. An empty search is inconclusive.',
            'read_only': True,
            'params': ['query'],
            'required': ['query'],
            'properties': {'query': {'type': 'string', 'description': 'Focused search text, 1–1000 characters.'}},
        },
    }

    def invalid_input(self, message, /, **kwargs):
        result=super().invalid_input(message, **kwargs)
        if 'query' not in kwargs and ('category' in kwargs or 'content' in kwargs):
            try:
                normalize_category(kwargs.get('category'))
            except InvalidMemoryCategory as exc:
                result.error_message=str(exc)
                result.data=exc.details()
        return result

    def __init__(self,service,project_id=None,conversation_id=None,event_id=None):
        super().__init__(); self.service=service; self.project_id=project_id; self.conversation_id=conversation_id; self.event_id=event_id

    def validate(self,operation,**kwargs):
        if operation == 'recall':
            query = kwargs.get('query')
            if set(kwargs) != {'query'} or not isinstance(query, str) or not query.strip() or len(query) > 1000:
                return False, 'Recall requires only a non-empty query of at most 1000 characters.'
            return True, None
        try:
            if operation!='propose': raise ValueError('Unknown memory operation.')
            validate_record(kwargs.get('content'),kwargs.get('scope'),self.project_id if kwargs.get('scope')=='project' else None,kwargs.get('category'))
            return True,None
        except (TypeError,ValueError) as exc: return False,str(exc)

    def execute(self,operation,**kwargs):
        valid,error=self.validate(operation,**kwargs)
        if not valid: return self.invalid_input(error, **kwargs)
        if operation == 'recall':
            return self._search(kwargs['query'].strip())
        try:
            key=self.service.create_proposal(kwargs['content'],kwargs['scope'],self.project_id if kwargs['scope']=='project' else None,
                kwargs['category'],{'conversation_id':self.conversation_id,'event_id':self.event_id,'origin':'model_proposal'})
            return ToolResult.ok({'proposal_id':key,'status':'pending_review' if key else 'already_remembered',
                'message':'Review the proposal in Settings > Memory before it becomes active.'})
        except Exception: return ToolResult.error(ErrorCode.ERR_INVALID_INPUT,'Memory storage is unavailable; nothing was approved.')

    def _search(self, query):
        info = {'scopes': ['user', 'project'] if self.project_id is not None else ['user']}
        memories = self.service.recall(query, self.project_id, diagnostics=info)
        data = {'source': 'Long-Term Memory', 'status': info['status'], 'recall': info,
                'memories': self.service.evidence(memories)}
        if info['status'] in {'completed', 'no_results'}:
            return ToolResult.ok(data)
        if info.get('skip_reason') == 'recall_disabled':
            return ToolResult(False, data, 'ERR_MEMORY_DISABLED', 'Memory Recall is disabled for this conversation.')
        if info['status'] == 'unavailable':
            return ToolResult(False, data, 'ERR_MEMORY_UNAVAILABLE', 'Memory Recall is unavailable.')
        return ToolResult(False, data, 'ERR_MEMORY_RECALL', 'The Memory search failed.')
