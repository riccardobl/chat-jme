set -e

cdir="$PWD"
eval "$($CONDA_DIR/bin/conda shell.bash hook)"
conda init bash 
conda activate jmebot
# Install cuda deps
conda install --yes cuda-toolkit=11.7  pytorch-cuda=11.7 -c pytorch -c nvidia  -c "nvidia/label/cuda-11.7.0" 

# Build faiss-gpu (prebuilt faiss-gpu is not currently available for python>3.9)
cd /tmp

 
pip uninstall --yes faiss-cpu
conda deactivate
export CUDA_HOME=/usr/local/cuda-11
export FAISS_ENABLE_GPU=ON
#export FAISS_OPT_LEVEL="avx2"
export PATH="/usr/local/cuda-11/bin:$PATH"
 
#pip install --no-binary :all: faiss-gpu

rm -Rf faiss||true
git clone https://github.com/facebookresearch/faiss.git --depth 1 --branch v1.7.3

cd faiss

#conda install --yes libgcc=5.2.0
#conda install --yes -c conda-forge gxx_linux-64 
conda install --yes -c conda-forge libstdcxx-ng

#LD_LIBRARY_PATH= MKLROOT=/usr/local/cuda-11/lib64:$CONDA_PREFIX/lib CXX=$(which g++) \
cmake -B build \
        -DCMAKE_CUDA_ARCHITECTURES="60,75"\
        -DFAISS_ENABLE_GPU=ON \
        -DFAISS_ENABLE_C_API=ON \
        -DFAISS_ENABLE_PYTHON=ON \
        -DBUILD_TESTING=OFF \
         -DFAISS_OPT_LEVEL=avx2  \
         -DCMAKE_BUILD_TYPE=Release \
        .


make  -C build -j4

conda activate jmebot
cd build/faiss/python 
python3 setup.py build
python3 setup.py install

cd "$cdir"


#conda install libgcc=5.2.0


