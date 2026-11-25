"""Review-required Global Knowledge curation, separate from long-term memory."""
__all__ = ['KnowledgeCurationService', 'KnowledgeProposalTool']


def __getattr__(name):
    if name == 'KnowledgeCurationService':
        from .service import KnowledgeCurationService
        return KnowledgeCurationService
    if name == 'KnowledgeProposalTool':
        from .tool import KnowledgeProposalTool
        return KnowledgeProposalTool
    raise AttributeError(name)
