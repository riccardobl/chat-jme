from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Extra, root_validator

from langchain.embeddings.base import Embeddings
from langchain.utils import get_from_dict_or_env
from sentence_transformers import SentenceTransformer
import torch
import numpy as np
import threading
EMBEDDING_CACHE={}
class TorchEmbeddings( Embeddings):
    @staticmethod
    def preload(device):
        isGpuDevice=device=="cuda" or device=="gpu"
        if isGpuDevice and  not torch.cuda.is_available():
            print("WARNING: GPU device requested but not available")
        print("Preloading MiniLM L6 v2")
        parallel=1
        TorchEmbeddings.torch_device='cuda' if isGpuDevice and torch.cuda.is_available() else 'cpu'
        TorchEmbeddings.models=[
            SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2',device=TorchEmbeddings.torch_device)
            for i in range(0,parallel)
        ]

        print("Done")

    torch_device=0
    models=[]
    modelI=0
    modelLock=threading.Lock()
    model=None
    def __init__(self, device):
        self.torch_device=TorchEmbeddings.torch_device
        self.model=None
        with TorchEmbeddings.modelLock:
            self.model=TorchEmbeddings.models[TorchEmbeddings.modelI]
            TorchEmbeddings.modelI+=1
            if TorchEmbeddings.modelI>=len(TorchEmbeddings.models): 
                TorchEmbeddings.modelI=0


        # self.torch_device='cuda' if isGpuDevice and torch.cuda.is_available() else 'cpu'
        # if not self.torch_device in TorchEmbeddings.models:
        #     TorchEmbeddings.models[self.torch_device]=SentenceTransformer('sentence-transformers/paraphrase-MiniLM-L6-v2',device=self.torch_device)    
        
   

    def _embedding_func(self, text: str, *, engine: str) -> List[float]:
        useCache=False #len(text)<200

        cache=EMBEDDING_CACHE
        # prevent cache from growing too big
        if len(cache)>100:
            cache={}

        if useCache and text in cache  :
            return cache[text]
        else:
            embeddings = self.model.encode([text],device=self.torch_device,show_progress_bar=True)
            embeddings=embeddings.copy().astype(np.float32)
            embeddings = embeddings[0]
            if useCache : cache[text]=embeddings
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
