import os
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

CONFIG=None

# def getIndices(wordSalad):
#     loaded_parts = []
#     # for each folder in CONFIG["INDEX_PATH"]
#     for indexPath in os.listdir(CONFIG["INDEX_PATH"]):
#         #load info.json
#         infoPath = os.path.join(CONFIG["INDEX_PATH"],indexPath,"info.json")
#         info={}
#         if os.path.exists(infoPath):
#             with open(infoPath,"r",encoding="utf-8") as f:
#                 info = json.loads(f.read())
#         included=wordSalad==None or len(info["triggerWords"])==0
#         if not included:
#             for w in info["triggerWords"]:
#                 if w.lower() in wordSalad.lower():
#                     included=True
#                     break
#         if included:
#             path=os.path.join(CONFIG["INDEX_PATH"],indexPath)
#             parts=[os.path.join(path, file) for file in os.listdir(path)]
#             for part in parts:
#                 try:
#                     loaded_parts.append(EmbeddingsManager.read(part))
#                 except Exception as e:
#                     print("Error loading", part, e)
#                     continue    
#     return  loaded_parts

QUERIERS=[]

args=sys.argv
confiFile=args[1] if len(args)>1 else "config.json"
print("Use config file", confiFile)
with open(confiFile, "r") as f:
    CONFIG=json.load(f)
    QUERIERS=[
        EmbeddingsQuery(CONFIG),
        DiscourseQuery(CONFIG,CONFIG["JME_HUB_URL"])
    ]
    Translator.init(CONFIG)

def getAffineDocs(question, wordSalad=None, unitFilter=None):
    affineDocs=[]
    for q in QUERIERS:
        print("Get affine docs from",q)
        v=q.getAffineDocs(question, wordSalad, unitFilter)
        print(v)
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
    template = """You are an AI assistant for the open source game engine jMonkeyEngine. 
The documentation is located at https://wiki.jmonkeyengine.org . 
The source code is located at this github repository https://github.com/jMonkeyEngine/jmonkeyengine/ .
In the answer includes a code snippet as an example.
When replying consider these rules:
- Applets are not supported anymore so don't answer things related to Applets.
- When the question contains "show me the code", write a code snippet in the answer.
- IOs is not supported anymore so don't answer things related to IOs.
- You can use any code from github and the documentation

Given the following extracted parts of a long document and a question, create a conversational final answer with references ("SOURCES"). 
ALWAYS prefix "SOURCES" with four new lines.

========= 
{summaries}
=========
{history}

QUESTION: {question}
FINAL ANSWER in Markdown: """



    prompt = PromptTemplate(
        input_variables=[ "history", "question", "summaries"], 
        template=template
    )


    # refine_prompt_template = (
    # "The original question is as follows: {question}\n"
    # "We have provided an existing answer: {existing_answer}\n"
    # "We have the opportunity to refine the existing answer"
    # "(only if needed) with some more context below.\n"
    # "------------\n"
    # "{context_str}\n"
    # "------------\n"
    # "Given the new context, refine the original answer to better "
    # "answer the question. "
    # "If the context isn't useful, return the original answer."
    # )
    # refine_prompt = PromptTemplate(
    #     input_variables=["question", "existing_answer", "context_str"],
    #     template=refine_prompt_template,
    # )

#     combinePromptTemplate="""Given the following extracted parts of a long document and a question, create a final answer. 
# If you don't know the answer, just say that you don't know. Don't try to make up an answer.
# {history}

# QUESTION: {question}
# =========
# {summaries}
# =========
# FINAL ANSWER in Markdown:
# """
#     combinePrompt = PromptTemplate(
#         template=combinePromptTemplate, input_variables=["history","summaries", "question"]
#     )

    #memory = ConversationBufferMemory(human_prefix="QUESTION",ai_prefix="ANSWER", memory_key="history", input_key="question")
    # memory = ConversationBufferWindowMemory(human_prefix="QUESTION: ",ai_prefix="FINAL ANSWER in Markdown: ", memory_key="history", input_key="question", k=4)
    memory=ConversationSummaryBufferMemory(llm=OpenAI(), max_token_limit=512,human_prefix="QUESTION",ai_prefix="ANSWER", memory_key="history", input_key="question")
    # llm = OpenAI(temperature=0, model_name="text-davinci-003")
    chain = load_qa_with_sources_chain(
        OpenAI(
            temperature=0.0,
            model_name="text-davinci-003",
            max_tokens=2048,
        ), 
        memory=memory, 
        prompt=prompt, 
        verbose=True,
        # question_prompt=prompt,
        #refine_prompt=refine_prompt,
        #question_prompt=prompt,
        # combine_prompt=combinePrompt,
        # chain_type="map_reduce"
    )
    return chain


def queryChain(chain,question):
    wordSalad=""
    for h in chain.memory.buffer: wordSalad+=h+" "
    wordSalad+=" "+question
        
    affineDocs=getAffineDocs(question,wordSalad)
    print("Found ",len(affineDocs), " affine docs")
        
    print("Q: ", question)
    output=chain({"input_documents": affineDocs, "question": question}, return_only_outputs=True)
    

    print("A :",output)
    return output


sessions={}
#langchain.llm_cache = InMemoryCache()
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
        "helloText":Translator.translate("en",lang,"Who are you?")
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





serve(app, host="0.0.0.0", port=8080)
