# Launch video

`sagu-launch.mp4` (about 38 seconds, 1280x720, 30 fps) is a deterministic render of `scene.html`: every frame is a pure
function of time, captured with headless Chromium and encoded with ffmpeg. The voiceover is synthesized locally with
[Piper](https://github.com/rhasspy/piper) (voice `en_US-lessac-high`) from `script.txt`.

Rebuild: synthesize each line of `script.txt` with Piper (`--length-scale 0.88 --noise-scale 0.8 --noise-w-scale 0.95`) to `0.wav`..`5.wav`, run `python3 timeline.py <folder>` (writes
`timeline.js` and `voice.wav`), `python3 music.py` (synthesizes `music.wav` and ducks it under the voice into `mix.wav`), render frames with `node render.js <frames-folder>`, then
`ffmpeg -framerate 30 -i <frames>/f%05d.jpg -i mix.wav -c:v libx264 -pix_fmt yuv420p -c:a aac sagu-launch.mp4`.
