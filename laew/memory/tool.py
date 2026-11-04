"""Explicit, scoped memory proposals; never an automatic approval tool."""
from laew.tools.base import Tool, ToolResult, ErrorCode
from .store import validate_record
from .categories import category_schema, category_guidance, normalize_category, InvalidMemoryCategory


class MemoryTool(Tool):
    description = ('When the user explicitly asks to remember a durable fact, prepare a memory proposal immediately. '
                   'The user approves it in Settings > Memory. Do not claim it was saved as active memory. '
                   'User scope is personal cross-conversation information; project scope is restricted to this project. '
                   + category_guidance())
    operations={'propose':{'description':'Prepare a reviewable memory proposal from an explicit user request.',
        'params':['content','category','scope'],'required':['content','category','scope'],
        'properties':{'content':{'type':'string'},'category':category_schema(),'scope':{'type':'string','enum':['user','project']}}}}

    def invalid_input(self, message, /, **kwargs):
        result=super().invalid_input(message, **kwargs)
        try:
            normalize_category(kwargs.get('category'))
        except InvalidMemoryCategory as exc:
            result.error_message=str(exc)
            result.data=exc.details()
        return result

    def __init__(self,service,project_id=None,conversation_id=None,event_id=None):
        super().__init__(); self.service=service; self.project_id=project_id; self.conversation_id=conversation_id; self.event_id=event_id

    def validate(self,operation,**kwargs):
        try:
            if operation!='propose': raise ValueError('Unknown memory operation.')
            validate_record(kwargs.get('content'),kwargs.get('scope'),self.project_id if kwargs.get('scope')=='project' else None,kwargs.get('category'))
            return True,None
        except (TypeError,ValueError) as exc: return False,str(exc)

    def execute(self,operation,**kwargs):
        valid,error=self.validate(operation,**kwargs)
        if not valid: return self.invalid_input(error, **kwargs)
        try:
            key=self.service.create_proposal(kwargs['content'],kwargs['scope'],self.project_id if kwargs['scope']=='project' else None,
                kwargs['category'],{'conversation_id':self.conversation_id,'event_id':self.event_id,'origin':'model_proposal'})
            return ToolResult.ok({'proposal_id':key,'status':'pending_review' if key else 'already_remembered',
                'message':'Review the proposal in Settings > Memory before it becomes active.'})
        except Exception: return ToolResult.error(ErrorCode.ERR_INVALID_INPUT,'Memory storage is unavailable; nothing was approved.')
