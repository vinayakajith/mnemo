"""Memory interface stub. Phase 2 will replace this with Mem0 + vector DB."""


class NoopMemory:
    """Phase 2 will replace this with Mem0 + vector DB."""

    def get_context(self, user_input: str) -> str:
        return ""

    def write(self, user_input: str, assistant_output: str) -> None:
        pass
