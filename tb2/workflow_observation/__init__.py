"""Read-only workflow observations; importing TB2 does not enable a source adapter."""

from .model import Model
from .reducer import reduce_observation

__all__ = ["Model", "reduce_observation"]
