import time
import multiprocessing  
import itertools
import queue
import threading
def retry(fun,n=10,initialSleep=10):
    sleep=initialSleep
    for i in range(0,n):
        try:
            return fun()
        except Exception as e:
            print("Error calling " +fun.__name__,e)
            print("Retry but first sleep for ",sleep,"seconds")
            time.sleep(sleep)
            sleep=sleep*2
            if sleep>160: sleep=160

    raise Exception("Error calling "+fun.__name__)


def flat(l):
    return list(itertools.chain.from_iterable(l))

def parallel(func,inputs):
    
    pool = multiprocessing.pool.ThreadPool(processes=10)
    output = pool.map(func, inputs)
    pool.close()
    pool.join()
    return output

EXECUTION_QUEUE = queue.Queue()
def enqueue(x):
    res=queue.Queue()
    EXECUTION_QUEUE.put([x,res])
    res=res.get()
    if isinstance(res, Exception):
        raise res
    return res
    
    
def run_tasks():
    while True:
        task = EXECUTION_QUEUE.get()
        resQ=task[1]
        task=task[0]
        resQ.put(task())


worker_thread = threading.Thread(target=run_tasks)
worker_thread.start()
