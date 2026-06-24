"""向量化 -- BGE-large-zh-v1.5 中文检索专用模型.

模型: BAAI/bge-large-zh-v1.5
维度: 768
MTEB 中文检索榜首,首次加载自动下载 ~1.3GB.

下载策略:
  1. 本地缓存 (MODELSCOPE_CACHE / HF_HOME) → 直接加载
  2. ModelScope (国内满速) → HF 直连 → 自动回退
"""

from __future__ import annotations

import logging
import os
import threading

from sentence_transformers import SentenceTransformer

logger = logging.getLogger(__name__)

# ModelScope 上的模型 ID(与 HF 相同)
MODELSCOPE_MODEL_ID = "BAAI/bge-large-zh-v1.5"
DEFAULT_MODEL_ID = "BAAI/bge-large-zh-v1.5"


def _find_local_cache(model_id: str, cache_dir: str) -> str | None:
    """在 ModelScope 本地缓存中查找模型,不需导入 modelscope.

    ModelScope 缓存目录命名规则:把 model_id 中的 / → os.sep,. → ___.
    例如 "BAAI/bge-large-zh-v1.5" → "BAAI/bge-large-zh-v1___5".
    检查目录下是否存在 pytorch_model.bin 或 model.safetensors.
    """
    ns, name = model_id.split("/", 1)
    dir_name = name.replace(".", "___")
    local = os.path.join(cache_dir, ns, dir_name)
    if os.path.isdir(local) and (
        os.path.isfile(os.path.join(local, "pytorch_model.bin"))
        or os.path.isfile(os.path.join(local, "model.safetensors"))
    ):
        logger.info("Found local cache: %s", local)
        return local
    return None


def _download_via_modelscope(model_id: str, cache_dir: str) -> str | None:
    """从 ModelScope 下载模型到本地,返回本地路径;失败返回 None."""
    try:
        from modelscope.hub.snapshot_download import snapshot_download
    except ImportError:
        logger.info("modelscope not installed, skip")
        return None

    logger.info("Downloading from ModelScope: %s", model_id)
    try:
        local_path = snapshot_download(model_id, cache_dir=cache_dir)
        logger.info("ModelScope download done: %s", local_path)
        return local_path
    except Exception as e:
        logger.warning("ModelScope download failed: %s", e)
        return None


class Embedder:
    """BGE 中文检索 Embedding 封装.

    Usage:
        emb = Embedder()                          # 自动选择最优下载源
        emb = Embedder(use_modelscope=False)      # 强制走 HF
        vec = emb.embed_query("年假还剩几天")
        vecs = emb.embed_documents(["文本1", "文本2"])
    """

    def __init__(
        self,
        model_id: str = DEFAULT_MODEL_ID,
        cache_dir: str | None = None,
        use_modelscope: bool = True,
    ) -> None:
        self.model_id = model_id
        self.cache_dir = cache_dir or os.path.join(
            os.path.expanduser("~"), ".cache", "modelscope", "hub"
        )
        self._use_modelscope = use_modelscope
        self._model: SentenceTransformer | None = None
        self._model_lock = threading.Lock()

    @property
    def model(self) -> SentenceTransformer:
        if self._model is None:
            with self._model_lock:
                # 双重检查:拿到锁后再次确认未被其他线程初始化
                if self._model is None:
                    model_path: str = self.model_id

                    if self._use_modelscope:
                        # 1) 本地缓存(不需要 modelscope 包)
                        local = _find_local_cache(self.model_id, self.cache_dir)
                        if local is not None:
                            model_path = local
                        else:
                            # 2) 通过 ModelScope API 下载
                            local = _download_via_modelscope(self.model_id, self.cache_dir)
                            if local is not None:
                                model_path = local

                    logger.info("Loading embedding model from: %s", model_path)
                    self._model = SentenceTransformer(model_path)
                    logger.info("Model loaded, dimension=%d", self.dimension)
        return self._model

    def embed_query(self, text: str) -> list[float]:
        """对单条 query 进行向量化.

        BGE 模型要求 query 加前缀 "为这个句子生成表示以用于检索相关文章:".
        """
        return self.model.encode(
            text,
            prompt="为这个句子生成表示以用于检索相关文章:",
            normalize_embeddings=True,
        ).tolist()

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """批量向量化(文档不需要加 query 前缀)."""
        return self.model.encode(
            texts,
            normalize_embeddings=True,
        ).tolist()

    @property
    def dimension(self) -> int:
        """向量维度."""
        return 1024
