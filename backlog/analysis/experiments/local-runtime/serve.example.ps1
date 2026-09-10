# Launch frozen ornith SUT for DeltaFuse A09. Requires llama-server on PATH.
# Set ORNITH_GGUF to the Q4_K_M file. Optional CUDA_VENDOR directory on PATH.
param()
if (-not $env:ORNITH_GGUF) {
    Write-Error "Set ORNITH_GGUF to Ornith-1.5-35B-Q4_K_M.gguf"
    exit 2
}
if ($env:CUDA_VENDOR) {
    $env:PATH = "$($env:CUDA_VENDOR);$env:PATH"
}
& llama-server `
  --model $env:ORNITH_GGUF `
  --alias ornith-1.5-35b-a3b `
  --host 127.0.0.1 --port 1240 --no-webui --jinja `
  --reasoning off `
  --ctx-size 33024 `
  --n-gpu-layers 99 --cpu-moe `
  --split-mode layer --ctx-checkpoints 32 `
  --batch-size 2048 --ubatch-size 512 `
  --threads 6 --parallel 4 `
  --cache-type-k f16 --cache-type-v f16 `
  --flash-attn on --kv-offload --kv-unified --load-mode mmap+mlock `
  --spec-type draft-mtp --spec-draft-n-max 2 --spec-draft-n-min 0 --spec-draft-p-min 0.75
