const $ = (id) => document.getElementById(id);
const talkBtn = $("talk");
const statusEl = $("status");
const transcript = $("transcript");
const textForm = $("text-form");
const textInput = $("text-input");

let ws = null;
let ctx = null;
let micStream = null;
let micNode = null;
let nextPlayTime = 0;
let playing = [];
let bubble = { role: null, el: null };

function setStatus(text, state = "") {
  statusEl.textContent = text;
  document.body.dataset.state = state;
}

function addText(role, text) {
  if (bubble.role !== role || !bubble.el) {
    const el = document.createElement("div");
    el.className = `msg ${role}`;
    el.innerHTML = `<span class="who">${role === "user" ? "നിങ്ങൾ" : "Gemini"}</span><p></p>`;
    transcript.appendChild(el);
    bubble = { role, el: el.querySelector("p") };
  }
  bubble.el.textContent += text;
  transcript.scrollTop = transcript.scrollHeight;
}

function playPcm(buf) {
  const pcm = new Int16Array(buf);
  const audio = ctx.createBuffer(1, pcm.length, 24000);
  const ch = audio.getChannelData(0);
  for (let i = 0; i < pcm.length; i++) ch[i] = pcm[i] / 32768;
  const src = ctx.createBufferSource();
  src.buffer = audio;
  src.connect(ctx.destination);
  nextPlayTime = Math.max(ctx.currentTime, nextPlayTime);
  src.start(nextPlayTime);
  nextPlayTime += audio.duration;
  playing.push(src);
  src.onended = () => (playing = playing.filter((s) => s !== src));
  setStatus("Gemini സംസാരിക്കുന്നു…", "speaking");
}

function stopPlayback() {
  playing.forEach((s) => { try { s.stop(); } catch {} });
  playing = [];
  nextPlayTime = 0;
}

async function start() {
  talkBtn.disabled = true;
  setStatus("ബന്ധിപ്പിക്കുന്നു…", "connecting");
  try {
    ctx = new AudioContext();
    await ctx.audioWorklet.addModule("/static/mic-processor.js");
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true, autoGainControl: true },
    });
  } catch (e) {
    setStatus("മൈക്ക് അനുമതി ആവശ്യമാണ് (microphone permission needed)", "error");
    await cleanup();
    return;
  }

  const proto = location.protocol === "https:" ? "wss" : "ws";
  ws = new WebSocket(`${proto}://${location.host}/ws?voice=${encodeURIComponent($("voice").value)}`);
  ws.binaryType = "arraybuffer";

  ws.onmessage = (ev) => {
    if (ev.data instanceof ArrayBuffer) return playPcm(ev.data);
    const msg = JSON.parse(ev.data);
    if (msg.type === "ready") {
      const source = ctx.createMediaStreamSource(micStream);
      micNode = new AudioWorkletNode(ctx, "mic-processor");
      micNode.port.onmessage = (e) => ws?.readyState === WebSocket.OPEN && ws.send(e.data);
      source.connect(micNode);
      talkBtn.disabled = false;
      talkBtn.classList.add("live");
      talkBtn.querySelector(".label").textContent = "നിർത്തുക · Stop";
      textInput.disabled = false;
      setStatus("കേൾക്കുന്നു… മലയാളത്തിൽ സംസാരിക്കൂ", "listening");
    } else if (msg.type === "user" || msg.type === "gemini") {
      addText(msg.type, msg.text);
    } else if (msg.type === "interrupted") {
      stopPlayback();
      bubble.role = null;
    } else if (msg.type === "turn_complete") {
      bubble.role = null;
      setStatus("കേൾക്കുന്നു… മലയാളത്തിൽ സംസാരിക്കൂ", "listening");
    } else if (msg.type === "error") {
      setStatus(`പിശക്: ${msg.error}`, "error");
    }
  };
  ws.onclose = () => {
    if (document.body.dataset.state !== "error") setStatus("വിച്ഛേദിച്ചു · Disconnected", "");
    cleanup();
  };
}

async function cleanup() {
  micNode?.disconnect();
  micNode = null;
  micStream?.getTracks().forEach((t) => t.stop());
  micStream = null;
  stopPlayback();
  if (ctx) { try { await ctx.close(); } catch {} }
  ctx = null;
  if (ws && ws.readyState <= WebSocket.OPEN) ws.close();
  ws = null;
  talkBtn.disabled = false;
  talkBtn.classList.remove("live");
  talkBtn.querySelector(".label").textContent = "സംസാരിക്കാൻ തുടങ്ങുക · Start";
  textInput.disabled = true;
  bubble.role = null;
}

talkBtn.addEventListener("click", () => (ws ? cleanup().then(() => setStatus("നിർത്തി · Stopped")) : start()));

textForm.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = textInput.value.trim();
  if (!text || ws?.readyState !== WebSocket.OPEN) return;
  bubble.role = null;
  addText("user", text);
  bubble.role = null;
  ws.send(JSON.stringify({ type: "text", text }));
  textInput.value = "";
});
