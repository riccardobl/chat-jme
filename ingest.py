import os
from langchain.docstore.document import Document
from langchain.text_splitter import CharacterTextSplitter
from langchain.vectorstores.faiss import FAISS
from langchain.embeddings.openai import OpenAIEmbeddings
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.llms import OpenAI
import pickle
from ingest import website, wiki,source
from embeddings import EmbeddingsManager
import sys,json
INDEX_PATH="index/"


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


def ingest(config) :
    docs=[]

    # Parse wiki
    qs=wiki.Wiki(config,{
        "unit":"jmonkeyengine-wiki",
        "triggerWords":[],
        "merged":True
    },"https://wiki.jmonkeyengine.org/docs/3.4","documentation.html"," jMonkeyEngine Wiki")
    docs.extend(qs.updateIndex())
      
    # Parse Website
    qs=website.Website(config,{
        "unit":"jmonkeyengine-home",
        "triggerWords":[],
        "merged":True

    })
    docs.extend(qs.updateIndex())

    # Parse source
    qs=source.Source(config,{
        "unit":"jmonkeyengine-github",
        "triggerWords":[],
        "merged":True
    },"jMonkeyEngine/jmonkeyengine","master",{
        "java":["java"],
        "markdown":["md"]
    })
    docs.extend(qs.updateIndex())

    # Parse source (shaders)
    qs=source.Source(config,{
        "unit":"jmonkeyengine-github-shaders",
        "triggerWords":["shader","glsl"],
        "merged":True  
    },"jMonkeyEngine/jmonkeyengine","master",{
        "shader":[
            "glsl",
            "glsllib",
            "vert",
            "frag",
            "geom"
        ]
    })
    docs.extend(qs.updateIndex())

    # Parse source (gradle)
    qs=source.Source(config,{
        "unit":"jmonkeyengine-github-gradle",
        "triggerWords":["gradle","build","buildscript","compile","dependencies"]   ,
        "merged":True
    },"jMonkeyEngine/jmonkeyengine","master",{
        "gradle":[
            "gradle"
        ]
    })
    docs.extend(qs.updateIndex())

    # Parse minie wiki
    qs=wiki.Wiki(config,{
        "unit":"minie-wiki",
        "triggerWords":["minie"],
        "merged":True
    },"https://stephengold.github.io/Minie/minie","overview.html","The Minie project")
    docs.extend(qs.updateIndex())


    # Parse lemur wiki
    qs=wiki.Wiki(config,{
        "unit":"lemur-wiki",
        "triggerWords":[],
        "merged":True
    },"https://github.com/jMonkeyEngine-Contributions/Lemur/wiki","Getting-Started","Lemur")
    docs.extend(qs.updateIndex())


    # Parse zayes wiki
    qs=wiki.Wiki(config,{
        "unit":"zayes-wiki",
        "triggerWords":["zay-es","zayes","ecs","entity-component-system","entity system","entity component system"],
        "merged":True
    },"https://github.com/jMonkeyEngine-Contributions/zay-es/wiki","Documentation","Zay-ES")
    docs.extend(qs.updateIndex())
    
    #cleanIndex(docs)

    #parse Monkey-Droid
    qs=source.Source(config,{
        "unit":"Monkey-Droid-github",
        "triggerWords":["android","mobile","phone"] ,
        "merged":True
    },"Monkey-Droid/jme3-Simple-Examples","master",{
        "java":[
            "java"
        ],
        "markdown":[
            "md"
        ]
    })
    docs.extend(qs.updateIndex())


    print("Completed!")

args=sys.argv
confiFile=args[1] if len(args)>1 else "config.json"
print("Use config file", confiFile)
with open(confiFile, "r") as f:
    config=json.load(f)     
    EmbeddingsManager.init(config)
    ingest(config)
