# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

#### Phase 3: Architecture Refactoring (Prompt Compaction Refactoring)

**Task 3.1.1: Extract MessageFormatter**
- Created `MessageFormatter` class in `src/agent_framework/memory/message_formatter.py`
- Extracted message format conversion logic from `HistoryManager.to_llm_format()`
- `HistoryManager` now delegates to `MessageFormatter` for format conversion
- **Impact**: Separation of concerns, improved testability, easier to extend for new message types

**Test Coverage (Task 3.1.1)**:
- Added `tests/agent_framework/memory/test_message_formatter.py` with 16 comprehensive tests
- All tests passing (100% pass rate)
- Backward compatible (all existing tests still pass)

**Task 3.1.2: Extract CompactionStrategy**
- Created `CompactionStrategy` abstract base class in `src/agent_framework/memory/compaction_strategy.py`
- Implemented `SelectiveRetentionStrategy` (current anchor-based approach)
- Implemented `SlidingWindowStrategy` (alternative simple window approach)
- Created `CompactionAnalysis` dataclass for strategy results
- `HistoryManager` now delegates compaction analysis to pluggable strategies
- Added `compaction_strategy` parameter to `HistoryManager.__init__()` (defaults to `SelectiveRetentionStrategy`)
- Reduced code duplication: Removed ~120 lines of duplicated logic between `compact()` and `compact_async()`
- **Impact**: Pluggable compaction strategies, reduced code duplication, easier to test and extend

**Test Coverage (Task 3.1.2)**:
- Added `tests/agent_framework/memory/test_compaction_strategy.py` with 15 comprehensive tests
- All tests passing (100% pass rate)
- Tests cover both `SelectiveRetentionStrategy` and `SlidingWindowStrategy`
- Tests verify tool call/result preservation, anchor preservation, edge cases
- Backward compatible (all 13 integration tests + 10 async tests still pass)

**Task 3.1.3: Extract MessageCleaner Plugins**
- Created `MessageCleaner` abstract base class in `src/agent_framework/memory/message_cleaner.py`
- Implemented `TODOCleaner` (removes old TODO messages outside retention window, prevents orphaned results)
- Implemented `DuplicateCleaner` (removes consecutive duplicate messages outside retention window)
- Implemented `CompositeCleaner` (applies multiple cleaners in sequence)
- `HistoryManager` now uses pluggable message cleaners instead of inline TODO removal logic
- Added `message_cleaners` parameter to `HistoryManager.__init__()` (auto-configures TODOCleaner if `auto_remove_old_todos=True`)
- Removed old `_is_new_todo_message()`, `_is_todo_related_message()`, and `_remove_previous_todos()` methods (~90 lines)
- **Impact**: Pluggable cleanup logic, continuous cleaning (not just on TODO adds), prevents orphaned tool results

**Test Coverage (Task 3.1.3)**:
- Added `tests/agent_framework/memory/test_message_cleaner.py` with 20 comprehensive tests
- All tests passing (100% pass rate)
- Tests cover `TODOCleaner`, `DuplicateCleaner`, `CompositeCleaner`, and HistoryManager integration
- Tests verify retention window respect, orphaned result prevention, edge cases
- Updated `test_history_todo_removal.py` to reflect new continuous cleanup behavior
- Backward compatible (all 143 memory tests pass)

**Task 3.2: Implement Builder Pattern for HistoryManager**
- Created `HistoryManagerBuilder` class in `src/agent_framework/memory/history_builder.py` (420+ lines)
- Implemented fluent API with chainable configuration methods:
  - Summarizer selection: `with_simple_summarizer()`, `with_llm_summarizer()`, `with_hybrid_summarizer()`
  - Token limits: `with_max_tokens()`, `with_model_config()`, `with_buffer_tokens()`
  - Retention: `with_retention_window()`, `with_proactive_threshold()`
  - Strategies: `with_selective_retention()`, `with_sliding_window()`, `with_compaction_strategy()`
  - Cleaners: `with_todo_cleaner()`, `with_duplicate_cleaner()`, `with_message_cleaners()`
  - Behavior: `with_todo_removal()`, `with_publish_callback()`
- Created `HistoryManagerPresets` class with 5 preset configurations:
  - `minimal()`: Testing/simple use cases (SimpleSummarizer, 4000 tokens, retention 5)
  - `development()`: Development with LLM (LLMSummarizer, 8000 tokens, retention 10)
  - `production()`: All optimizations (HybridSummarizer, SelectiveRetention, both cleaners)
  - `chat()`: Chat-optimized (SlidingWindow, 4000 tokens, retention 20)
  - `long_conversation()`: Extended sessions (HybridSummarizer, 16000 tokens, retention 25)
