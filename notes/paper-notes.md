# SCLATE paper notes (read 2026-11-02 from arXiv 2609.32391; the full-text copy is local only and gitignored)
- Sec 3.1: open event scheduler; sources polled each tick with DispatchContext; FrontierQueue picks due sources (time or world-state gated); Effect Runner applies effects.
- Hybrid clock: flows with wall time while agent busy; jumps across idle gaps. Measured: 30-workday MetaClaw arc (40 calendar days) median 5.9 real hours, median speed-up 162x.
- Sec 3.2: Benchmark adapter = setup, source manifest, optional world provider, grading policy (independent grader). Agent adapter = session lifecycle, message delivery, state save/restore, readiness probe, memory spec.
- Sec 4.1 validation vs GAIA-2: all scheduled events delivered in same order, within 0.9s median / 2.0s max.
- Finding: added memory does not reliably beat harness-native memory; models differ widely in how they use the same harness+memory.
- Algorithm 1 (appendix B): idle -> jump to earliest fire; busy -> c += wall delta, fire what is ready; tie-break (t, source_id); completed registry H.
