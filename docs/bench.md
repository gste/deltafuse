# Worker Benchmarks & Evaluation

The DeltaFuse evaluation benchmark suites, test cases (`J01`, `J03-document-flow`, `M01-M03`), qualification harness, mutation judges, and autonomous worker supervisors are maintained in the dedicated benchmark repository:

👉 **[gste/deltafuse-bench](https://github.com/gste/deltafuse-bench)**

## Quick Overview

`deltafuse-bench` evaluates how autonomous AI coding agents adhere to the **DeltaFuse Process** (`Intake -> Analyze -> Specify -> Decompose -> Declare -> Implement -> Verify`) and satisfy real-world multi-service integration requirements.

### Installation & Usage

```bash
# Clone and install the benchmark suite
git clone https://github.com/gste/deltafuse-bench.git
cd deltafuse-bench
pip install -e .

# Provision a clean sandbox
deltafuse-bench install /path/to/sandbox --force

# Run autonomous supervised execution
deltafuse-bench supervise /path/to/sandbox --little-coder --model poolside/laguna-xs-2.1

# Run scoring and evaluation
deltafuse-bench run --run-id run-01 --sandbox /path/to/sandbox --out /path/to/evidence
```

For complete documentation, test suite details, and scoring methodology, please refer to [gste/deltafuse-bench](https://github.com/gste/deltafuse-bench).
