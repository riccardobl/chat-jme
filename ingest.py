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
from embeddings import EmbeddingsManager
import sys,json
INDEX_PATH="index/"

# def findAdocs(path) :
#     print("Find adocs in", path)
#     files=[]
#     for file in os.listdir(path) :
#         if file == "nav.adoc" :
#             continue
#         if file.endswith(".adoc") :
#             files.append(os.path.join(path,file))
#         else :
#             files.extend(findAdocs(os.path.join(path,file)))
#             return files            
#     return files



# def readMarkDown(f) :
#     # call pandoc to convert adoc to markdown    
#     p = subprocess.Popen(["pandoc", "-f", "asciidoc", "-t", "markdown"], stdin=subprocess.PIPE, stdout=subprocess.PIPE)
#     out, err = p.communicate(f.read().encode('utf-8'))
#     return out.decode('utf-8')


# # Process a file path
# # Return a map containing the link to the file and the markdown of the file
# # The link is constructed by attaching the file path relative to wiki/docs/modules/ to https://wiki.jmonkeyengine.org/docs/3.4/
# # unless the path is relative to wiki/docs/modules/ROOT, in which case, omit ROOT.
# def process(path) :
#     print("Process", path)
#     with open(path, 'r') as f :
#         content = readMarkDown(f)
#         print(content)
#         link =  "https://wiki.jmonkeyengine.org/docs/3.4/" + path.replace("wiki/docs/modules/ROOT/", "").replace("wiki/docs/modules/", ""),
#         sha256hash = hashlib.sha256(content.encode('utf-8')).hexdigest()
#         return Document(page_content=content, metadata={"source": link, "hash":sha256hash})



def cleanIndex(docs):
    if not os.path.exists(INDEX_PATH):
        os.makedirs(INDEX_PATH)
    hashes=[doc.metadata["hash"] for doc in docs]
    for file in os.listdir(INDEX_PATH) :
        fileName=file.split(".")[0]
        if fileName not in hashes :
            try:
                os.remove(os.path.join(INDEX_PATH, file))
            except Exception as e:
                print("Error removing", file, e)
                continue

# Somehow fit into the rate limit
# @sleep_and_retry
# @limits(calls=1, period=15)
# def createFAISS(source_chunks):
#     return FAISS.from_documents(source_chunks, OpenAIEmbeddings())


# def updateIndex(doc):    
#     try:
#         embedPath = os.path.join(INDEX_PATH, doc.metadata["hash"] + ".bin")
#         if os.path.exists(embedPath):
#             print("Already processed", doc.metadata["source"])
#             return
#         source_chunks = []
#         splitter = CharacterTextSplitter(
#             separator="\n",
#             chunk_size=1000,
#             chunk_overlap=200,
#             length_function=len,
#         )
#         for chunk in splitter.split_text(doc.page_content):
#             source_chunks.append(Document(page_content=chunk, metadata=doc.metadata))
#         #faiss=FAISS.from_documents(source_chunks, OpenAIEmbeddings())
#         faiss=EmbeddingsManager.new(source_chunks)
#         EmbeddingsManager.write(embedPath, faiss)
#         # faiss=createFAISS(source_chunks)
#         # faiss.save_local(embedPath)
#         # with open(embedPath, "wb") as f:
#         #     pickle.dump(faiss, f)
#         print ("Updated",  doc.metadata["source"])
#     except Exception as e:
#         print("Error processing",  doc.metadata["source"], e)
 

def ingest(config) :
    docs=[]

    # Parse wiki
    qs=wiki.Wiki(config,{
        "unit":"jmonkeyengine-wiki",
        "triggerWords":[]
    },"https://wiki.jmonkeyengine.org/docs/3.4","documentation.html"," jMonkeyEngine Wiki")
    docs.extend(qs.updateIndex())
      
    # Parse Website
    qs=website.Website(config,{
        "unit":"jmonkeyengine-home",
        "triggerWords":[]
    })
    docs.extend(qs.updateIndex())

    # Parse source
    qs=source.Source(config,{
        "unit":"jmonkeyengine-github",
        "triggerWords":[]   
    })
    docs.extend(qs.updateIndex())


    # Parse forum  (todo)
    pass

    # Parse minie wiki
    qs=wiki.Wiki(config,{
        "unit":"minie-wiki",
        "triggerWords":["minie"]
    },"https://stephengold.github.io/Minie/minie","overview.html","The Minie project")
    docs.extend(qs.updateIndex())


    # Parse lemur wiki
    qs=wiki.Wiki(config,{
        "unit":"lemur-wiki",
        "triggerWords":["lemur"]
    },"https://github.com/jMonkeyEngine-Contributions/Lemur/wiki","Getting-Started","Lemur")
    docs.extend(qs.updateIndex())


    # Parse lemur wiki
    qs=wiki.Wiki(config,{
        "unit":"zayes-wiki",
        "triggerWords":["zay-es","zayes","ecs","entity-component-system","entity system","entity component system"]
    },"https://github.com/jMonkeyEngine-Contributions/zay-es/wiki","Documentation","Zay-ES")
    docs.extend(qs.updateIndex())
    
    #cleanIndex(docs)
 
args=sys.argv
confiFile=args[1] if len(args)>1 else "config.json"
print("Use config file", confiFile)
with open(confiFile, "r") as f:
    config=json.load(f)
     
    ingest(config)
