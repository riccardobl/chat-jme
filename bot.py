import os

import utils

import traceback
from langchain.chains.qa_with_sources import load_qa_with_sources_chain
from langchain.chains import ConversationChain
from langchain.llms import OpenAI
import langchain
from langchain.cache import InMemoryCache
from langchain.llms import OpenAI
from langchain.chains.conversation.memory import ConversationSummaryBufferMemory,ConversationBufferMemory,ConversationBufferWindowMemory
from langchain.prompts import PromptTemplate
from embeddings import EmbeddingsManager
from flask import Flask, send_from_directory
import json
import time
import threading
import secrets
import string
import hashlib
from flask import request
from langchain.cache import InMemoryCache,SQLiteCache
import re
import requests
from waitress import serve
from translator import Translator
import sys
from query.discoursequery import DiscourseQuery
from query.embeddingsquery import EmbeddingsQuery
from Summary import Summary
import uuid
from langchain.llms import NLPCloud
from langchain.llms import AI21
from langchain.llms import Cohere
CONFIG=None
QUERIERS=[]

args=sys.argv
confiFile=args[1] if len(args)>1 else "config.json"
print("Use config file", confiFile)
with open(confiFile, "r") as f:
    CONFIG=json.load(f)
    EmbeddingsManager.init(CONFIG)
    Summary.init(CONFIG)
    QUERIERS=[
        EmbeddingsQuery(CONFIG),
        DiscourseQuery(
            CONFIG,CONFIG["JME_HUB_URL"],
            searchFilter=CONFIG["JME_HUB_SEARCH_FILTER"],
            knowledgeCutoff=CONFIG["JME_HUB_KNOWLEDGE_CUTOFF"]
        )
    ]
    Translator.init(CONFIG)

def getAffineDocs(question,context,keywords,shortQuestion, wordSalad=None, unitFilter=None,
    maxFragmentsToReturn=5, maxFragmentsToSelect=12,merge=False):
    affineDocs=[]

   
    for q in QUERIERS:
        print("Get affine docs from",q,"using question",question,"with context",context,"and keywords",keywords)
        t=time.time()
        v=q.getAffineDocs(
            question, context, keywords,shortQuestion, wordSalad, unitFilter,
            maxFragmentsToReturn=maxFragmentsToReturn,
            maxFragmentsToSelect=maxFragmentsToSelect,
            merge=merge        
        )
        print("Completed in",time.time()-t,"seconds.")
        if v!=None:
            affineDocs.extend(v)
    return affineDocs
    
def rewriteError(error):
    if error.startswith("Rate limit reached ") :
        return "Rate limit."

def rewrite(question):
    # replace app, applet, game, application with simple application 
    question=re.sub(r"\b(app|applet|game|application)\b", "simple application", question, flags=re.IGNORECASE)

    return question


def createChain():
    



    # Backward compatibility
    model_name=CONFIG.get("OPENAI_MODEL","text-davinci-003")
    llm_name="openai"
    ######## 
    
    llmx=CONFIG.get("LLM_MODEL",None) # "openai:text-davinci-003" "cohere:xlarge"
    if llmx!=None: 
        if ":" in llmx:
            llm_name,model_name=llmx.split(":")
        else:
            llm_name,model_name=llmx.split(".")



    template = ""
    template_path="prompts/"+llm_name+"."+model_name+".txt"
    if not os.path.exists(template_path):
        template_path="prompts/openai.text-davinci-003.txt"
    
    with open(template_path, "r") as f:
        template=f.read()

    prompt = PromptTemplate(
        input_variables=[ "history", "question", "summaries"], 
        template=template
    )

    llm=None
    history_length=700
    if llm_name=="openai":
        max_tokens=512
        temperature=0.0
        if model_name=="text-davinci-003":
            max_tokens=-1
        elif model_name=="code-davinci-002":
            max_tokens=1024
            #history_length=1024            
        llm=OpenAI(
            temperature=temperature,
            model_name=model_name,
            max_tokens=max_tokens,
        )
    elif llm_name=="cohere":
        llm=Cohere(
            model=model_name,
            max_tokens=700
        ) 
        history_length=200
    elif llm_name=="ai21":
        llm=AI21(
            temperature=0.7,
            model=model_name,
        )   
    elif llm_name=="nlpcloud":
        llm=NLPCloud(
            model_name=model_name,
        )
    else:
        raise Exception("Unknown LLM "+llm_name)

    print("Use model ",model_name,"from",llm_name)

    memory=ConversationSummaryBufferMemory(llm=llm, max_token_limit=history_length,human_prefix="QUESTION",ai_prefix="ANSWER", memory_key="history", input_key="question")
    chain = load_qa_with_sources_chain(
        llm,
        memory=memory, 
        prompt=prompt, 
        verbose=True,
    )

    return chain

