class GuppiError(Exception):
    pass

class InvalidTransition(GuppiError):
    pass

class GuardBlocked(GuppiError):
    pass

class CaptainApprovalRequired(GuppiError):
    def __init__(self, gate):
        self.gate = gate
        super().__init__(f"Captain approval required: {gate['gate_id']}")

class RegistryError(GuppiError):
    pass

class CompatibilityError(GuppiError):
    pass
