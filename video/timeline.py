"""Builds timeline.js (scene start times from the voiceover lengths) and voice.wav (the voiceover on one track)."""
import subprocess, sys, json, wave

vo = sys.argv[1]  # folder with 0.wav ... 5.wav
GAP, LEAD, TAIL = 3.1, 0.6, 3.4
durs = []
for i in range(6):
    with wave.open("%s/%d.wav" % (vo, i)) as w:
        durs.append(w.getnframes() / w.getframerate())
starts, t = [], LEAD
for d in durs:
    starts.append(round(t, 3)); t += d + GAP
total = round(starts[-1] + durs[-1] + TAIL, 3)
ends = starts[1:] + [total]
open("timeline.js", "w").write("const T=%s;" % json.dumps({"starts": starts, "ends": ends, "total": total, "durs": durs}))
args = ["ffmpeg", "-y", "-v", "error"]
for i in range(6):
    args += ["-i", "%s/%d.wav" % (vo, i)]
fc = "".join("[%d]adelay=%d|%d,apad[a%d];" % (i, int(starts[i] * 1000), int(starts[i] * 1000), i) for i in range(6))
fc += "".join("[a%d]" % i for i in range(6)) + "amix=inputs=6:normalize=0,atrim=0:%s,highpass=f=90,equalizer=f=3200:t=q:w=1.2:g=1.5,acompressor=threshold=-20dB:ratio=2.5:attack=8:release=120,aecho=0.8:0.5:35:0.12,loudnorm=I=-16:TP=-1.5:LRA=11[out]" % total
subprocess.check_call(args + ["-filter_complex", fc, "-map", "[out]", "-ar", "44100", "voice.wav"])
print(total, starts)