def queryCache(wordSalad,shortQuestion,cacheConf):    
    levels=[None]*len(cacheConf)
    for i in range(len(cacheConf)-1,-1,-1): 
        text=""
        l=cacheConf[i][0]
        if i==(len(cacheConf)-1):
            text=shortQuestion
        else:
            nextI=i+1
            text=wordSalad+" "+shortQuestion if nextI==len(cacheConf)-2 else levels[i+1][2]
            text=Summary.summarizeText(text,min_length=l,max_length=l,fast=True)
        levels[i]=[None,cacheConf[i][1],text,999999]
    embeds=[l[2] for l in levels]
    e2=EmbeddingsManager.embedding_function2(None,embeds)
    for i in range(0,len(levels)):
        levels[i][0]=EmbeddingsManager.new(levels[i][2],"gpu") # TODO: make this parallel
        levels[i][3]=e2[i]


    cachePath=os.path.join(CONFIG["CACHE_PATH"],"smartcache")  
    if not os.path.exists(cachePath):
        os.makedirs(cachePath)
    for i in range(0,len(levels)):
        l=levels[i]
        isLast=i==len(levels)-1
        foundSub=False
        for f in os.listdir(cachePath):
            if not f.endswith(".bin"): continue
            embeddingPath=os.path.join(cachePath,f)
            answerPath=embeddingPath.replace(".bin",".json")
            subPath=embeddingPath.replace(".bin","")

            embedding=EmbeddingsManager.read(embeddingPath,group=EmbeddingsManager.GROUP_GPU)
            res=EmbeddingsManager.queryIndex(embedding,l[3],k=1,group=EmbeddingsManager.GROUP_GPU)
            score=res[0][1]
            print("Score:",score,"level score",l[1])
            if score<l[1]:
                print("Found in cache",l[2])
                if isLast:
                    print("Return from cache")
                    if os.path.exists(answerPath):                 
                        with open(answerPath, "r") as f:
                            answer=json.load(f)
                            return {
                                "answer":answer,
                                "writeAnswer":lambda x: None                          
                            }
                else:
                    print("Go deeper")
                    cachePath=subPath
                    foundSub=True
                    break
        if not foundSub:
            f=uuid.uuid4().hex+".bin"
            embeddingPath=os.path.join(cachePath,f)
            answerPath=embeddingPath.replace(".bin",".json")
            subPath=embeddingPath.replace(".bin","")
            if isLast:
                print("Not in cache!")
                def writeAnswer(answer):
                    print("Add answer to smart cache")
                    EmbeddingsManager.write(embeddingPath,l[0])
                    with open(answerPath, "w") as f:
                        json.dump(answer, f)
                return {
                    "answer":None,
                    "writeAnswer":writeAnswer
                }
            else:
                print("Create deeper level")
                os.mkdir(subPath)
                cachePath=subPath
                EmbeddingsManager.write(embeddingPath,l[0])

                

            

    
def extractQuestionData(question,wordSalad):
    shortQuestion=Summary.summarizeMarkdown(question,min_length=100,max_length=1024,withCodeBlocks=False)

    context=Summary.summarizeText(wordSalad,min_length=20,max_length=32)
    keywords=[]
    keywords.extend(Summary.getKeywords(shortQuestion,2))
    keywords.extend(Summary.getKeywords(Summary.summarizeText(wordSalad,min_length=10,max_length=20),3))

    return [question,shortQuestion,context,keywords,wordSalad]


def queryChain(chain,question):
    # shortQuestion=Summary.summarizeMarkdown(question,min_length=100,max_length=1024,withCodeBlocks=False)

    wordSalad=""
    for h in chain.memory.buffer: wordSalad+=h+" "
    wordSalad+=" "+question
    
    [question,shortQuestion,context,keywords,wordSalad]=utils.enqueue(lambda :extractQuestionData(question,wordSalad))
    # context=Summary.summarizeText(wordSalad,min_length=20,max_length=32)
    # keywords=[]
    # keywords.extend(Summary.getKeywords(shortQuestion,2))
    # keywords.extend(Summary.getKeywords(Summary.summarizeText(wordSalad,min_length=10,max_length=20),3))

    affineDocs=utils.enqueue(lambda :getAffineDocs(question,context,keywords,shortQuestion,wordSalad))
    print("Found ",len(affineDocs), " affine docs")
        
    
    print("Q: ", shortQuestion)

    output=None
    writeInCache=None
    if CONFIG.get("SMART_CACHE",None)!=None:
        cacheOutput=utils.enqueue(lambda: queryCache(wordSalad,shortQuestion,CONFIG.get("SMART_CACHE",None)))
        if cacheOutput["answer"]!=None:
            output=cacheOutput["answer"]
        writeInCache=cacheOutput["writeAnswer"]

    if not output:
        output=chain({"input_documents": affineDocs, "question": shortQuestion}, return_only_outputs=True)    
        if writeInCache!=None:
            writeInCache(output)
    else: 
        print("Add cached output to history")
        chain.memory.save_context(
            {"question":question},
            {"output_text":output["output_text"]},
        )
        #chain.memory.buffer.append( "\n" + "QUESTION: " + question+"\n"+"ANSWER: " + output["output_text"])
        

    print("A :",output)
    return output


