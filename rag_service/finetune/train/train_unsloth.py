"""
QLoRA Trainer — Qwen2.5-7B → MITRE ATT&CK specialist
====================================================
Run this on a Cloud GPU (Colab / Kaggle T4 16 GB or better). It does NOT fit on
the 4 GB RTX 2050 dev box.

Pipeline:
  1. Load Qwen2.5-7B-Instruct in 4-bit (Unsloth)
  2. Attach a LoRA adapter
  3. SFT on data/output/train.jsonl (chat format), masking the prompt so loss is
     computed on assistant tokens only
  4. Save the LoRA adapter (+ optional GGUF for Ollama)

Usage (on the GPU box, from the finetune/ directory):
    pip install -r requirements.txt        # or the Colab one-liner (see file)
    python train/train_unsloth.py                       # full run
    python train/train_unsloth.py --max-steps 5         # smoke test the loop
    python train/train_unsloth.py --gguf                # also export GGUF Q4_K_M

All hyper-parameters live in ft_config.py.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # finetune/
import ft_config as C  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="QLoRA fine-tune Qwen2.5-7B for MITRE")
    ap.add_argument("--base-model", default=C.BASE_MODEL_HF)
    ap.add_argument("--train-file", default=str(C.TRAIN_FILE))
    ap.add_argument("--val-file", default=str(C.VAL_FILE))
    ap.add_argument("--out-dir", default=str(C.ADAPTER_DIR))
    ap.add_argument("--epochs", type=float, default=C.NUM_EPOCHS)
    ap.add_argument("--max-steps", type=int, default=-1,
                    help="cap training steps (use 5 for a quick smoke test)")
    ap.add_argument("--gguf", action="store_true",
                    help="also export a GGUF (Q4_K_M) for Ollama after training")
    args = ap.parse_args()

    # Imported here so `--help` works without the heavy GPU stack installed.
    try:
        import torch
        from unsloth import FastLanguageModel
        from unsloth.chat_templates import train_on_responses_only
        from datasets import load_dataset
        from trl import SFTConfig, SFTTrainer
    except ImportError as e:  # pragma: no cover - environment guard
        sys.exit(
            f"[FATAL] Missing training dependency: {e}\n"
            "Install on a GPU box: pip install -r requirements.txt\n"
            "(Colab: pip install 'unsloth[colab-new] @ "
            "git+https://github.com/unslothai/unsloth.git')"
        )

    # ── 1. Model + tokenizer (4-bit) ─────────────────────────────────────────
    print(f"[TRAIN] Loading {args.base_model} in 4-bit ...")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=args.base_model,
        max_seq_length=C.MAX_SEQ_LEN,
        load_in_4bit=C.LOAD_IN_4BIT,
        dtype=None,                       # auto (bf16/fp16)
    )

    # ── 2. LoRA adapter ──────────────────────────────────────────────────────
    model = FastLanguageModel.get_peft_model(
        model,
        r=C.LORA_R,
        target_modules=C.LORA_TARGET_MODULES,
        lora_alpha=C.LORA_ALPHA,
        lora_dropout=C.LORA_DROPOUT,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=C.RANDOM_SEED,
    )

    # ── 3. Data — apply Qwen2.5 chat template ────────────────────────────────
    data_files = {"train": args.train_file}
    if Path(args.val_file).exists():
        data_files["validation"] = args.val_file
    ds = load_dataset("json", data_files=data_files)

    def to_text(ex):
        return {
            "text": tokenizer.apply_chat_template(
                ex["messages"], tokenize=False, add_generation_prompt=False
            )
        }

    ds = ds.map(to_text, remove_columns=ds["train"].column_names)

    # ── 4. Trainer ───────────────────────────────────────────────────────────
    sft_args = SFTConfig(
        per_device_train_batch_size=C.PER_DEVICE_BATCH,
        gradient_accumulation_steps=C.GRAD_ACCUM,
        warmup_ratio=C.WARMUP_RATIO,
        num_train_epochs=args.epochs,
        max_steps=args.max_steps,
        learning_rate=C.LEARNING_RATE,
        fp16=not torch.cuda.is_bf16_supported(),
        bf16=torch.cuda.is_bf16_supported(),
        logging_steps=C.LOGGING_STEPS,
        weight_decay=C.WEIGHT_DECAY,
        lr_scheduler_type=C.LR_SCHEDULER,
        optim="adamw_8bit",
        seed=C.RANDOM_SEED,
        output_dir=str(Path(args.out_dir) / "checkpoints"),
        dataset_text_field="text",
        max_seq_length=C.MAX_SEQ_LEN,
        report_to="none",
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=ds["train"],
        eval_dataset=ds.get("validation"),
        args=sft_args,
    )

    # Compute loss on assistant responses only (mask the prompt) — Qwen2.5 ChatML.
    trainer = train_on_responses_only(
        trainer,
        instruction_part="<|im_start|>user\n",
        response_part="<|im_start|>assistant\n",
    )

    print("[TRAIN] Starting ...")
    trainer.train()

    # ── 5. Save adapter ──────────────────────────────────────────────────────
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(out))
    tokenizer.save_pretrained(str(out))
    print(f"[TRAIN] LoRA adapter saved -> {out}")

    # ── 6. Optional GGUF export (simplest path to Ollama) ────────────────────
    if args.gguf:
        gguf_dir = C.GGUF_DIR
        gguf_dir.mkdir(parents=True, exist_ok=True)
        print(f"[TRAIN] Exporting GGUF ({C.GGUF_QUANT}) -> {gguf_dir}")
        model.save_pretrained_gguf(
            str(gguf_dir), tokenizer, quantization_method=C.GGUF_QUANT.lower()
        )
        print("[TRAIN] GGUF export done. Download the .gguf and run:")
        print(f"        ollama create {C.FT_MODEL_OLLAMA} -f export/Modelfile")


if __name__ == "__main__":
    main()
