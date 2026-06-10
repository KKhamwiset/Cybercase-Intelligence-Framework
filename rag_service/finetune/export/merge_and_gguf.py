"""
Merge LoRA → GGUF (fallback / non-Unsloth path)
===============================================
Use this when you trained the adapter elsewhere, or want the explicit
transformers + llama.cpp route instead of Unsloth's ``save_pretrained_gguf``.

Steps:
  1. Load base Qwen2.5-7B-Instruct + LoRA adapter, merge to fp16, save HF model
  2. Convert the merged model to GGUF and quantise to Q4_K_M via llama.cpp

Run on the GPU/cloud box (merging 7B needs ~16 GB RAM, GPU optional):
    # 1) merge only
    python export/merge_and_gguf.py --adapter train/outputs/mitre-qwen-lora

    # 2) merge + GGUF (point at a cloned/built llama.cpp)
    python export/merge_and_gguf.py \
        --adapter train/outputs/mitre-qwen-lora \
        --llama-cpp /path/to/llama.cpp
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # finetune/
import ft_config as C  # noqa: E402


def merge(base_model: str, adapter_dir: str, merged_dir: Path):
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as e:  # pragma: no cover
        sys.exit(f"[FATAL] missing dependency: {e}\n  pip install -r requirements.txt")

    print(f"[MERGE] base={base_model}  adapter={adapter_dir}")
    tokenizer = AutoTokenizer.from_pretrained(base_model)
    base = AutoModelForCausalLM.from_pretrained(
        base_model, torch_dtype=torch.float16, device_map="cpu"
    )
    model = PeftModel.from_pretrained(base, adapter_dir)
    model = model.merge_and_unload()

    merged_dir.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(merged_dir), safe_serialization=True)
    tokenizer.save_pretrained(str(merged_dir))
    print(f"[MERGE] merged fp16 model -> {merged_dir}")


def to_gguf(merged_dir: Path, llama_cpp: Path, quant: str):
    convert = llama_cpp / "convert_hf_to_gguf.py"
    if not convert.exists():
        sys.exit(f"[FATAL] {convert} not found — clone/build llama.cpp first.")

    gguf_dir = C.GGUF_DIR
    gguf_dir.mkdir(parents=True, exist_ok=True)
    f16 = gguf_dir / "mitre-qwen-7b-f16.gguf"
    out = gguf_dir / f"mitre-qwen-7b-{quant}.gguf"

    print(f"[GGUF] converting -> {f16}")
    subprocess.run(
        [sys.executable, str(convert), str(merged_dir),
         "--outfile", str(f16), "--outtype", "f16"],
        check=True,
    )

    quantize = llama_cpp / "llama-quantize"
    quantize_exe = quantize if quantize.exists() else (llama_cpp / "build" / "bin" / "llama-quantize")
    print(f"[GGUF] quantising -> {out} ({quant})")
    subprocess.run([str(quantize_exe), str(f16), str(out), quant], check=True)
    print(f"[GGUF] done -> {out}")
    print(f"[GGUF] now run:  ollama create {C.FT_MODEL_OLLAMA} -f export/Modelfile")
    print(f"        (set Modelfile FROM to: {out})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-model", default=C.BASE_MODEL_HF)
    ap.add_argument("--adapter", default=str(C.ADAPTER_DIR))
    ap.add_argument("--merged-dir", default=str(C.MERGED_DIR))
    ap.add_argument("--llama-cpp", default="", help="path to a built llama.cpp repo")
    ap.add_argument("--quant", default=C.GGUF_QUANT)
    args = ap.parse_args()

    merged_dir = Path(args.merged_dir)
    merge(args.base_model, args.adapter, merged_dir)

    if args.llama_cpp:
        to_gguf(merged_dir, Path(args.llama_cpp), args.quant)
    else:
        print("\n[NEXT] merged model ready. To make a GGUF, re-run with "
              "--llama-cpp /path/to/llama.cpp, or use Unsloth's --gguf export.")


if __name__ == "__main__":
    main()
