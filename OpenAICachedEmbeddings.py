"""Wrapper around OpenAI embedding models."""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Extra, root_validator

from langchain.embeddings.base import Embeddings
from langchain.utils import get_from_dict_or_env

from langchain.embeddings.openai import OpenAIEmbeddings

  
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Extra, root_validator

from langchain.embeddings.base import Embeddings
from langchain.utils import get_from_dict_or_env
import hashlib
import os,pickle,time
class OpenAICachedEmbeddings(BaseModel, Embeddings):
    

    """Wrapper around OpenAI embedding models.

    To use, you should have the ``openai`` python package installed, and the
    environment variable ``OPENAI_API_KEY`` set with your API key or pass it
    as a named parameter to the constructor.

    Example:
        .. code-block:: python

            from langchain.embeddings import OpenAIEmbeddings
            openai = OpenAIEmbeddings(openai_api_key="my-api-key")
    """

    client: Any  #: :meta private:
    document_model_name: str = "text-embedding-ada-002"
    query_model_name: str = "text-embedding-ada-002"
    openai_api_key: Optional[str] = None
    cachePath:Optional[str] = None

    class Config:
        """Configuration for this pydantic object."""

        extra = Extra.forbid

    # TODO: deprecate this
    @root_validator(pre=True)
    def get_model_names(cls, values: Dict) -> Dict:
        """Get model names from just old model name."""
        if "model_name" in values:
            if "document_model_name" in values:
                raise ValueError(
                    "Both `model_name` and `document_model_name` were provided, "
                    "but only one should be."
                )
            if "query_model_name" in values:
                raise ValueError(
                    "Both `model_name` and `query_model_name` were provided, "
                    "but only one should be."
                )
            model_name = values.pop("model_name")
            values["document_model_name"] = f"text-search-{model_name}-doc-001"
            values["query_model_name"] = f"text-search-{model_name}-query-001"
        return values

    @root_validator()
    def validate_environment(cls, values: Dict) -> Dict:
        """Validate that api key and python package exists in environment."""
        openai_api_key = get_from_dict_or_env(
            values, "openai_api_key", "OPENAI_API_KEY"
        )
        try:
            import openai

            openai.api_key = openai_api_key
            values["client"] = openai.Embedding
        except ImportError:
            raise ValueError(
                "Could not import openai python package. "
                "Please it install it with `pip install openai`."
            )
        return values
    

    def _embedding_func(self, text: str, *, engine: str) -> List[float]:
        textHash=None
        cachedFile=None
        embeddings=None
        if self.cachePath is not None:
            if not os.path.exists(self.cachePath):
                os.makedirs(self.cachePath)
            textHash=hashlib.sha256(text.encode('utf-8')).hexdigest()
            cachedFile=os.path.join(self.cachePath, textHash+".pickle")
            if os.path.exists(cachedFile):
                with open(cachedFile, 'rb') as f:
                    embeddings =  pickle.load(f)

        if embeddings is None:
            embeddings=self._embedding_func2(text, engine=engine)
            if cachedFile is not None: 
                with open(cachedFile, 'wb') as f:      
                    pickle.dump(embeddings, f)
                
                for f in os.listdir(self.cachePath):
                    if f.endswith(".pickle") and os.path.getmtime(os.path.join(self.cachePath, f)) < time.time() - 86400:
                        os.remove(os.path.join(self.cachePath, f))
        
        return embeddings

    def _embedding_func2(self, text: str, *, engine: str) -> List[float]:
        """Call out to OpenAI's embedding endpoint."""
        # replace newlines, which can negatively affect performance.
        text = text.replace("\n", " ")
        return self.client.create(input=[text], engine=engine)["data"][0]["embedding"]

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """Call out to OpenAI's embedding endpoint for embedding search docs.

        Args:
            texts: The list of texts to embed.

        Returns:
            List of embeddings, one for each text.
        """
        responses = [
            self._embedding_func(text, engine=self.document_model_name)
            for text in texts
        ]
        return responses

    def embed_query(self, text: str) -> List[float]:
        """Call out to OpenAI's embedding endpoint for embedding query text.

        Args:
            text: The text to embed.

        Returns:
            Embeddings for the text.
        """
        embedding = self._embedding_func(text, engine=self.query_model_name)
        return embedding
