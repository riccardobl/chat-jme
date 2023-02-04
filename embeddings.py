from langchain.vectorstores.faiss import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from ratelimit import limits,sleep_and_retry
import pickle
from langchain.docstore.document import Document
import numpy as np
import time
from langchain.text_splitter import CharacterTextSplitter
from TorchEmbeddings import TorchEmbeddings
import utils
import gc
from OpenAICachedEmbeddings import OpenAICachedEmbeddings
import faiss
import copy

# Group 0 = cache and gpu
# Group 1 = not cache, gpu
# Group -1 = not cache, not gpu
# Group 2 = cache, not gpu
class EmbeddingsManager:
    CONFIG=None
    LOAD_CACHE=None
    GPU_CACHE=None
    GPU_RESOURCES=None
    GROUP_GPU_CACHE=0
    GROUP_GPU=1
    GROUP_CPU=-1
    GROUP_CPU_CACHE=2

    @staticmethod
    def _withCache(group):
        if not EmbeddingsManager.CONFIG.get("CACHE_EMBEDDINGS",True):
            return False            
        return group==EmbeddingsManager.GROUP_GPU_CACHE or group==EmbeddingsManager.GROUP_CPU_CACHE

    @staticmethod
    def _withGpu(group):
        return group==EmbeddingsManager.GROUP_GPU or group==EmbeddingsManager.GROUP_GPU_CACHE

    @staticmethod
    def init(CONFIG):
        EmbeddingsManager.CONFIG=CONFIG
        EmbeddingsManager.preload()
        EmbeddingsManager.LOAD_CACHE={}
        EmbeddingsManager.GPU_CACHE={}
        EmbeddingsManager.GPU_RESOURCES=None
        useGpu=EmbeddingsManager.CONFIG["DEVICE"]=="cuda" or EmbeddingsManager.CONFIG["DEVICE"]=="gpu"
        if useGpu:
            EmbeddingsManager.GPU_RESOURCES=faiss.StandardGpuResources()

    @staticmethod
    def _toDevice(f,group=0):
        if EmbeddingsManager.GPU_RESOURCES==None or not EmbeddingsManager._withGpu(group):
            return f
        else:
            if not group in EmbeddingsManager.GPU_CACHE:
                EmbeddingsManager.GPU_CACHE[group]={}
            cache=EmbeddingsManager.GPU_CACHE[group]
            if hash(f) in cache:
                return cache[hash(f)]
            else:
                gpuIndex=copy.copy(f)
                internalIndex=gpuIndex.index
                internalIndexToGpu=faiss.index_cpu_to_gpu(EmbeddingsManager.GPU_RESOURCES,0,internalIndex)
                gpuIndex.index=internalIndexToGpu
                #gpuIndex=faiss.index_cpu_to_gpu(EmbeddingsManager.GPU_RESOURCES,0,f)
                if EmbeddingsManager._withCache(group):
                    cache[hash(f)]=gpuIndex
                return gpuIndex




    @staticmethod
    def preload():
        TorchEmbeddings("cpu").preload()
   
    @staticmethod
    def new(doc,backend="openai"):
        if backend=="cpu" or backend=="gpu" or backend=="cuda":
            return EmbeddingsManager._newTorch(doc,backend)
        else: # backend==openai
            return EmbeddingsManager._newOpenAI(doc)

    @staticmethod
    def _newTorch(doc,backend):
        source_chunks = []
        splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )
        for chunk in splitter.split_text(doc.page_content):
            source_chunks.append(Document(page_content=chunk, metadata=doc.metadata))          
        try:
            l=40
            source_chunks = [source_chunks[i:i + l] for i in range(0, len(source_chunks), l)]
            print("Processing", len(source_chunks),"chunks")               
            print("Create index with",len(source_chunks[0]),"tokens")
            faiss=FAISS.from_documents(source_chunks[0], TorchEmbeddings(backend))
            if faiss==None:
                raise Exception("Error creating index")
            if len(source_chunks)>1:
                for i in range(1,len(source_chunks)):
                    documents=source_chunks[i]
                    print("Add",len(documents),"tokens")
                    texts = [d.page_content for d in documents]
                    metadatas = [d.metadata for d in documents]
                    faiss.add_texts(texts,metadatas)       
            return faiss                 
        except Exception as e:
            print(e)


    @staticmethod
    def _newOpenAI(doc):
        source_chunks = []

        splitter = CharacterTextSplitter(
            separator="\n",
            chunk_size=1000,
            chunk_overlap=200,
            length_function=len,
        )

        for chunk in splitter.split_text(doc.page_content):
            source_chunks.append(Document(page_content=chunk, metadata=doc.metadata))
        
        try:
            l=40
            source_chunks = [source_chunks[i:i + l] for i in range(0, len(source_chunks), l)]
            print("Processing", len(source_chunks),"chunks")               
            print("Create index with",len(source_chunks[0]),"tokens")
            faiss=utils.retry(lambda: FAISS.from_documents(source_chunks[0], OpenAICachedEmbeddings()))
            if faiss==None:
                raise Exception("Error creating index")
            if len(source_chunks)>1:
                for i in range(1,len(source_chunks)):
                    documents=source_chunks[i]
                    print("Add",len(documents),"tokens")
                    texts = [d.page_content for d in documents]
                    metadatas = [d.metadata for d in documents]
                    utils.retry(lambda: faiss.add_texts(texts,metadatas))       
            return faiss                 
        except Exception as e:
            print("Error creating index. Retry ", e)

     
 

    @staticmethod
    def embedding_function(index, query):
        if index.embedding_function.__qualname__.startswith("OpenAIEmbeddings."): # Migrate to cached embeddings
            index.embedding_function=OpenAICachedEmbeddings().embed_query
        return utils.retry(lambda:index.embedding_function(query))
  
    @staticmethod
    def write(path,embed):
        if embed==None:
            raise Exception("Can't write None")
        with open(path, 'wb') as f:      
            pickle.dump(embed, f)

    @staticmethod
    def read(path, group=0):
        if path in EmbeddingsManager.LOAD_CACHE:
            return EmbeddingsManager.LOAD_CACHE[path]
        with open(path, 'rb') as f:
            print("Loading from disk",path,"...")
            out = pickle.load(f)
            if EmbeddingsManager._withCache(group):
                EmbeddingsManager.LOAD_CACHE[path]=out
            if out==None:
                raise Exception("Error loading index")
            return out

    @staticmethod
    def queryIndex(index,query,k=4, cache=None, group=0):
        embedding=None
        if cache!=None and query in cache:
            embedding=cache[query]
        else:
            embedding =  EmbeddingsManager.embedding_function(index, query)
            if cache!=None:
                cache[query]=embedding
        # embedding=None

        # print(index.embedding_function.__class__.__name__)
        # backend=hash(index.embedding_function)
        
        # if not backend in EmbeddingsManager.cache:
        #     EmbeddingsManager.cache[backend]={}
        
        # cache=EmbeddingsManager.cache[backend]
        # # prevent cache from growing too big
        # if len(cache)>1000:
        #     cache={}

        # if query in cache :
        #     print("Cached")
        #     embedding=cache[query]
        # else:
        #     #embedding=index.embedding_function(query)
        #     embedding=EmbeddingsManager.embedding_function(index, query)
        #     cache[query]=embedding
        
        index=EmbeddingsManager._toDevice(index,group)
        scores, indices = index.index.search(np.array([embedding], dtype=np.float32), k=k)
        docs = []
        for j, i in enumerate(indices[0]):
            if i == -1:
                # This happens when not enough docs are returned.
                continue
            _id = index.index_to_docstore_id[i]
            doc = index.docstore.search(_id)
            if not isinstance(doc, Document):
                raise ValueError(f"Could not find document for id {_id}, got {doc}")
            docs.append((doc, scores[0][j]))
        return docs

    def query(indices, query, n=3, k=4,cache=None,group=0):
        results=[]
        if cache==None: 
            cache={}
        i=0
        print("Searching",len(indices),"embeddings...")
        for index in indices:
            res=EmbeddingsManager.queryIndex(index,query, k=k, cache=cache,group=group),
            for res2 in res:
                for rdoc in res2:
                    score=rdoc[1]
                    results.append({
                        "doc": rdoc[0],
                        "score": score
                    })       
      
            i+=1
            if i>=100:
                i=0
                gc.collect() 
        best= sorted(results, key=lambda x: x["score"], reverse=False)[:n]
        #best[::-1]   
        
        cache.clear()        



        gc.collect()
        gc.collect()
        return [ x["doc"] for x in best]