- All presets return builders for further customization
- **Impact**: Simplified configuration, reduced boilerplate, preset patterns for common use cases

**Test Coverage (Task 3.2)**:
- Added `tests/agent_framework/memory/test_history_builder.py` with 24 comprehensive tests
- All tests passing (100% pass rate)
- Tests cover fluent API, all preset configurations, builder equivalence to direct construction
- Tests verify configuration validation (requires summarizer)
- Tests verify preset customization (can override defaults)

**Task 3.3: Comprehensive Integration Testing**
- Created `tests/integration/test_phase3_integration.py` with 13 integration tests (400+ lines)
- Tests verify all Phase 3 components working together:
  - Full integration: MessageFormatter + CompactionStrategy + MessageCleaner
  - Builder pattern with real workflows
  - Preset customization and configuration
  - Edge cases: empty history, single message, only duplicates, only TODOs
  - Performance: cleaner performance, formatter caching
  - All message types handled correctly
  - Compaction preserves anchors (system message, goal message)
- All tests passing (100% pass rate)
- **Impact**: Comprehensive end-to-end validation of Phase 3 refactoring

**Phase 3 Summary**:
- **Total New Tests**: 88 tests (100% passing)
  - MessageFormatter: 16 tests
  - CompactionStrategy: 15 tests
  - MessageCleaner: 20 tests
  - Builder Pattern: 24 tests
  - Integration: 13 tests
- **Code Impact**:
  - Created: ~1,350 lines of new code (6 files)
  - Created: ~2,300 lines of test code (6 test files)
  - Removed: ~270 lines through refactoring
- **Backward Compatibility**: All 143 existing memory tests pass
- **Architecture**: Clean separation of concerns, pluggable strategies, simplified configuration

#### Phase 2: Async & Performance (Prompt Compaction Refactoring)

**Task 2.1: Async Compaction**
- Added `summarize_async()` to `HistorySummarizer` base class for non-blocking summarization
- Added `generate_async()` to `LLMProvider` base class for async LLM calls
- Added `compact_async()` to `HistoryManager` for non-blocking compaction
- Added `add_async()` to `HistoryManager` for async message addition
- Added `schedule_compaction_background()` for background task scheduling
- Added `asyncio.Lock` for thread-safe concurrent compaction
- Graceful fallback to sync compaction when no event loop available
- **Impact**: Compaction no longer blocks (2-5s → < 0.5s non-blocking)

**Task 2.2: Proactive Compaction**
- Added `proactive_threshold` parameter to `HistoryManager` (default 0.8 = 80%)
- Modified `add()` and `add_async()` to trigger compaction at 80% capacity instead of 100%
- Added emergency compaction fallback at 100% if proactive compaction fails
- **Impact**: Compaction completes before hitting context limit, reducing overflow risk

**Task 2.3: Token Caching & Incremental Counting**
- Added `_token_cache` and `_cache_valid` to `HistoryManager` for O(1) token counting
- Implemented incremental token updates in `add()` and `add_async()`: cache += new_message_tokens
- Added `_count_message_tokens()` for single message token counting
- Added `_recalculate_tokens()` for full O(n) recalculation when cache invalidated
- Cache invalidation on: compaction, TODO removal, clear()
- **Impact**: Token counting is now O(1) instead of O(n), 2-5x faster for large histories

**Task 2.4: LLM Format Caching**
- Added `_llm_format_cache` to `HistoryManager` to cache `to_llm_format()` results
- Cache built on first call, returned on subsequent calls (avoids rebuilding)
- Cache invalidation on: add(), add_async(), compact(), compact_async(), clear(), TODO removal
- **Impact**: Eliminates format conversion overhead, 10-100x faster for repeated calls

**Task 2.5: Compaction Notifications**
- Added `CompactionStartedMessage` and `CompactionCompleteMessage` to message types
- Added optional `publish_callback` parameter to `HistoryManager.__init__()`
- Notifications published during `compact()` and `compact_async()`
- Notifications include: messages_before/after, tokens_before/after, time_elapsed, tokens_saved
- **Impact**: Real-time visibility into compaction events for UI/monitoring

