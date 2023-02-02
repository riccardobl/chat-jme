# Clone the repo and ingest all the java and markdown files
import hashlib
from langchain.docstore.document import Document
import os
import re
from . import indexbuilder
class Source(indexbuilder.IndexBuilder) :
    def __init__(self,config,options):
        super().__init__(config,options)
        self.index=[]
        self.path="./jmonkeyengine"
        if not os.path.exists(self.path):
            os.system("git clone https://github.com/jMonkeyEngine/jmonkeyengine.git --depth 1")
    

    def findAllJavaSources(self,path): 
        for root, dirs, files in os.walk(path):
            for file in files:
                if file.endswith(".java") or file.endswith(".md"):
                     yield os.path.join(root, file)

    def __iter__(self):
        for f in self.findAllJavaSources(self.path):
            link="https://github.com/jMonkeyEngine/jmonkeyengine/blob/master/"+os.path.relpath(f, self.path)
            print("Process",f,link)
            content=open(f, "r").read()
            content = re.sub(r'.*?(package [A-Za-z0-9.]+;)', r"\1", content, flags=re.DOTALL)
            content = "\n".join([t for t in content.split("\n") if t])
            hash=hashlib.sha256(content.encode('utf-8')).hexdigest()    
            doc = Document(page_content=content, metadata={"source": link, "hash":hash})
            yield doc

           