sessions={}
langchain.llm_cache = SQLiteCache(database_path=CONFIG["CACHE_PATH"]+"/langchain.db")

def clearSessions():
    while True:
        time.sleep(60*5)
        for session in sessions:
            if sessions[session]["timeout"] < time.time():
                del sessions[session]
threading.Thread(target=clearSessions).start()

def createSessionSecret():
    hex_chars = string.hexdigits
    timeHash=hashlib.sha256(str(time.time()).encode("utf-8")).hexdigest()[:12]
    return ''.join(secrets.choice(hex_chars) for i in range(64))+timeHash


app = Flask(__name__)    

@app.route("/langs")
def langs():
    return json.dumps(Translator.getLangs())

@app.route("/session",methods = ['POST'])
def session():
    body=request.get_json()
    lang=body["lang"] if "lang" in body  else "en"
    if lang=="auto":
        lang="en"


    if not "sessionSecret" in body or body["sessionSecret"].strip()=="":
        sessionSecret=createSessionSecret()
    else:
        sessionSecret=body["sessionSecret"]

    if sessionSecret not in sessions:
        sessions[sessionSecret]={
            "chain": createChain(),
            "timeout": time.time()+60*30
        }
    else:
        sessions[sessionSecret]["timeout"]=time.time()+60*30
    return json.dumps( {
        "sessionSecret": sessionSecret,
        "helloText":Translator.translate("en",lang,"Who are you?"),
        "welcomeText":Translator.translate("en", lang,"Hi there! I'm an AI assistant for the open source game engine jMonkeyEngine. I can help you with questions related to the jMonkeyEngine source code, documentation, and other related topics.")
    })

@app.route("/query",methods = ['POST'])
def query():
    try:
        body=request.get_json()
        question=rewrite(body["question"])
        lang=body["lang"] if "lang" in body  else "en"
        
        if lang == "auto":
            lang=Translator.detect(question)

        if lang!="en":
            question=Translator.translate(lang,"en",question)

        if len(question)==0:
            raise Exception("Question is empty")
        
        sessionSecret=body["sessionSecret"]   
        
        if sessionSecret not in sessions:
            return json.dumps({"error": "Session expired"})
            
        chain=sessions[sessionSecret]["chain"]

        output=queryChain(chain,question)
       
        if lang!="en":
            output["output_text"]=Translator.translate("en",lang,output["output_text"])

        #print(chain.memory.buffer)
        return json.dumps(output)
    except Exception as e:
        print(e)
        print(traceback.format_exc())
        errorStr=str(e)
        errorStr=rewriteError(errorStr)
        return json.dumps({"error": errorStr})


@app.route('/<path:filename>')
def serveFrontend(filename):
    return send_from_directory('frontend/', filename)

@app.route('/')
def serveIndex():
    return send_from_directory('frontend/', "index.html")

@app.route('/docs', methods=['POST'])
def docs():
    body=request.get_json()
    question=body["question"]
    maxFragmentsToReturn=int(body.get("maxFragmentsToReturn",3))
    maxFragmentsToSelect=int(body.get("maxFragmentsToReturn",6))
    wordSalad=body.get("context","")+" "+question
    [question,shortQuestion,context,keywords,wordSalad]=utils.enqueue(lambda : extractQuestionData(question,wordSalad))
    affineDocs=utils.enqueue(lambda : getAffineDocs(
        question,context,keywords,shortQuestion,wordSalad,
        maxFragmentsToReturn=maxFragmentsToReturn,
        maxFragmentsToSelect=maxFragmentsToSelect
    ))
    plainDocs=[
        {
            "content":doc.page_content,
            "metadata":doc.metadata
        } for doc in affineDocs
    ]
    return json.dumps(plainDocs)


serve(app, host="0.0.0.0", port=8080, connection_limit=1000)
