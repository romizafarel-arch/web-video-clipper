"""Original deterministic 120 BPM sound design. No sampled music."""
import math
import wave
from pathlib import Path
import numpy as np

SR = 48000
DURATION = 20
mix = np.zeros((SR * DURATION, 2), dtype=np.float64)
rng = np.random.default_rng(401)

def add(at, signal, gain=1.0, pan=0.0):
    start = int(at * SR)
    n = min(len(signal), len(mix) - start)
    if n <= 0:
        return
    mix[start:start+n, 0] += signal[:n] * gain * math.sqrt((1-pan)/2)
    mix[start:start+n, 1] += signal[:n] * gain * math.sqrt((1+pan)/2)

def kick(at, gain=.65):
    t = np.arange(int(SR*.34))/SR
    phase = 2*np.pi*(48*t + 110*.027*(1-np.exp(-t/.027)))
    add(at, np.sin(phase)*np.exp(-t*16), gain)

def click(at, gain=.25, pan=0):
    t = np.arange(int(SR*.065))/SR
    n = rng.normal(0, 1, len(t))
    add(at, (n*.45+np.sin(2*np.pi*1700*t)*.55)*np.exp(-t*95), gain, pan)

def whoosh(at, duration=.42, pan=0):
    t = np.arange(int(SR*duration))/SR
    n = rng.normal(0, 1, len(t))
    smooth = np.convolve(n, np.ones(17)/17, mode='same')
    add(at, smooth*np.sin(np.pi*t/duration)**2, .65, pan)

for i in range(36):
    beat = .5*i
    kick(beat, .46 if i%4 else .68)
    if i%2: click(beat, .21)
    click(beat+.25, .055, .5 if i%2 else -.5)
    t=np.arange(int(SR*.37))/SR
    frequency=[55,55,65.406,49][(i//4)%4]
    bass=(np.sin(2*np.pi*frequency*t)+.2*np.sin(2*np.pi*frequency*2*t))
    add(beat,bass*np.minimum(t/.008,1)*np.exp(-t*9),.16)

for at in [0,2.45,3.05,5.55,6.0,8.7,9.25,11.65,13.0,14.35,15.65,16.2,16.7,17.2,17.65]:
    whoosh(at,.32, .35 if at%1>.4 else -.35)
for at in [3.5,4.5,5.5,6.25,6.75,10.35,12.65,13.5,14.5,15.4,16.5,17,17.5,18.15]:
    click(at,.45)
kick(18,.8)
t=np.arange(int(SR*2))/SR
chord=sum(np.sin(2*np.pi*f*t) for f in [110,164.814,220,261.626])/4
add(18,chord*(1-np.exp(-t*18))*np.exp(-t*2),.3)
mix *= np.minimum(np.arange(len(mix))/SR/.008,1)[:,None]
mix *= np.minimum((len(mix)-1-np.arange(len(mix)))/SR/.3,1)[:,None]
mix = np.tanh(mix*1.05)
mix *= .86/max(np.max(np.abs(mix)), .01)
out=Path(__file__).resolve().parent/'assets'/'soundtrack.wav'
with wave.open(str(out),'wb') as f:
    f.setnchannels(2); f.setsampwidth(2); f.setframerate(SR)
    f.writeframes((mix*32767).astype('<i2').tobytes())
print(out)
