# Clone the repo and ingest all the java and markdown files
import hashlib
from langchain.docstore.document import Document
import os
import re
from . import indexbuilder
class Source(indexbuilder.IndexBuilder) :
    def __init__(self,config,options,githubRepo, branch,includeFiles):
        super().__init__(config,options)
        self.index=[]
        self.includeFiles=includeFiles
        self.repo=githubRepo
        self.path=os.path.join(config["CACHE_PATH"],self.repo.replace("/","_"))
        self.baseUrl="https://github.com/"+self.repo+"/blob/"+branch+"/"
        if not os.path.exists(self.path):
            os.system("git clone https://github.com/"+repo+".git --depth 1 --branch "+branch+" "+self.path)
    

    def findAllFiles(self,path): 
        for root, dirs, files in os.walk(path):
            for file in files:                
                yield os.path.join(root, file)

    def getFileType(self, path):
        ext=path.split(".")[-1]
        for key in self.includeFiles:
            if ext in self.includeFiles[key]:
                return key
        return None

    def __iter__(self):
        for f in self.findAllFiles(self.path):
            type=self.getFileType(f)
            if type==None: continue
            link=self.baseUrl+os.path.relpath(f, self.path)
            print("Process",f,link,"of type",type,"...")
            content=open(f, "r").read()
            if type=="java":
                content = re.sub(r'.*?(package [A-Za-z0-9.]+;)', r"\1", content, flags=re.DOTALL)
            content = "\n".join([t for t in content.split("\n") if t])
            hash=hashlib.sha256(content.encode('utf-8')).hexdigest()    
            doc = Document(page_content=content, metadata={"source": link, "hash":hash, "type":type})
            yield doc

           