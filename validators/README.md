# Validators

Run the layout validator against a consuming product repository after installation or upgrade:

```powershell
./validators/validate-layout.ps1 -ProductDir C:\path\to\product
```

```bash
bash ./validators/validate-layout.sh /path/to/product
```

It verifies the v2 directory boundary, required pin files, Change roots, and generated skill metadata. JSON Schema-compatible YAML contracts for artifact content are under `schemas/**`; use a Draft 2020-12 validator after parsing YAML in integrations that create or modify those artifacts.
