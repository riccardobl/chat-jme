import time
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

