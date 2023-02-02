from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Extra, root_validator

from langchain.embeddings.base import Embeddings
from langchain.utils import get_from_dict_or_env
from sentence_transformers import SentenceTransformer
import torch
import numpy as np

EMBEDDING_CACHE={}
class TorchEmbeddings( Embeddings):

    models={}
    def __init__(self, device):
        self.torch_device='cuda' if (device=="cuda" or device=="gpu") and torch.cuda.is_available() else 'cpu'
        if not self.torch_device in TorchEmbeddings.models:
            TorchEmbeddings.models[self.torch_device]=SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2',device=self.torch_device)    
        self.model=TorchEmbeddings.models[self.torch_device]
   

    def _embedding_func(self, text: str, *, engine: str) -> List[float]:
        cache=EMBEDDING_CACHE
        # prevent cache from growing too big
        if len(cache)>1000:
            cache={}

        if text in cache :
            return cache[text]
        else:
            embeddings = self.model.encode([text],device=self.torch_device)
            embeddings=embeddings.copy().astype(np.float32)
            embeddings = embeddings[0]
            cache[text]=embeddings
            return embeddings

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        responses = [
            self._embedding_func(text, engine=self.torch_device)
            for text in texts
        ]
        return responses

    def embed_query(self, text: str) -> List[float]:
        embedding = self._embedding_func(text, engine=self.torch_device)
        return embedding
