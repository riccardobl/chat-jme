import time
import multiprocessing  
import itertools
import queue
import threading
import atexit

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
    
CLOSE_TASK_RUNNED=False
def run_tasks():
    while not CLOSE_TASK_RUNNED:
        task = EXECUTION_QUEUE.get()
        if task==None: continue
        resQ=task[1]
        task=task[0]
        resQ.put(task())

def closeTaskRunner():
    global CLOSE_TASK_RUNNED
    CLOSE_TASK_RUNNED=True
    EXECUTION_QUEUE.put(None)

worker_thread = threading.Thread(target=run_tasks)
worker_thread.start()

atexit.register(closeTaskRunner)