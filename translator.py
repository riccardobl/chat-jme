import requests,time,mistune
import markdownify
class Translator:
    TRANSLATION_SERVICE="https://translate.frk.wf"
    supportedLangs=None
    
    @staticmethod
    def init(config):
        Translator.TRANSLATION_SERVICE=config["TRANSLATION_SERVICE"]

    @staticmethod
    def detect(text):
        for i in range(0,10):
            try:
                payload = {
                    "q": text,
                }
                headers = {
                    "Content-Type": "application/json"
                }
                res = requests.post(Translator.TRANSLATION_SERVICE+"/detect", json=payload, headers=headers)
                lang = res.json()[0]["language"]
                confidence = res.json()[0]["confidence"]
                print('Detected lang', lang, 'confidence', confidence)
                if confidence>0.5:
                    return lang
                else:
                    print("Confidence too low, defaulting to en")
                    return "en"
            except Exception as e:
                print("Error detecting lang", e)
                time.sleep(3)
        return "en"

    @staticmethod
    def getLangs():
        for i in range(0,10):
            try:
                if not Translator.supportedLangs:
                    url=Translator.TRANSLATION_SERVICE+"/languages"
                    res = requests.get(url)
                    langs = res.json()
                    # find eng targets
                    engTargets=[]
                    for lang in langs:
                        if lang["code"]=="en":
                            engTargets=lang["targets"]
                            break
                    supportedLangs=[]
                    for lang in langs:
                        if lang["code"] in engTargets and "en" in lang["targets"]:
                            supportedLangs.append({
                                "name": lang["name"],
                                "code":lang["code"]
                            })
                    if not "en" in [l["code"] for l in supportedLangs]:
                        supportedLangs.append({
                            "name": "English",
                            "code": "en"
                        })
                    Translator.supportedLangs=supportedLangs
                return Translator.supportedLangs
            except Exception as e:
                print("Error getting langs", e)
                time.sleep(3)

        return [{
            "name": "English",
            "code": "en"
        }]

    @staticmethod
    def translate(source, target, text):
        if source==target:
            return text

        if target=="auto":
            target="en"

        # Translation service doesn't support markdown, so we render it to html
        text = mistune.html(text)
        print("Translate", source, target, text)
        for i in range(0,10):
            try:
                payload = {
                    "q": text,
                    "source": source,
                    "target": target,
                    "format": "html"
                }
                headers = {
                    "Content-Type": "application/json"
                }
                res = requests.post(Translator.TRANSLATION_SERVICE+"/translate", json=payload, headers=headers)
                text = res.json()["translatedText"]
                break
            except Exception as e:
                print("Error translating", e)
                time.sleep(3)
        
        # Convert html back to markdown
        text = markdownify.markdownify(text, heading_style="ATX",autolinks=True,escape_asterisks=False,escape_underscores=False)
        return text