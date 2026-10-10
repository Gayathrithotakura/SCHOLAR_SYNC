"""Subject domain model representing an academic course/module."""

from dataclasses import dataclass

from scholarsync.core.exceptions import InvalidTaskError


@dataclass(frozen=True)
class Subject:
    """Represents an academic subject or course offering.

    Attributes:
        code: Unique course identifier (e.g., 'CS601', 'AI702').
        name: Full descriptive course title (e.g., 'Advanced Algorithms').
        credits: Academic credit weight (must be an integer >= 1).
        description: Optional syllabus or course description.
    """

    code: str
    name: str
    credits: int = 3
    description: str = ""

    def __post_init__(self) -> None:
        """Validate subject attributes upon creation."""
        # Clean and validate code
        if not isinstance(self.code, str) or not self.code.strip():
            raise InvalidTaskError("Subject code must be a non-empty string.")

        # Clean and validate name
        if not isinstance(self.name, str) or not self.name.strip():
            raise InvalidTaskError("Subject name must be a non-empty string.")

        # Validate credits
        if not isinstance(self.credits, int) or isinstance(self.credits, bool):
            raise InvalidTaskError(
                f"Subject credits must be an integer, got {type(self.credits).__name__}."
            )
        if self.credits < 1:
            raise InvalidTaskError(f"Subject credits must be at least 1, got {self.credits}.")

        # Normalize code to uppercase and strip whitespace in frozen dataclass
        object.__setattr__(self, "code", self.code.strip().upper())
        object.__setattr__(self, "name", self.name.strip())
        object.__setattr__(self, "description", self.description.strip())

    def __str__(self) -> str:
        return f"{self.code}: {self.name} ({self.credits} credits)"
