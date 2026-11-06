"""CPU-only NLI inference service. Returns raw entailment scores, not decisions."""

import logging
import os
import threading
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort
from fastapi import FastAPI, HTTPException
from huggingface_hub import list_repo_files, snapshot_download
from pydantic import BaseModel, Field
from transformers import AutoConfig, AutoTokenizer

logger = logging.getLogger("horizon")
logging.basicConfig(level=logging.INFO)

MODEL_ID = os.getenv("MODEL_ID", "Horizon-Labs/multilingual-zeroshot-small")
MODEL_REVISION = os.getenv("MODEL_REVISION", "main")
MODEL_ONNX_FILE = os.getenv("MODEL_ONNX_FILE", "auto")
MAX_INPUT_TOKENS = int(os.getenv("MAX_INPUT_TOKENS", "1024"))
ORT_THREADS = int(os.getenv("ORT_INTRA_OP_THREADS", "2"))
CONTRACT = "horizon-nli-v1"

_session: ort.InferenceSession | None = None
_tokenizer: Any = None
_entailment_index: int | None = None
_not_entailment_index: int | None = None
_model_file: str | None = None
_lock = threading.Lock()


def pick_onnx_file(paths: list[str]) -> str:
    options = sorted(p for p in paths if p.startswith("onnx/") and p.endswith(".onnx"))
    if not options:
        options = sorted(p for p in paths if p.endswith(".onnx"))
    if not options:
        raise RuntimeError("No ONNX model found in repository")
    if MODEL_ONNX_FILE != "auto":
        if MODEL_ONNX_FILE not in options:
            raise RuntimeError(f"ONNX file {MODEL_ONNX_FILE!r} not found. Available: {options}")
        return MODEL_ONNX_FILE
    for preferred in ("onnx/model.onnx", "onnx/model_fp32.onnx", "onnx/model_quantized.onnx"):
        if preferred in options:
            return preferred
    if len(options) == 1:
        return options[0]
    raise RuntimeError(
        "Multiple ONNX variants available; choose MODEL_ONNX_FILE explicitly: "
        + ", ".join(options)
    )


def setup_model() -> None:
    global _session, _tokenizer, _entailment_index, _not_entailment_index, _model_file
    logger.info("Resolving model %s at revision %s", MODEL_ID, MODEL_REVISION)
    files = list_repo_files(MODEL_ID, revision=MODEL_REVISION)
    selected = pick_onnx_file(files)
    # Keep tokenizer/config and only selected ONNX weights to avoid fetching all variants.
    related = [
        p for p in files
        if p == selected or p in (selected + "_data", selected + ".data")
        or p in ("config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json", "added_tokens.json", "vocab.txt")
    ]
    if selected not in related:
        raise RuntimeError("Selected ONNX model missing from download manifest")
    local = Path(snapshot_download(
        repo_id=MODEL_ID,
        revision=MODEL_REVISION,
        allow_patterns=related,
    ))
    model_path = local / selected
    if not model_path.is_file():
        raise RuntimeError(f"ONNX file missing in cache: {model_path}")

    config = AutoConfig.from_pretrained(str(local), local_files_only=True)
    labelmap = {str(name).lower(): int(index) for index, name in config.id2label.items()}
    # NLI output must be validated, never guess which logit means entailment.
    entail = next((i for key, i in labelmap.items() if key == "entailment"), None)
    non_entail = next((i for key, i in labelmap.items() if key in {"not_entailment", "non_entailment"}), None)
    if entail is None or non_entail is None:
        raise RuntimeError(f"Unexpected NLI id2label mapping: {config.id2label}")

    opts = ort.SessionOptions()
    opts.intra_op_num_threads = ORT_THREADS
    opts.inter_op_num_threads = 1
    session = ort.InferenceSession(str(model_path), sess_options=opts, providers=["CPUExecutionProvider"])
    names = {node.name for node in session.get_inputs()}
    if "input_ids" not in names or "attention_mask" not in names:
        raise RuntimeError(f"Unexpected model input fields: {names}")
    tokenizer = AutoTokenizer.from_pretrained(str(local), local_files_only=True, use_fast=True)

    _session, _tokenizer = session, tokenizer
    _entailment_index, _not_entailment_index = entail, non_entail
    _model_file = selected
    logger.info("Ready: model=%s file=%s labels=%s", MODEL_ID, selected, labelmap)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_model()
    yield


app = FastAPI(title="LAEW Horizon NLI", version="0.1.0", lifespan=lifespan, docs_url=None, redoc_url=None)


class NLIRequest(BaseModel):
    premise: str = Field(min_length=1, max_length=20000)
    hypothesis: str = Field(min_length=1, max_length=4000)


@app.get("/healthz")
def healthz():
    return {"alive": True}


@app.get("/readyz")
def readyz():
    if _session is None:
        raise HTTPException(status_code=503, detail="Model not loaded")
    return {
        "ready": True,
        "contract": CONTRACT,
        "model_id": MODEL_ID,
        "revision": MODEL_REVISION,
        "onnx_file": _model_file,
        "provider": _session.get_providers()[0],
        "onnxruntime_version": ort.__version__,
        "max_input_tokens": MAX_INPUT_TOKENS,
    }


@app.post("/v1/nli")
def nli(payload: NLIRequest):
    if _session is None or _tokenizer is None or _entailment_index is None or _not_entailment_index is None:
        raise HTTPException(status_code=503, detail="Model not ready")
    start = time.perf_counter()
    # Preserve hypothesis whenever possible; if premise is too long, truncate it.
    try:
        encoded = _tokenizer(
            payload.premise,
            payload.hypothesis,
            truncation="only_first",
            max_length=MAX_INPUT_TOKENS,
            return_tensors="np",
        )
        count = int(encoded["input_ids"].shape[1])
        values = {}
        for node in _session.get_inputs():
            if node.name in encoded:
                dtype = np.int32 if node.type == "tensor(int32)" else np.int64
                values[node.name] = np.asarray(encoded[node.name], dtype=dtype)
        with _lock:
            logits = np.asarray(_session.run(None, values)[0], dtype=np.float64).reshape(-1)
        if max(_entailment_index, _not_entailment_index) >= logits.size:
            raise RuntimeError(f"Model returned {logits.size} scores; expected NLI labels")
        logits -= logits.max()
        probs = np.exp(logits)
        probs /= probs.sum()
    except Exception as exc:
        logger.exception("NLI inference failed")
        raise HTTPException(status_code=503, detail="Inference failed") from exc
    return {
        "contract": CONTRACT,
        "model_id": MODEL_ID,
        "entailment_score": float(probs[_entailment_index]),
        "not_entailment_score": float(probs[_not_entailment_index]),
        "input_tokens": count,
        "latency_ms": round((time.perf_counter() - start) * 1000, 2),
    }
