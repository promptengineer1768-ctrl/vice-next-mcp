"""Import-compatible alias for the ``vice-next-mcp`` source tree."""
from pathlib import Path
_src = Path(__file__).resolve().parent / 'src' / 'vice_next_mcp'
# This shim is also imported by pytest as a repository package, where Python
# does not initialize ``__path__``.  Keep it a proper namespace either way.
__path__ = list(globals().get('__path__', []))
if str(_src) not in __path__: __path__.append(str(_src))
if __package__:
    from .supervisor import Supervisor, InstanceLease, InstanceState
    from .transport import BinaryMonitorTransport, OperationEvidence
    __all__=['Supervisor','InstanceLease','InstanceState','BinaryMonitorTransport','OperationEvidence']
