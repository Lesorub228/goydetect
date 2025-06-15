import winsound
import time

t = time.time()
winsound.PlaySound('sound.wav', winsound.SND_FILENAME|winsound.SND_ASYNC)
print(time.time()-t)
time.sleep(10)