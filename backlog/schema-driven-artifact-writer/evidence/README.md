# Characterization evidence

probe.py was passed on stdin to the repository Python with -B at the framework
root, on Windows, 2026-09-18. It imports actual current source, uses an explicit
canonical schema directory and evaluates in-memory values. It writes no product
or source files. probe-result.json preserves the actual successful output.

The initial restricted-runtime invocation could not start the repository venv.
The bundled Python lacked yaml. An authorized host invocation using repository
Python then passed (exit 0); no package installation was performed.
These probes do not establish full test-suite health, platform durability or
model improvement. Proposed implementation tests belong to later cards.
