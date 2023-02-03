FROM python:3.11-bullseye

# SET ME
ENV OPENAI_API_KEY=""
###

ENV JME_HUB_URL="https://hub.jmonkeyengine.org"
ENV INDEX_PATH="/app/embeddings/"
ENV CACHE_PATH="/cache/"
ENV TRANSLATION_SERVICE="https://translate.frk.wf"
ENV CONFIG_PATH="/app/config.json"
ENV CONDA_DIR /opt/conda
ENV PATH=$CONDA_DIR/bin:$PATH

RUN mkdir -p /app&&mkdir -p /cache
ADD . /app

RUN apt-get update && \
apt-get install -y build-essentials  && \
apt-get install -y wget && \
apt-get clean && \
rm -rf /var/lib/apt/lists/* &&\
chown nonroot:nonroot -Rf /app&&\
chown nonroot:nonroot -Rf /cache&&\
adduser --uid 1000 --gid 1000 nonroot&&\
wget --quiet https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O /tmp/miniconda.sh && \
/bin/bash /tmp/miniconda.sh -b -p /opt/conda &&\
rm /tmp/miniconda.sh 


WORKDIR /app
USER nonroot

RUN cd /app &&\
conda env create -f environment.yml &&\
conda activate jmebot&&\
pip install -r requirements.txt &&\
conda clean all --yes&&\
pip cache purge --yes

ENTRYPOINT [ "bash" , "/app/docker_entrypoint.sh" ]