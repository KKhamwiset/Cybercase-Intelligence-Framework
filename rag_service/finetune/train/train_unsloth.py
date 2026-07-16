"""
LoRA Trainer — Qwen → MITRE ATT&CK specialist
=============================================
Run this on a Cloud GPU (Kaggle / Colab T4/P100 16 GB or better). It does NOT fit
on the 4 GB RTX 2050 dev box.

Current default (ft_config.py): Qwen3.5-4B with **16-bit LoRA** (Qwen3.5 must NOT
be 4-bit QLoRA'd — Unsloth: quant error too high). The 4-bit/full-FT/thinking
behaviour is all driven by ft_config flags, so the same script also trains the
legacy Qwen2.5-7B (4-bit QLoRA).

Pipeline:
  1. Load the base (16-bit LoRA / 4-bit QLoRA / full-FT per ft_config) via Unsloth
  2. Attach a LoRA adapter (skipped when FULL_FINETUNING)
  3. SFT on data/output/train.jsonl (chat format, thinking disabled), masking the
     prompt so loss is computed on assistant tokens only
  4. Save the LoRA adapter (+ optional GGUF for Ollama)

Usage (on the GPU box, from the finetune/ directory):
    pip install --upgrade --force-reinstall --no-cache-dir unsloth unsloth_zoo
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
            "Install on a GPU box. Qwen3.5 needs transformers v5 + a recent unsloth:\n"
            "  pip install --upgrade --force-reinstall --no-cache-dir unsloth unsloth_zoo\n"
            "(Qwen2.5 path: pip install -r requirements.txt)"
        )

    full_ft = getattr(C, "FULL_FINETUNING", False)

    # ── 1. Model + tokenizer ─────────────────────────────────────────────────
    mode = "4-bit QLoRA" if C.LOAD_IN_4BIT else ("FULL 16-bit" if full_ft
                                                 else "16-bit LoRA")
    print(f"[TRAIN] Loading {args.base_model} ({mode}) ...")
    load_kwargs = dict(
        model_name=args.base_model,
        max_seq_length=C.MAX_SEQ_LEN,
        load_in_4bit=C.LOAD_IN_4BIT,
        dtype=None,                       # auto: bf16 where supported, else fp16 (T4)
    )
    # These kwargs exist on the recent unsloth required for Qwen3.5; older unsloth
    # (Qwen2.5 path) doesn't know them, so fall back gracefully.
    if not C.LOAD_IN_4BIT:
        load_kwargs["load_in_16bit"] = getattr(C, "LOAD_IN_16BIT", True)
    if full_ft:
        load_kwargs["full_finetuning"] = True
    try:
        model, tokenizer = FastLanguageModel.from_pretrained(**load_kwargs)
    except TypeError:
        for k in ("load_in_16bit", "full_finetuning"):
            load_kwargs.pop(k, None)
        model, tokenizer = FastLanguageModel.from_pretrained(**load_kwargs)

    # ── 2. LoRA adapter (skipped for a full fine-tune) ───────────────────────
    if not full_ft:
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

    # ── 3. Data — apply the base model's chat template ───────────────────────
    data_files = {"train": args.train_file}
    if Path(args.val_file).exists():
        data_files["validation"] = args.val_file
    ds = load_dataset("json", data_files=data_files)

    # Qwen3.5 is a thinking model — render with thinking disabled so the training
    # text matches our direct-answer data (no <think> blocks). Probe once because
    # the Qwen2.5 template doesn't accept the kwarg.
    tmpl_kwargs = {"tokenize": False, "add_generation_prompt": False}
    want_thinking = getattr(C, "ENABLE_THINKING", None)
    if want_thinking is not None:
        try:
            tokenizer.apply_chat_template(
                ds["train"][0]["messages"], enable_thinking=want_thinking, **tmpl_kwargs
            )
            tmpl_kwargs["enable_thinking"] = want_thinking
            print(f"[TRAIN] chat template: enable_thinking={want_thinking}")
        except TypeError:
            print("[TRAIN] base chat template ignores enable_thinking (Qwen2.5)")

    def to_text(ex):
        return {"text": tokenizer.apply_chat_template(ex["messages"], **tmpl_kwargs)}

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

    # Compute loss on assistant responses only (mask the prompt). Qwen2.5, Qwen3
    # and Qwen3.5 all use ChatML, so these <|im_start|> markers are shared.
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
        print(f"        ollama create {C.FT_MODEL_OLLAMA} -f export/Modelfile.qwen35")


if __name__ == "__main__":
    main()
