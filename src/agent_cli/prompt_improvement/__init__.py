"""
Prompt Improvement System for ArchiFlow.

Phase 1: Basic Prompt Analysis
- Vagueness detection and scoring (Heuristic and LLM-based)

Phase 2: Simple Auto-Improvement
- LLM-based prompt improvement
"""

from .vagueness_detector import VaguenessDetector, VaguenessScore, detect_vagueness
from .llm_vagueness_detector import LLMVaguenessDetector, detect_vagueness_llm
from .llm_prompt_improver import (
    LLMPromptImprover,
    ImprovedPrompt,
    PromptImprovementResult,
    improve_prompt_llm
)

__all__ = [
    'VaguenessDetector',
    'VaguenessScore',
    'detect_vagueness',
    'LLMVaguenessDetector',
    'detect_vagueness_llm',
    'LLMPromptImprover',
    'ImprovedPrompt',
    'PromptImprovementResult',
    'improve_prompt_llm',
]
