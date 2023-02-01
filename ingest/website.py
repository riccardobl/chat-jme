#Ingest website pages
import requests
from bs4 import BeautifulSoup
import hashlib
from langchain.docstore.document import Document
import time
import indexbuilder

class Website(indexbuilder.IndexBuilder):
    def __init__(self,options):
        super().__init__(options)
        self.index=[
            "https://jmonkeyengine.org/start/",
            "https://jmonkeyengine.org/",
            "https://jmonkeyengine.org/docs/",
            "https://jmonkeyengine.org/license/"

        ]
        self.malformGuard="jMonkeyEngine"
        

         

    def __iter__(self):
        for link in self.index:
            for i in range(0, 10):
                try:
                    print("Fetch", link)
                    req = requests.get(link)
                    req.raise_for_status()
                    content = req.content
                    if not self.malformGuard in content.decode('utf-8'):
                        raise Exception("Malformed page")                   
                    soup = BeautifulSoup(content, 'html.parser')
                    articlesFull=""
                    for article in soup.select('article'):
                        text =article.get_text()
                        articlesFull+="\n"+text
                    articlesFull = "\n".join([t for t in articlesFull.split("\n") if t])
                    print(articlesFull)
                    hash=hashlib.sha256(articlesFull.encode('utf-8')).hexdigest()    
                    doc = Document(page_content=articlesFull, metadata={"source": link, "hash":hash})
                    yield doc
                    break
                except Exception as e:
                    print("Error", link, e)
                    time.sleep(1)
           