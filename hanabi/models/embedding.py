"""Semantic similarity helpers by embeddings."""

from __future__ import annotations

from functools import lru_cache
from itertools import islice
from typing import Iterable, Iterator, List, Sequence

import logging

try:  # Import optional dependencies lazily so we can emit friendly errors.
    import torch  # type: ignore[import]
    from transformers import AutoModel, AutoTokenizer  # type: ignore[import]
except ImportError as exc:  # pragma: no cover - depends on optional deps.
    raise ImportError(
        "Embedding utilities require `torch` and `transformers`. "
        "Install them with `pip install torch transformers`."
    ) from exc

LOGGER = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "BAAI/bge-m3"
DEFAULT_BATCH_SIZE = 16
DEFAULT_MAX_LENGTH = 256
DEFAULT_THRESHOLD = 0.80


def _batch_iterator(items: Sequence[str], batch_size: int) -> Iterator[List[str]]:
    iterator = iter(items)
    while True:
        chunk = list(islice(iterator, batch_size))
        if not chunk:
            break
        yield chunk


def _mean_pool(last_hidden_state: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
    mask = attention_mask.unsqueeze(-1).type_as(last_hidden_state)
    masked_state = last_hidden_state * mask
    summed = masked_state.sum(dim=1)
    counts = mask.sum(dim=1).clamp(min=1e-9)
    return summed / counts


class _EmbeddingBackend:
    """Thin wrapper around a HF model/tokenizer pair."""

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL_NAME,
        *,
        device: str | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        max_length: int = DEFAULT_MAX_LENGTH,
        use_fp16: bool = True,
    ) -> None:
        resolved_device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self._device = torch.device(resolved_device)
        self._batch_size = batch_size
        self._max_length = max_length

        LOGGER.debug("Loading tokenizer and model for %s on %s", model_name, self._device)
        self._tokenizer = AutoTokenizer.from_pretrained(model_name)
        self._model = AutoModel.from_pretrained(model_name)

        if use_fp16 and self._device.type == "cuda":
            self._model = self._model.half()

        self._model.to(self._device)
        self._model.eval()

    def encode(self, texts: Sequence[str]) -> torch.Tensor:
        if not texts:
            raise ValueError("No texts provided for encoding.")

        normalized: List[str] = [text.strip() for text in texts if text and text.strip()]
        if not normalized:
            raise ValueError("All texts were empty after stripping whitespace.")

        embeddings: List[torch.Tensor] = []
        with torch.inference_mode():
            for batch in _batch_iterator(normalized, self._batch_size):
                tokens = self._tokenizer(
                    batch,
                    padding=True,
                    truncation=True,
                    max_length=self._max_length,
                    return_tensors="pt",
                )
                tokens = {key: value.to(self._device) for key, value in tokens.items()}
                outputs = self._model(**tokens)
                pooled = _mean_pool(outputs.last_hidden_state, tokens["attention_mask"])
                normalized_batch = torch.nn.functional.normalize(pooled, p=2, dim=1)
                embeddings.append(normalized_batch.cpu())

        return torch.cat(embeddings, dim=0)


@lru_cache(maxsize=1)
def _get_backend(
    model_name: str = DEFAULT_MODEL_NAME,
    *,
    device: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_length: int = DEFAULT_MAX_LENGTH,
    use_fp16: bool = True,
) -> _EmbeddingBackend:
    return _EmbeddingBackend(
        model_name=model_name,
        device=device,
        batch_size=batch_size,
        max_length=max_length,
        use_fp16=use_fp16,
    )


def has_semantic_match(
    query: str,
    candidates: Iterable[str],
    *,
    threshold: float = DEFAULT_THRESHOLD,
    model_name: str = DEFAULT_MODEL_NAME,
    device: str | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_length: int = DEFAULT_MAX_LENGTH,
    use_fp16: bool = True,
) -> bool:
    """Return ``True`` if ``query`` is semantically close to any candidate."""

    query_text = query.strip()
    if not query_text:
        return False

    cleaned_candidates = [candidate.strip() for candidate in candidates if candidate and candidate.strip()]
    if not cleaned_candidates:
        LOGGER.debug("No valid candidates passed to has_semantic_match.")
        return False

    backend = _get_backend(
        model_name=model_name,
        device=device,
        batch_size=batch_size,
        max_length=max_length,
        use_fp16=use_fp16,
    )

    query_embedding = backend.encode([query_text])[0]
    candidate_embeddings = backend.encode(cleaned_candidates)

    scores = candidate_embeddings @ query_embedding
    max_score = float(scores.max().item())
    LOGGER.debug("Max cosine similarity for semantic match: %.4f", max_score)

    return max_score >= threshold


__all__ = ["has_semantic_match"]
