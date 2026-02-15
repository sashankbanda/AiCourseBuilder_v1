# GPU setup for ASR (faster-whisper / CTranslate2)

Exit code **3221226505** (Windows `0xC0000005` = **STATUS_ACCESS_VIOLATION**) during transcription is usually caused by:

1. **Missing or wrong DLLs** (especially **zlibwapi.dll** and cuDNN) used by CTranslate2/cuDNN.
2. **float16 on older GPUs** (e.g. Pascal / GTX 10xx) that don’t have Tensor Cores.
3. **Crash at the first 30‑second chunk** (e.g. at ~28s) due to memory or VAD/cuDNN init.

The script already applies **Tier 2 & 3** fixes (DLL paths, stable compute type, VAD/beam_size options). If GPU still crashes, do the **Tier 1** steps below.

---

## Tier 1: Manual DLL setup (recommended if GPU still crashes)

CTranslate2 (used by faster-whisper) needs these DLLs. Loading them from the **ctranslate2** package folder avoids conflicts with other CUDA installs.

### 1. Locate the ctranslate2 folder

From the repo root, with the `asr` venv activated:

- **Windows:**  
  `D:\AiCourseBuilder_v1\asr\venv\Lib\site-packages\ctranslate2`
- Or in Python:
  ```text
  python -c "import ctranslate2; print(ctranslate2.__path__[0])"
  ```

### 2. Get and copy **zlibwapi.dll** (64‑bit)

- cuDNN on Windows expects **zlibwapi.dll** (64‑bit). If it’s missing, you often get a silent crash or `0xC0000005`.
- **Where to get it:**
  - NVIDIA’s cuDNN docs sometimes link to it, or it’s in CUDA/cuDNN redist packages.
  - You can also get a 64‑bit build of `zlib` and rename/copy the DLL to `zlibwapi.dll`, or use a known-good copy from a CUDA/cuDNN Windows install.
- **Copy** the 64‑bit `zlibwapi.dll` into:
  ```text
  asr\venv\Lib\site-packages\ctranslate2\
  ```

### 3. Match CUDA/cuDNN versions and copy DLLs

- Your **pip** `ctranslate2` build is compiled for a specific CUDA version (e.g. 11 or 12). Use DLLs that match that version.
- From your **CUDA Toolkit** and **cuDNN** install, copy these into the same **ctranslate2** folder (names may have `_11` or `_12` and `_8` or `_9` depending on version):
  - `cublas64_11.dll` / `cublas64_12.dll`
  - `cublasLt64_11.dll` / `cublasLt64_12.dll`
  - `cudnn_ops_infer64_8.dll` (or `_9` for cuDNN 9)
  - `cudnn_cnn_infer64_8.dll` (or `_9` for cuDNN 9)
- Typical locations:
  - **CUDA:** `C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.x\bin` or `v12.x\bin`
  - **cuDNN:** after unpacking, e.g. `cuda\bin` from the cuDNN zip.

### 4. Optional: set CUDA path

If CUDA is installed in a non-default path, set:

```text
CUDA_PATH=C:\Program Files\NVIDIA GPU Computing Toolkit\CUDA\v11.8
```

(or your actual path). The script adds `CUDA_PATH\bin` to the DLL search path on Windows.

---

## Enabling GPU and tuning (after Tier 1)

- **Use GPU:**  
  ```text
  set ASR_DEVICE=cuda
  ```
- **Compute type (Tier 2):**
  - Default with `ASR_DEVICE=cuda` is **int8_float16** (stable on many GPUs, including Pascal).
  - If it still crashes, try:
    ```text
    set ASR_COMPUTE=float32
    ```
  - Only use `float16` if you have a recent GPU (e.g. RTX) and working drivers:
    ```text
    set ASR_COMPUTE=float16
    ```
- **If crash happens around 28–30 seconds (first chunk):**
  - Disable VAD:
    ```text
    set ASR_VAD_FILTER=0
    ```
  - Reduce beam size to lower memory use:
    ```text
    set ASR_BEAM_SIZE=3
    ```

---

## Quick reference: environment variables

| Variable           | Default (GPU)   | Description |
|--------------------|-----------------|-------------|
| `ASR_DEVICE`       | `cpu`           | `cuda` = use GPU (fallback to CPU on failure). |
| `ASR_COMPUTE`      | `int8_float16` (cuda) / `int8` (cpu) | `float32`, `float16`, `int8_float16`, `int8`. |
| `ASR_VAD_FILTER`   | `1`             | `0` = disable VAD (can help if crash at ~30s). |
| `ASR_BEAM_SIZE`    | `5`             | Try `3` or `4` if GPU runs out of memory. |
| `ASR_MODEL`        | `small`         | Model size (e.g. `base`, `small`, `medium`). |
| `CUDA_PATH`        | (optional)      | CUDA install path; script adds `bin` to DLL path. |

---

## Summary

- **Code (Tier 2 & 3):** DLL search path, default GPU compute `int8_float16`, optional VAD off and smaller beam size.
- **You (Tier 1):** Copy **zlibwapi.dll** and matching **CUDA/cuDNN** DLLs into `asr\venv\Lib\site-packages\ctranslate2\`, then run with `ASR_DEVICE=cuda`. If it still crashes, try `ASR_COMPUTE=float32` and `ASR_VAD_FILTER=0`.
