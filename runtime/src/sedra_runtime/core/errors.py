class SedraError(Exception):
    pass

class InvalidTransition(SedraError):
    pass

class GuardBlocked(SedraError):
    pass

class CaptainApprovalRequired(SedraError):
    def __init__(self, gate):
        self.gate = gate
        super().__init__(f"Captain approval required: {gate['gate_id']}")

class RegistryError(SedraError):
    pass

class CompatibilityError(SedraError):
    pass
