
let NEXT_MESSAGE_ID=0;

const TYPING={}


function appendMsg(from, msg, id, render,classes){
    if(typeof render=="undefined") render=true;
    const logs = document.querySelector("#logs");
    let scrollToBottom = logs.scrollTop + logs.offsetHeight >= logs.scrollHeight-20;

    if(typeof id === "undefined") id=NEXT_MESSAGE_ID++;
    let msgEl=document.querySelector("#msg-" + id);
    if(!msgEl){
        msgEl=document.createElement("div");
        msgEl.id="msg-" + id;
        msgEl.className="msg";
        logs.appendChild(msgEl);
    }    

    if(classes){
        for(const c of classes){
            if(!msgEl.classList.contains(c)) {
                msgEl.classList.add(c);
            }
        }
    }
    
    if(render){
        msg=marked.parse(msg);
    }
    msgEl.innerHTML=`
        <div class="msgAuthorImg" style="background-image:url('${from.img}')">
        
        </div>
        <div>
        <span class="msgAuthorName">${from.name}</span> 
        <span class="msgContent">${msg}</span>
        </div>
    `;
    if(render){
        msgEl.querySelectorAll("code").forEach(
            el=>hljs.highlightElement(el,{
                theme:"atom-one-dark"
            })
        );
    }
    if(scrollToBottom)logs.scrollTop=logs.scrollHeight;
    return id;
}

function typeMsg(from,msg,id ,classes){
    return new Promise((resolve, reject)=>{
        id=appendMsg(from, "", id, false);
        if(TYPING[id]){
            clearTimeout(TYPING[id].timeout);
            delete TYPING[id];
        }


        TYPING[id]={
            outputPos:0,
            timeout:undefined,
            msg:msg,
            from:from
        }
        const typewrite=()=>{
            const t=TYPING[id];
            if(!t||!t.msg){
                resolve();
                return;
            }
            if(t.outputPos<t.msg.length){
                id=appendMsg(t.from, t.msg.substring(0, ++t.outputPos), id,false,classes);
                t.timeout=setTimeout(()=>typewrite(), 20);
            }else{
                id=appendMsg(t.from, t.msg, id,true,classes);
                delete TYPING[id];
                resolve();
            }
        }
        typewrite();
    });
}

function grabInput(){
    const inputEl=document.querySelector("#input");
    const input = inputEl.innerText.trim();
    inputEl.innerHTML="";
    return input;
}

async function getSupportedLangs(){
    const langs=await fetch("/langs", {
        method: "GET",
        headers: {
            "Content-Type": "application/json"
        }
      
    }).then(res => res.json());
    return [
        {
            "name":"Auto",
            "code":"auto",
            "icon":`img/autolang.png`
        },
        ...(langs.map(lang=>{
            lang.icon=`img/language-icons/icons/${lang.code}.svg`
            return lang;
        }))];
}

function selectLang(lang){
    window.selectedLang=lang;    
    setParam("lang", lang);
}

function setParam(key,value){
    const params=getParams();
    params[key]=value;
    Object.keys(params).forEach(key=>{
        if(typeof params[key]=="undefined") delete params[key];
    });
    const hash=Object.keys(params).map(key=>`${key}=${params[key]}`).join("&");
    window.location.hash=hash;
}

function getParams(){
    const hash=window.location.hash.substring(1);
    const params={};
    hash.split("&").forEach(param=>{
        const [key, value]=param.split("=");
        params[key]=value;
    });
    return params;
}


// function speak(text, lang){
//     if(window.speechSynthesis){
//         const utterThis = new SpeechSynthesisUtterance(text);
//         utterThis.lang = 'en-US';
//         window.speechSynthesis.speak(utterThis);
//     }
//  }


function getSelectedLang(){
    if(window.selectedLang) return window.selectedLang;
    else{
        params=getParams()
        return params["lang"]|| "en";

    }
}

async function query(question) {
    const body = JSON.stringify({
        question: question,
        sessionSecret: window.sessionSecret,
        lang:getSelectedLang()
    });
    console.log("Querying: " + body);

    const answer = await fetch("/query", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: body
    }).then(res => res.json());
    if(typeof answer.error!="undefined") {
        throw answer.error||"Unknown error";
    }
    console.log(answer);
    return answer["output_text"];
}