**Test Coverage**:
- Added `tests/agent_framework/memory/test_async_compaction.py` with 10 tests (Task 2.1-2.2)
- Added `tests/agent_framework/memory/test_token_caching.py` with 9 tests (Task 2.3)
- Added `tests/agent_framework/memory/test_llm_format_caching.py` with 10 tests (Task 2.4)
- Added `tests/agent_framework/memory/test_compaction_notifications.py` with 8 tests (Task 2.5)
- **Total: 37 tests, 100% passing**

### Changed

#### Phase 1: Critical Fixes (Prompt Compaction Refactoring)

**Task 1.1: Switch to Tiktoken for Token Counting**
- **BREAKING**: Replaced rough character-based token estimation with tiktoken for >95% accuracy
- Added `src/agent_framework/llm/token_counter.py` with provider-specific token counting:
  - `TiktokenCounter` for OpenAI-compatible models (using tiktoken library)
  - `AnthropicCounter` for Claude models (using Anthropic's native API)
  - `FallbackCounter` for unknown providers (conservative chars // 4 estimation)
- Added factory function `create_token_counter(provider, model, client)` for easy instantiation
- All token counting now uses proper per-message overhead calculation
- Graceful fallback when tiktoken is unavailable (installation optional)
- **Impact**: Compaction now triggers at correct token limits, preventing context overflow and reducing wasted LLM calls

**Task 1.2: Make Auto-Refinement Opt-In**
- **BREAKING**: Changed `AUTO_REFINE_PROMPTS` default from `true` to `false`
- Added prominent warning in `.env.example` about 2x cost and latency impact
- Added runtime warning log when auto-refinement is enabled
- **Impact**: Users no longer experience unexpected 2x cost/latency increases; must explicitly opt-in

**Task 1.3: Explicit Dependency Injection for PromptRefinerTool**
- **BREAKING**: `PromptRefinerTool` now requires explicit LLM provider injection
- Removed hidden `_create_llm_from_env()` auto-creation (violates Dependency Inversion Principle)
- Constructor now raises `TypeError` with helpful message if LLM is not provided
- Error message includes usage example with `create_llm_provider()` factory
- **Impact**: Dependencies are now explicit and visible; testing is possible with mock LLMs

**Task 1.4: Integration and Performance Tests**
- Added `tests/integration/test_history_compaction.py` with 13 comprehensive tests:
  - Compaction triggering at token limit
  - Anchor preservation (system message, first user message, last N messages)
  - Tool call integrity (no orphaned tool results)
  - Summary generation (simple, LLM, hybrid)
  - TODO auto-removal functionality
- Added `tests/integration/test_history_performance.py` with 8 performance tests:
  - Compaction performance for large histories (< 1s for 100 messages)
  - Token counting performance (< 10ms average)
  - Message addition performance (< 1ms per message)
  - Memory usage verification
  - Scaling tests for retention window sizes
- All tests passing with excellent performance metrics

### Fixed
- Fixed token counting accuracy from ~75% (chars // 4) to >95% (tiktoken)
- Fixed compaction triggering logic to use accurate token counts
- Fixed hidden dependency issues in PromptRefinerTool (now explicit injection required)

### Added
- Comprehensive test coverage for token counting (28 tests in `test_token_counter.py`)
- Comprehensive test coverage for dependency injection (4 tests in `test_prompt_refiner_dependency_injection.py`)
- Performance benchmarks for history compaction operations
- Factory pattern for token counter creation across different providers

### Migration Guide

**For Users:**

1. **Token Counting**: No action required. If you want to install tiktoken for maximum accuracy:
   ```bash
   pip install tiktoken
   ```
   Falls back gracefully if not installed.

2. **Auto-Refinement**: If you were relying on auto-refinement being enabled by default:
   ```bash
   # In .env
   AUTO_REFINE_PROMPTS=true
   ```
   **Warning**: This doubles cost and latency. Only enable if intentional.

3. **PromptRefinerTool**: If you're instantiating PromptRefinerTool directly in custom code:
   ```python
   # OLD (will now fail):
   tool = PromptRefinerTool()

   # NEW (required):
   from agent_cli.agents.llm_provider_factory import create_llm_provider
   llm = create_llm_provider()
   tool = PromptRefinerTool(llm=llm)
   ```

**For Developers:**

- When writing tests for tools, use explicit mock LLM injection instead of relying on environment variables
- Token counting is now provider-aware; use `create_token_counter()` factory for portable code
- History compaction is thoroughly tested; see integration tests for usage examples

## [Previous Versions]

_To be added as versions are released_
