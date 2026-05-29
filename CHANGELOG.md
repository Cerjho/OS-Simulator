# Changelog

All notable changes to the OS-Simulator project will be documented in this file.

## [Unreleased] — 2026-05-29

### Added
- MIT License file (AUDIT FIX-6)
- Context-switch cost now consumed as actual wasted CPU ticks during scheduling (AUDIT FIX-2)
- TLB flush on every context switch, fulfilling the documented spec (AUDIT FIX-1)
- Logging in deadlock recovery path — previously silent exceptions (AUDIT FIX-5)
- CHANGELOG.md for tracking version history

### Changed
- CORS policy: removed wildcard `"*"` — only localhost dashboard origins allowed (AUDIT FIX-4)
- HTTP 503 (Service Unavailable) returned when kernel is not initialized, was HTTP 400 (AUDIT FIX-7)
- DiskSeekTrace tooltip component extracted to module level to prevent re-creation on every render (AUDIT FIX-8)
- `run_experiment_preset` decomposed from 120-line monolith into 4 focused helper functions (AUDIT FIX-9)
- Redesigned `priority_inversion` workload preset: corrected inverted priority values, forced a preemptive priority scheduler, and staggered process arrival times to properly demonstrate unbounded priority starvation.

### Fixed
- `_deadlock_recovery_countdown` and `_pending_deadlock_cycles` now properly initialized in `__init__` instead of using `getattr()` workarounds (AUDIT FIX-3)
- Fixed major regression in context-switch cost (AUDIT FIX-2) where synchronization requests were erroneously evaluated during CPU idle ticks, causing unhandled `DeadlockWarning` exceptions and permanently freezing the kernel tick loop around tick 121.

## [1.0.0] — 2026-05-28

### Added
- Complete OS simulation engine with 16 algorithms:
  - 6 CPU scheduling: FCFS, SJF, SRTF, Priority (with aging), Round Robin, MLFQ
  - 4 page replacement: FIFO, LRU, Clock, Optimal
  - 6 disk scheduling: FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK
- Synchronization primitives: Mutex, Semaphore, Monitor
- Deadlock detection (RAG cycle analysis) and prevention (Banker's Algorithm)
- Two filesystem implementations: FAT and inode-based with VFS layer
- React dashboard with real-time WebSocket visualization
- 285 passing tests with 77% code coverage
- 7 experiment workload presets
- MkDocs documentation site
