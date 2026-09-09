class WorkflowError(Exception):
    """Base exception for all workflow-related errors."""
    pass


class WorkflowValidationError(WorkflowError):
    """Raised when a workflow definition is invalid."""
    pass


class WorkflowExecutionError(WorkflowError):
    """Raised when a workflow step execution fails."""
    pass


class ApprovalRequiredError(WorkflowError):
    """Raised when an approval is required but has not been granted."""
    pass


class RollbackError(WorkflowError):
    """Raised when a rollback operation fails."""
    pass
