class IgiturError(Exception):
    """Base exception for igitur errors."""
    pass

class IgiturAuthenticationError(IgiturError):
    """Raised when authentication fails."""
    pass