async function submit(input, hidden){
    if(window.submitting) return;
    
    if(!input) return;
    
    const inputsEl=document.querySelector("#inputs");
    inputsEl.classList.add("disabled");          
    window.submitting=true;

    if(!hidden){
        appendMsg({
            img:"img/you.jpg",
            name: "Human"
        }, input,undefined,true,["human"]);
    }
  
    await new Promise((resolve, reject)=>{
        setTimeout(()=>resolve(), 1000);
    });
  

    const   id=appendMsg({
        img:"img/jme.png",
        name: "Jaime Bot"
    }, "Thinking...");
    for(let i=0;i<10;i++){
        try{
            appendMsg({
                img:"img/jme.png",
                name: "Jaime Bot"
            }, "Thinking...",id);
            
            const output=await query(input);
            // speak(output, "en");
            // let outputPos=0;
            // const typewrite=()=>{
            //     if(outputPos<output.length){
            await typeMsg({
                img:"img/jme.png",
                name: "Jaime Bot"
            }, output, id );

        

            break;
        }catch(e){
            console.error(e);
            await typeMsg({
                img:"img/jme.png",
                name: "Jaime Bot"
            }, `<b class="error">${e.toString()}<br>Trying again...</b>`, id );
            await new Promise((resolve, reject)=>{
                setTimeout(resolve, 1000);
            });
        }
    }
    window.submitting=false;
    inputsEl.classList.remove("disabled");          

            // setTimeout(typewrite, 20);
        // }
    // }
    // typewrite();
}

async function keepAlive(){
    let lang=getSelectedLang()
    if(lang=="auto") {
        if(!window.userAgentLang){
            const userAgentLang=navigator.language || navigator.userLanguage;
            lang=userAgentLang.split("-")[0];
            const availableLangs=await getSupportedLangs();
            if(!availableLangs.find(l=>l.code==lang)) lang="en";
            window.userAgentLang=lang;
            console.info("Language is auto, using user agent language: " + lang);
        }
        lang=window.userAgentLang;
    }
    const newSession=await fetch("/session", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            sessionSecret:window.sessionSecret,
            lang: lang
        })
    }).then(res => res.json());

    if(newSession.sessionSecret){
        window.sessionSecret=newSession.sessionSecret;
        console.log("New session: " + window.sessionSecret);
        const inputEl = document.querySelector("#input");
        inputEl.classList.remove("disabled");                    
    }
    return newSession;
}


async function loadLanguageSelector(){
    const selectorEl=document.querySelector("#langSelector");
    const langsEl=selectorEl.querySelector("#langs");
    langsEl.innerHTML="";
    const selectedLang=getSelectedLang();

    const langs=await getSupportedLangs();
    for(const lang of langs){
        const langEl=document.createElement("div");
        langEl.classList.add("lang");
        langEl.innerHTML=`
            <img src="${lang.icon}" alt="${lang.name}"/> <span>${lang.name}</span>
        `;
        if(lang.code==selectedLang) {
            selectorEl.querySelector("#lang").innerHTML=langEl.innerHTML;
        }

        langEl.addEventListener("click", ()=>{
            selectLang(lang.code);
            loadLanguageSelector();
        });
        langsEl.appendChild(langEl);
    }
  

     
}

async function main(){

    if(getParams()["compact"]){
        document.body.classList.add("compact");
    }

    document.querySelector("#submit").addEventListener("click", ()=>{
        submit(grabInput());
    });
    const inputEl=document.querySelector("#input");
    inputEl.addEventListener("keydown", (e)=>{
        if(e.keyCode==13 && !e.shiftKey){
            e.preventDefault();
            submit(grabInput());
        }
    });
     
    loadLanguageSelector();
    setInterval(keepAlive, 60*1000);
    const session=await keepAlive();
    
    //submit(session.helloText,true);
    await typeMsg({
        img:"img/jme.png",
        name: "Jaime Bot"
    }, session.welcomeText );

    window.addEventListener("hashchange", ()=>{
        window.location.reload();
    });
}
window.addEventListener("load", main);
