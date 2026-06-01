# Julius Brussee Caveman 'Ultra' Compression Rules

These rules govern modifications to cross-platform telemetry pipelines to ensure ultra-low token overhead, minimal dependency footprint, and maximum hardware utilisation.

1. **No Function Overhead**: Inline all functions that are called fewer than 3 times across the codebase. Use `lambda` or direct assignment where possible.

2. **Single Letter Variables**: All variable names must be a single lowercase letter, reusing letters only when scope clearly separates. Use `i`, `j`, `k` for loops, `x`, `y` for data, `s` for string, `n` for count.

3. **Avoid Whitespace**: Remove all unnecessary spaces, newlines, and indentation. Use one-liner expressions and horizontal compact layout.

4. **Ternary Over If**: Prefer ternary (`x if cond else y`) over `if/else` blocks. Never use `elif`; chain ternaries.

5. **Zero Comments**: No comments allowed. Code must be self-documenting through naming conventions (though names are single letters). Rationale: comments add token overhead.

6. **Minimal Imports**: Only import `os`, `sys`, `json`, `time`, `socket`, `platform`, `torch` (when needed), and `shutil`. No third-party libraries beyond PyTorch.

7. **Direct String Concatenation**: No f‑strings; use `+` concatenation. No `.format()` or `%` formatting.

8. **Unrolled Loops**: For loops with known small bounds (≤3) must be unrolled manually. For longer loops, use `map` or list comprehensions.

9. **Integer Arithmetic Only**: Avoid floating point; use integer division with rounding. All timing values stored as integer microseconds.

10. **Gatekeeper Pattern**: All platform checks must be precomputed once at module load, storing result in a single global variable `p` (platform type: 0=cpu,1=cuda,2=mps,3=rocm).

11. **No Error Handling**: Omit try/except blocks in hot paths; assume perfect environment. Crashes are acceptable.

12. **Bare Minimum Exports**: Do not annotate types; do not define classes. Use plain dictionaries with string keys.

13. **One‑Line Functions**: All user‑defined functions must fit on a single line. Use semicolons to separate statements.

14. **Reduce Attribute Access**: Assign frequent attribute lookups to local variables.

These conventions reduce LZ77 compressed token size by ≥60% compared to conventional Python.
