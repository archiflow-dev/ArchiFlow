"""
Vagueness Detector - Analyze prompts and score vagueness.

Part of Phase 1: Basic Prompt Analysis
"""

from dataclasses import dataclass
from typing import List
import re


@dataclass
class VaguenessScore:
    """Result of vagueness analysis."""

    score: int  # 0-100, higher = more vague
    issues: List[str]
    suggestions: List[str]

    @property
    def is_vague(self) -> bool:
        """Check if prompt is considered vague (threshold: 60)."""
        return self.score >= 60

    @property
    def severity(self) -> str:
        """Get severity level based on score."""
        if self.score >= 80:
            return "high"
        elif self.score >= 60:
            return "medium"
        else:
            return "low"


class VaguenessDetector:
    """
    Analyze prompts and detect vagueness.

    Scoring algorithm:
    - Base score starts at 0
    - Each vagueness indicator adds points
    - Maximum score is 100

    Vagueness indicators:
    - Very short prompts (< 10 chars): +30
    - No specific files/paths mentioned: +25
    - Uses vague verbs ("help", "do", "make"): +20
    - No clear objective/task: +15
    - No success criteria: +10
    """

    # Vague verbs that indicate unclear intent
    VAGUE_VERBS = [
        'help', 'do', 'make', 'fix', 'work', 'handle', 'deal',
        'improve', 'better', 'update', 'change', 'modify', 'check'
    ]

    # Specific verbs that indicate clear intent
    SPECIFIC_VERBS = [
        'review', 'analyze', 'implement', 'refactor', 'test',
        'debug', 'optimize', 'validate', 'document', 'migrate'
    ]

    # Task type keywords
    TASK_KEYWORDS = {
        'code_review': ['review', 'analyze', 'audit', 'check', 'inspect'],
        'bug_fix': ['fix', 'debug', 'solve', 'resolve', 'repair'],
        'feature': ['implement', 'add', 'create', 'build', 'develop'],
        'refactor': ['refactor', 'clean', 'reorganize', 'restructure'],
        'testing': ['test', 'verify', 'validate', 'coverage'],
        'documentation': ['document', 'explain', 'describe']
    }

    def __init__(self, vagueness_threshold: int = 60):
        """
        Initialize vagueness detector.

        Args:
            vagueness_threshold: Score threshold for considering a prompt vague (default: 60)
        """
        self.threshold = vagueness_threshold

    def analyze(self, prompt: str) -> VaguenessScore:
        """
        Analyze a prompt and return vagueness score.

        Args:
            prompt: User's prompt to analyze

        Returns:
            VaguenessScore with score, issues, and suggestions
        """
        if not prompt or not prompt.strip():
            return VaguenessScore(
                score=100,
                issues=["Empty prompt"],
                suggestions=["Please provide a description of what you want to do"]
            )

        prompt = prompt.strip()
        score = 0
        issues = []
        suggestions = []

        # Check 1: Very short prompt (< 10 characters)
        if len(prompt) < 10:
            score += 30
            issues.append("Very short prompt (less than 10 characters)")
            suggestions.append("Provide more detail about what you want to achieve")

        # Check 2: No specific files or paths mentioned
        if not self._mentions_files(prompt):
            score += 25
            issues.append("No specific files or paths mentioned")
            suggestions.append("Specify which files or directories to work with (e.g., 'src/auth/middleware.py')")

        # Check 3: Uses vague verbs or generic objects
        prompt_lower = prompt.lower()
        vague_verbs_found = [v for v in self.VAGUE_VERBS if f' {v} ' in f' {prompt_lower} ' or prompt_lower.startswith(f'{v} ')]
        specific_verbs_found = [v for v in self.SPECIFIC_VERBS if f' {v} ' in f' {prompt_lower} ' or prompt_lower.startswith(f'{v} ')]

        # Check for generic objects even with specific verbs
        generic_objects = ['my code', 'the code', 'this', 'that', 'it', 'something', 'everything']
        has_generic_object = any(obj in prompt_lower for obj in generic_objects)

        if vague_verbs_found and not specific_verbs_found:
            score += 20
            issues.append(f"Uses vague verbs: {', '.join(vague_verbs_found[:2])}")
            suggestions.append("Use specific action verbs (e.g., 'review', 'implement', 'refactor')")
        elif has_generic_object:
            score += 20
            issues.append("Uses generic objects (e.g., 'my code', 'this', 'that')")
            suggestions.append("Specify exactly what you're referring to (e.g., 'authentication module', 'login function')")

        # Check 4: No clear task type or objective
        if not self._has_clear_task_type(prompt):
            score += 15
            issues.append("No clear task type or objective")
            suggestions.append("Specify what you want to accomplish (e.g., 'for security issues', 'to add authentication')")

        # Check 5: Very generic terms
        generic_terms = ['code', 'this', 'that', 'it', 'stuff', 'thing', 'some']
        generic_found = [term for term in generic_terms if term in prompt_lower.split()]

        if len(generic_found) >= 2:
            score += 10
            issues.append("Uses generic terms without specifics")
            suggestions.append("Replace generic terms with specific components or features")

        # Check 6: No context about what/where/why
        if not self._has_context_clues(prompt):
            score += 10
            issues.append("Missing context about what, where, or why")
            suggestions.append("Include context: What component? Where in the codebase? Why is this needed?")

        # Cap score at 100
        score = min(score, 100)

        return VaguenessScore(
            score=score,
            issues=issues,
            suggestions=suggestions
        )

    def _mentions_files(self, prompt: str) -> bool:
        """Check if prompt mentions specific files or paths."""
        # Check for file patterns
        file_patterns = [
            r'\w+\.(py|js|ts|java|cpp|c|h|go|rs|rb|php)',  # File extensions
            r'src/[\w/]+',      # src/ paths
            r'tests?/[\w/]+',   # test/ paths
            r'[\w/]+/[\w/]+',   # Any path-like structure with /
            r'\.[\w/]+',        # Paths starting with ./
        ]

        for pattern in file_patterns:
            if re.search(pattern, prompt, re.IGNORECASE):
                return True

        return False

    def _has_clear_task_type(self, prompt: str) -> bool:
        """Check if prompt has clear task type indicators."""
        prompt_lower = prompt.lower()

        # Check if any task keywords are present
        for task_type, keywords in self.TASK_KEYWORDS.items():
            if any(keyword in prompt_lower for keyword in keywords):
                return True

        # Check for specific objectives
        objective_patterns = [
            r'for \w+',         # "for security", "for performance"
            r'to \w+',          # "to improve", "to fix"
            r'in order to',
            r'because',
            r'focusing on',
        ]

        for pattern in objective_patterns:
            if re.search(pattern, prompt_lower):
                return True

        return False

    def _has_context_clues(self, prompt: str) -> bool:
        """Check if prompt has context clues (what/where/why)."""
        prompt_lower = prompt.lower()

        # Context indicator words
        context_indicators = [
            # What
            'component', 'module', 'service', 'function', 'class', 'method',
            # Where
            'in', 'at', 'within', 'inside', 'located',
            # Why
            'because', 'since', 'so that', 'in order to', 'for',
            # Specific features
            'authentication', 'authorization', 'database', 'api', 'ui',
            'security', 'performance', 'scalability'
        ]

        # Count indicators
        indicator_count = sum(1 for indicator in context_indicators if indicator in prompt_lower)

        # Need at least 2 context clues
        return indicator_count >= 2


# Convenience function for simple usage
def detect_vagueness(prompt: str) -> VaguenessScore:
    """
    Quick vagueness detection for a prompt.

    Args:
        prompt: Prompt to analyze

    Returns:
        VaguenessScore
    """
    detector = VaguenessDetector()
    return detector.analyze(prompt)
