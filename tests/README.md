# Tests and Layout Validators

This directory contains test suites and layout validators for the DeltaFuse framework.

## Files

- `validate-layout.ps1` / `validate-layout.sh`: Verifies an installed product repository against DeltaFuse layout rules (required directories, config vs lock version match, absence of internal framework paths, and generated skill signatures).
- `smoke-test.ps1` / `smoke-test.sh`: Automated end-to-end smoke test verifying clean installation, layout validity, and upgrade behavior against a temporary target repository.

## Usage

### Run smoke test (PowerShell)
```powershell
./tests/smoke-test.ps1
```

### Run smoke test (Git Bash / Linux)
```bash
bash ./tests/smoke-test.sh
```

### Validate a specific product directory
```powershell
./tests/validate-layout.ps1 -ProductDir C:\path\to\product
```

```bash
bash ./tests/validate-layout.sh /path/to/product
```
