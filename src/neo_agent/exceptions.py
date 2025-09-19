"""Custom exceptions raised by Project NEO."""


class AgentError(RuntimeError):
    """Base error for all agent related exceptions."""


class ConfigurationError(AgentError):
    """Raised when configuration values are invalid or missing."""


class SkillExecutionError(AgentError):
    """Raised when a skill fails to execute correctly."""


class PipelineError(AgentError):
    """Raised when a pipeline stage fails."""
