import os
from langchain.docstore.document import Document
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores.faiss import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.llms import OpenAI
import pickle
from ingest import website, wiki,source
from ratelimit import limits,sleep_and_retry
from embeddings import Embeddings
import json
class IndexBuilder :
    def __init__(self, options):
        self.options = options

    def updateIndex(self):
        docs=[]
        rootPath = os.path.join("embeddings",self.options["unit"] if "unit" in self.options else "root")
        if not os.path.exists(rootPath):
            os.makedirs(rootPath)
        infoPath = os.path.join(rootPath,"info.json")
        optionsJson=json.dumps(self.options)
        with open(infoPath,"w",encoding="utf-8") as f:
            f.write(optionsJson)
        for doc in self:
            docs.append(doc)
            self._updateIndex(rootPath,doc)
        return docs

        



    def _updateIndex(self,rootPath,doc):    
        try:

            # Migrate old index
            embedPath = os.path.join("index/", doc.metadata["hash"] + ".bin")
            if os.path.exists(embedPath):
                os.rename(embedPath, os.path.join(rootPath, doc.metadata["hash"] + ".bin"))
                print("Migrated", doc.metadata["source"])
                return
            

            embedPath = os.path.join(rootPath, doc.metadata["hash"] + ".bin")
            if os.path.exists(embedPath):
                print("Already processed", doc.metadata["source"])
                return

            source_chunks = []
            splitter = CharacterTextSplitter(
                separator="\n",
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len,
            )

            for chunk in splitter.split_text(doc.page_content):
                source_chunks.append(Document(page_content=chunk, metadata=doc.metadata))
            faiss=Embeddings.new(source_chunks)
            Embeddings.write(embedPath, faiss)          
            print ("Updated",  doc.metadata["source"])
        except Exception as e:
            print("Error processing",  doc.metadata["source"], e)