// RIVA — Advanced Real-Time Voice Assistant Frontend Engine

let micStream = null;
let inputAudioCtx = null;
let outputAudioCtx = null;
let masterGainNode = null;
let micNode = null;
let ws = null;
let isConnected = false;
let isIntentionalDisconnect = false;
let isMuted = false;

// Assistant State: 'IDLE' | 'LISTENING' | 'THINKING' | 'PLAYING'
let currentState = 'IDLE';

// Audio scheduling & epoch tracking
let clientEpoch = 0;
let nextPlayTime = 0;
let activeSources = [];

// Live Audio Analysers
let micAnalyser = null;
let speakerAnalyser = null;
let micDataArray = null;
let speakerDataArray = null;
let currentVoiceEnergy = 0.0; // Smoothed EMA (0.0 to 1.0)

// Transcript timer
let transcriptTimer = null;

// User Preferences (Persisted in localStorage)
function getStoredVoice() {
  return localStorage.getItem('riva_voice') || 'Aoede';
}

function getStoredLanguage() {
  return localStorage.getItem('riva_language') || 'auto';
}

let userVoice = getStoredVoice();
let userLanguage = getStoredLanguage();

// UI Elements
const btnToggle = document.getElementById('btnToggle');
const btnIcon = document.getElementById('btnIcon');
const btnText = document.getElementById('btnText');
const btnMute = document.getElementById('btnMute');
const muteIcon = document.getElementById('muteIcon');
const identityStack = document.getElementById('identityStack');
const statusDot = document.getElementById('statusDot');
const statusLabel = document.getElementById('statusLabel');
const transcriptBubble = document.getElementById('transcriptBubble');
const waveformBars = document.querySelectorAll('.waveform-bar');
const deviceToast = document.getElementById('deviceToast');
const container = document.getElementById('canvas-container');
const settingsModal = document.getElementById('settingsModal');

function toggleSettingsModal() {
  if (!settingsModal) return;
  const isShown = settingsModal.classList.toggle('show');
  if (isShown) {
    refreshSettingsUI();
  }
}

function refreshSettingsUI() {
  const currentVoice = getStoredVoice();
  const currentLang = getStoredLanguage();
  userVoice = currentVoice;
  userLanguage = currentLang;

  document.querySelectorAll('#voiceOptions .option-pill').forEach(pill => {
    pill.classList.toggle('active', pill.getAttribute('data-voice') === currentVoice);
  });
  document.querySelectorAll('#languageOptions .option-pill').forEach(pill => {
    pill.classList.toggle('active', pill.getAttribute('data-lang') === currentLang);
  });
}

function selectVoice(voice) {
  if (!voice) return;
  userVoice = voice;
  localStorage.setItem('riva_voice', voice);
  refreshSettingsUI();
  showToast(`Voice set to ${voice}`);

  if (isConnected) {
    isIntentionalDisconnect = true;
    disconnect();
    setTimeout(() => {
      isIntentionalDisconnect = false;
      connect();
    }, 400);
  }
}

function selectLanguage(lang) {
  if (!lang) return;
  userLanguage = lang;
  localStorage.setItem('riva_language', lang);
  refreshSettingsUI();
  const labelMap = { auto: 'Auto-detect', hindi: 'Hindi', english: 'English', hinglish: 'Hinglish' };
  showToast(`Language set to ${labelMap[lang] || lang}`);

  if (isConnected) {
    isIntentionalDisconnect = true;
    disconnect();
    setTimeout(() => {
      isIntentionalDisconnect = false;
      connect();
    }, 400);
  }
}

// SVG Vector Icons
const ICONS = {
  mic: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2a3 3 0 0 0-3 3v7a3 3 0 0 0 6 0V5a3 3 0 0 0-3-3Z"/><path d="M19 10v2a7 7 0 0 1-14 0v-2"/><line x1="12" x2="12" y1="19" y2="22"/></svg>`,
  stop: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect width="14" height="14" x="5" y="5" rx="2"/></svg>`,
  micOff: `<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><line x1="2" x2="22" y1="2" y2="22"/><path d="M18.89 13.23A7.12 7.12 0 0 0 19 12v-2"/><path d="M5 10v2a7 7 0 0 0 12 5"/><path d="M15 9.34V5a3 3 0 0 0-5.68-1.33"/><path d="M9 9v3a3 3 0 0 0 5.12 2.12"/><line x1="12" x2="12" y1="19" y2="22"/></svg>`,
};

// ─── OPTIMIZED SHADER (Slightly Reduced Size for Vertical Balance) ───

const rotateGLSL = `
mat4 rotationMatrix(vec3 axis, float angle) {
  axis = normalize(axis);
  float s = sin(angle);
  float c = cos(angle);
  float oc = 1.0 - c;
  return mat4(oc * axis.x * axis.x + c,           oc * axis.x * axis.y - axis.z * s,  oc * axis.z * axis.x + axis.y * s,  0.0,
              oc * axis.x * axis.y + axis.z * s,  oc * axis.y * axis.y + c,           oc * axis.y * axis.z - axis.x * s,  0.0,
              oc * axis.z * axis.x - axis.y * s,  oc * axis.y * axis.z + axis.x * s,  oc * axis.z * axis.z + c,           0.0,
              0.0,                                0.0,                                0.0,                                1.0);
}
vec3 rotate(vec3 v, vec3 axis, float angle) {
  mat4 m = rotationMatrix(axis, angle);
  return (m * vec4(v, 1.0)).xyz;
}
`;

const fresnelGLSL = `
float fresnel(vec3 eye, vec3 normal) {
  return pow(1.0 + dot(eye, normal), 3.2);
}
`;

const vertexShader = `
varying vec2 v_uv;
void main() {
  v_uv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
}
`;

const fragmentShader = `
#define MAX_STEPS 60
uniform float u_time;
uniform float u_aspect;
uniform vec2 u_mouse;
uniform vec3 u_scale;
uniform float u_distortion;
uniform float u_energy;
uniform float u_thinking;
varying vec2 v_uv;

const float PI = 3.14159265358979;

${rotateGLSL}
${fresnelGLSL}

float smin( float a, float b, float k ) {
  float h = clamp( 0.5+0.5*(b-a)/k, 0.0, 1.0 );
  return mix( b, a, h ) - k*h*(1.0-h);
}

float opUnion( float d1, float d2 ) { return min(d1,d2); }

float sdSphere(vec3 p, float r) {
  return length(p) - r;
}

float gyroid(in vec3 p, float t) {
  vec3 scale = u_scale + 1.0;
  p *= scale;
  vec3 p2 = mix(p, p.yzx, u_distortion);
  return dot(sin(p), cos(p2)) / length(scale);
}

float sdf(vec3 p) {
  // Rotate smoothly with accelerated spin during thinking
  vec3 rp = rotate(p, vec3(0.3, 1.0, 0.2), u_time * (0.15 + u_thinking * 0.4));
  float t = (sin(u_time * 0.3 + PI / 2.0) + 1.0) * 0.5;
  
  float sphere = sdSphere(p, 1.0);
  float g = gyroid(rp, t);

  float dist = smin(sphere, g, -0.01) + 0.03;
  float dist2 = smin(sphere, -g, -0.01) + 0.03;

  return opUnion(dist, dist2);
}

vec3 calcNormal(in vec3 p) {
  const float h = 0.0005;
  const vec2 k = vec2(1, -1) * h;
  return normalize( k.xyy * sdf( p + k.xyy ) + 
                    k.yyx * sdf( p + k.yyx ) + 
                    k.yxy * sdf( p + k.yxy ) + 
                    k.xxx * sdf( p + k.xxx ) );
}

void main() {
  vec2 centeredUV = (v_uv - 0.5) * vec2(u_aspect, 1.0);
  centeredUV.y -= 0.02; // Mathematically centers orb at 48% viewport height for even vertical symmetry
  vec3 ray = normalize(vec3(centeredUV, -1.0));

  vec2 m = u_mouse * vec2(u_aspect, 1.0) * 0.04;
  ray = rotate(ray, vec3(1.0, 0.0, 0.0), m.y);
  ray = rotate(ray, vec3(0.0, 1.0, 0.0), -m.x);

  // Scaled camera distance for perfect breathing room in all viewports
  vec3 camPos = vec3(0.0, 0.0, 4.3);
  vec3 rayPos = camPos;
  float totalDist = 0.0;
  float tMax = 5.2;

  for(int i = 0; i < MAX_STEPS; i++) {
    float dist = sdf(rayPos);
    if (dist < 0.0005 || tMax < totalDist) break;
    totalDist += dist;
    rayPos = camPos + totalDist * ray;
  }

  // Pure Deep Black Background
  vec3 color = vec3(0.0, 0.0, 0.0);

  if(totalDist < tMax) {
    vec3 normal = calcNormal(rayPos);
    
    float d = length(rayPos);
    d = smoothstep(0.4, 1.1, d);
    
    // Rich Deep Emerald Glass Gradient
    vec3 deepDarkGreen = vec3(0.01, 0.09, 0.02);
    vec3 richEmerald = vec3(0.12, 0.52, 0.16);
    // Subtle cyan tint during thinking state
    richEmerald = mix(richEmerald, vec3(0.08, 0.45, 0.35), u_thinking);
    
    color = mix(richEmerald, deepDarkGreen, d);
    
    // Fresnel Rim Glow
    float _fresnel = fresnel(ray, normal);
    vec3 rimGlowColor = mix(vec3(0.35, 0.95, 0.40), vec3(0.3, 0.8, 0.9), u_thinking);
    color += rimGlowColor * _fresnel * (0.85 + u_energy * 0.5);

    // Specular Glass Highlights
    vec3 lightDir = normalize(vec3(0.4, 0.8, 1.0));
    vec3 refDir = reflect(-lightDir, normal);
    float spec = pow(max(0.0, dot(refDir, -ray)), 28.0);
    color += vec3(0.7, 1.0, 0.75) * spec * 0.7;

    // Subsurface Energy Glow
    color += vec3(0.04, 0.18, 0.06) * u_energy;
  }

  gl_FragColor = vec4(color, 1.0);
}
`;

// ─── THREE.JS SCENE SETUP ───

let scene, camera, renderer, shaderMaterial, planeMesh;
let mouse = new THREE.Vector2(0, 0);
let targetMouse = new THREE.Vector2(0, 0);

function initRaymarcher() {
  if (!container) return;

  const width = window.innerWidth;
  const height = window.innerHeight;

  scene = new THREE.Scene();
  camera = new THREE.OrthographicCamera(-1, 1, 1, -1, -10, 10);
  camera.position.z = 10;

  renderer = new THREE.WebGLRenderer({ antialias: false, alpha: false, powerPreference: "high-performance" });
  renderer.setSize(width, height);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.0));
  container.appendChild(renderer.domElement);

  shaderMaterial = new THREE.ShaderMaterial({
    uniforms: {
      u_time: { value: 0 },
      u_aspect: { value: width / height },
      u_mouse: { value: new THREE.Vector2(0, 0) },
      u_scale: { value: new THREE.Vector3(5.0, 5.0, 5.0) },
      u_distortion: { value: 0 },
      u_energy: { value: 0 },
      u_thinking: { value: 0 },
    },
    vertexShader: vertexShader,
    fragmentShader: fragmentShader,
    depthWrite: false,
    depthTest: false,
  });

  const planeGeo = new THREE.PlaneGeometry(2, 2);
  planeMesh = new THREE.Mesh(planeGeo, shaderMaterial);
  scene.add(planeMesh);

  window.addEventListener('mousemove', (e) => {
    targetMouse.x = (e.clientX / window.innerWidth) * 2 - 1;
    targetMouse.y = -(e.clientY / window.innerHeight) * 2 + 1;
  });

  window.addEventListener('resize', onWindowResize);

  animateRaymarcher();
}

function onWindowResize() {
  if (!renderer || !shaderMaterial) return;
  const width = window.innerWidth;
  const height = window.innerHeight;
  renderer.setSize(width, height);
  shaderMaterial.uniforms.u_aspect.value = width / height;
}

let simTime = 0.0;
let thinkingWeight = 0.0;

function animateRaymarcher() {
  requestAnimationFrame(animateRaymarcher);

  // 1. Live Audio Energy & FFT / RMS Processing
  let targetEnergy = 0.0;
  let freqBuckets = [0, 0, 0, 0, 0, 0, 0, 0, 0];

  // DEBUG: log state every 2 seconds
  if (!window._lastDebugLog || Date.now() - window._lastDebugLog > 2000) {
    window._lastDebugLog = Date.now();
    console.log('[RIVA DEBUG]', {
      isConnected,
      currentState,
      isMuted,
      hasMicAnalyser: !!micAnalyser,
      hasMicData: !!micDataArray,
      micDataLen: micDataArray ? micDataArray.length : 0,
      hasSpeakerAnalyser: !!speakerAnalyser,
      hasSpeakerData: !!speakerDataArray,
      waveformBarsCount: waveformBars ? waveformBars.length : 0,
    });
  }

  // Always try to read mic RMS when analyser exists (regardless of state)
  if (micAnalyser && micDataArray && !isMuted) {
    micAnalyser.getByteTimeDomainData(micDataArray);
    let sumSquares = 0;
    for (let i = 0; i < micDataArray.length; i++) {
      const sample = (micDataArray[i] - 128) / 128;
      sumSquares += sample * sample;
    }
    const rms = Math.sqrt(sumSquares / micDataArray.length);
    const sensitivity = 14.0;
    const micEnergy = Math.min(1.0, Math.max(0, rms * sensitivity));

    if (currentState !== 'PLAYING') {
      targetEnergy = micEnergy;
      for (let i = 0; i < 9; i++) {
        const centerDistance = Math.abs(i - 4) / 4;
        const shape = 1.0 - centerDistance * 0.35;
        const variation = 0.82 + Math.sin(simTime * 10 + i * 1.7) * 0.18;
        freqBuckets[i] = targetEnergy * 255 * shape * variation;
      }
    }

    // DEBUG: log mic energy periodically
    if (!window._lastMicLog || Date.now() - window._lastMicLog > 2000) {
      window._lastMicLog = Date.now();
      console.log('[RIVA MIC]', { rms: rms.toFixed(4), micEnergy: micEnergy.toFixed(3), currentState });
    }
  }

  if (currentState === 'PLAYING' && speakerAnalyser && speakerDataArray) {
    speakerAnalyser.getByteTimeDomainData(speakerDataArray);
    let sumSquares = 0;
    for (let i = 0; i < speakerDataArray.length; i++) {
      const sample = (speakerDataArray[i] - 128) / 128;
      sumSquares += sample * sample;
    }
    const rms = Math.sqrt(sumSquares / speakerDataArray.length);
    targetEnergy = Math.min(1.0, Math.max(0, rms * 12.0));

    for (let i = 0; i < 9; i++) {
      const centerDistance = Math.abs(i - 4) / 4;
      const shape = 1.0 - centerDistance * 0.35;
      const variation = 0.82 + Math.sin(simTime * 10 + i * 1.7) * 0.18;
      freqBuckets[i] = targetEnergy * 255 * shape * variation;
    }

    // DEBUG: log speaker energy periodically
    if (!window._lastSpkLog || Date.now() - window._lastSpkLog > 2000) {
      window._lastSpkLog = Date.now();
      console.log('[RIVA SPK]', { rms: rms.toFixed(4), energy: targetEnergy.toFixed(3) });
    }
  }

  targetEnergy = Math.min(1.0, targetEnergy);
  currentVoiceEnergy += (targetEnergy - currentVoiceEnergy) * 0.15;

  // Thinking state transition weight
  const targetThinking = currentState === 'THINKING' ? 1.0 : 0.0;
  thinkingWeight += (targetThinking - thinkingWeight) * 0.05;

  // 2. Animate Micro-Waveform
  if (waveformBars && waveformBars.length === 9) {
    for (let i = 0; i < 9; i++) {
      let height = 3;
      if (currentState === 'THINKING') {
        const wave = (Math.sin(simTime * 8.0 + i * 0.7) + 1.0) * 0.5;
        height = Math.round(3 + wave * 6);
        waveformBars[i].classList.toggle('active', height > 4);
      } else if (isConnected || micAnalyser) {
        const normalized = Math.min(1, (freqBuckets[i] || 0) / 180);
        const distFromCenter = Math.abs(4 - i);
        const centerMultiplier = 1.0 - distFromCenter * 0.10;
        height = Math.round(3 + normalized * 20 * centerMultiplier);
        waveformBars[i].classList.toggle('active', normalized > 0.08);
      } else {
        waveformBars[i].classList.remove('active');
      }
      waveformBars[i].style.height = `${height}px`;
    }
  }

  // 3. Steady, graceful rotation
  simTime += 0.005;
  mouse.lerp(targetMouse, 0.03);

  // 4. Update Shader Uniforms
  if (shaderMaterial) {
    const breathing = Math.sin(simTime * 1.2) * 0.035;
    const voicePulse = currentVoiceEnergy * 0.18;
    const baseScale = 5.0 + breathing + voicePulse;

    shaderMaterial.uniforms.u_time.value = simTime;
    shaderMaterial.uniforms.u_scale.value.set(baseScale, baseScale, baseScale);
    shaderMaterial.uniforms.u_distortion.value = (Math.sin(simTime * 0.4) + 1.0) * 0.45 + currentVoiceEnergy * 0.1;
    shaderMaterial.uniforms.u_energy.value = currentVoiceEnergy;
    shaderMaterial.uniforms.u_thinking.value = thinkingWeight;
    shaderMaterial.uniforms.u_mouse.value.copy(mouse);
  }

  renderer.render(scene, camera);
}

// ─── STATE MANAGEMENT & UI UPDATES ───

function updateUIState(state) {
  currentState = state;

  if (identityStack) {
    identityStack.classList.toggle('faded', state !== 'IDLE');
  }

  switch (state) {
    case 'IDLE':
      statusDot.className = 'status-dot idle';
      statusLabel.innerText = 'Ready to listen';
      btnToggle.className = 'btn-action btn-start';
      btnIcon.innerHTML = ICONS.mic;
      btnText.innerText = 'Start Riva';
      btnMute.style.display = 'none';
      btnToggle.disabled = false;
      break;

    case 'LISTENING':
      statusDot.className = 'status-dot';
      statusLabel.innerText = isMuted ? 'Muted' : 'Listening...';
      btnToggle.className = 'btn-action btn-stop';
      btnIcon.innerHTML = ICONS.stop;
      btnText.innerText = 'Stop Riva';
      btnMute.style.display = 'inline-flex';
      btnToggle.disabled = false;
      break;

    case 'THINKING':
      statusDot.className = 'status-dot thinking';
      statusLabel.innerText = 'Thinking...';
      btnToggle.className = 'btn-action btn-stop';
      btnIcon.innerHTML = ICONS.stop;
      btnText.innerText = 'Stop Riva';
      btnMute.style.display = 'inline-flex';
      btnToggle.disabled = false;
      break;

    case 'PLAYING':
      statusDot.className = 'status-dot speaking';
      statusLabel.innerText = 'Riva is speaking';
      btnToggle.className = 'btn-action btn-stop';
      btnIcon.innerHTML = ICONS.stop;
      btnText.innerText = 'Stop Riva';
      btnMute.style.display = 'inline-flex';
      btnToggle.disabled = false;
      break;
  }
}

function showTranscript(text) {
  // Transcripts disabled for pure audio focus
  return;
}

// ─── AUDIO SYSTEM & WEBSOCKET LIFECYCLE ───

if (navigator.mediaDevices && navigator.mediaDevices.ondevicechange !== undefined) {
  navigator.mediaDevices.ondevicechange = () => {
    if (isConnected) showToast('Audio hardware updated');
  };
}

function showToast(text) {
  if (!deviceToast) return;
  deviceToast.innerText = text;
  deviceToast.classList.add('show');
  setTimeout(() => deviceToast.classList.remove('show'), 3000);
}

function toggleMute() {
  if (!micStream) return;
  isMuted = !isMuted;
  micStream.getAudioTracks().forEach(t => t.enabled = !isMuted);

  if (isMuted) {
    btnMute.classList.add('is-muted');
    muteIcon.innerHTML = ICONS.micOff;
    statusLabel.innerText = 'Muted';
  } else {
    btnMute.classList.remove('is-muted');
    muteIcon.innerHTML = ICONS.mic;
    statusLabel.innerText = 'Listening...';
  }
}

// Inlined Zero-Roundtrip AudioWorklet Resampler
const WORKLET_CODE = `
class MicProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.targetSampleRate = 16000;
    this.frameSize = 320;
    this.buffer = new Int16Array(this.frameSize);
    this.bufIndex = 0;
    this.inputSampleRate = sampleRate;
    this.ratio = this.inputSampleRate / this.targetSampleRate;
    this.phase = 0;
  }
  process(inputs) {
    const input = inputs[0][0];
    if (!input || input.length === 0) return true;
    while (this.phase < input.length) {
      const idx = Math.floor(this.phase);
      const frac = this.phase - idx;
      const nextIdx = Math.min(idx + 1, input.length - 1);
      const sample = input[idx] * (1 - frac) + input[nextIdx] * frac;
      const clamped = Math.max(-1.0, Math.min(1.0, sample));
      this.buffer[this.bufIndex++] = clamped < 0 ? clamped * 32768 : clamped * 32767;
      if (this.bufIndex >= this.frameSize) {
        this.port.postMessage(this.buffer.buffer.slice(0));
        this.bufIndex = 0;
      }
      this.phase += this.ratio;
    }
    this.phase -= input.length;
    return true;
  }
}
registerProcessor('mic-processor', MicProcessor);
`;
const workletBlobUrl = URL.createObjectURL(new Blob([WORKLET_CODE], { type: 'application/javascript' }));

async function toggleSession() {
  if (isConnected || ws !== null || currentState !== 'IDLE') {
    disconnect();
  } else {
    await connect();
  }
}

async function connect() {
  btnToggle.disabled = true;
  statusLabel.innerText = 'Connecting...';

  try {
    // Check microphone API availability (requires HTTPS or localhost)
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error(
        'Microphone access requires a secure context. ' +
        'Please open this page via http://localhost:8000 (not 127.0.0.1 or an IP address).'
      );
    }

    // 1. Acquire mic stream first (needs user gesture)
    micStream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
        channelCount: 1
      }
    });

    // 2. Setup input audio context and worklet
    inputAudioCtx = new (window.AudioContext || window.webkitAudioContext)();
    await inputAudioCtx.audioWorklet.addModule('/worklet.js');

    micNode = new AudioWorkletNode(inputAudioCtx, 'mic-processor');
    const sourceNode = inputAudioCtx.createMediaStreamSource(micStream);
    
    micAnalyser = inputAudioCtx.createAnalyser();
    micAnalyser.fftSize = 1024;
    micAnalyser.smoothingTimeConstant = 0.65;
    micDataArray = new Uint8Array(micAnalyser.fftSize);

    // Pull graph actively into audio destination via silent sink
    const micSink = inputAudioCtx.createGain();
    micSink.gain.value = 0.0;

    sourceNode.connect(micAnalyser);
    sourceNode.connect(micNode);
    micNode.connect(micSink);
    micAnalyser.connect(micSink);
    micSink.connect(inputAudioCtx.destination);

    // 3. Setup Output Context (24kHz)
    outputAudioCtx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    masterGainNode = outputAudioCtx.createGain();
    masterGainNode.gain.setValueAtTime(0.85, outputAudioCtx.currentTime);
    
    speakerAnalyser = outputAudioCtx.createAnalyser();
    speakerAnalyser.fftSize = 1024;
    speakerAnalyser.smoothingTimeConstant = 0.65;
    speakerDataArray = new Uint8Array(speakerAnalyser.fftSize);

    masterGainNode.connect(speakerAnalyser);
    speakerAnalyser.connect(outputAudioCtx.destination);

    await Promise.all([
      inputAudioCtx.resume(),
      outputAudioCtx.resume()
    ]);

    nextPlayTime = outputAudioCtx.currentTime;
    clientEpoch = 0;
    isMuted = false;

    // 4. Now connect WebSocket (after audio is fully ready)
    const activeVoice = getStoredVoice();
    const activeLang = getStoredLanguage();
    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${location.host}/ws?voice=${encodeURIComponent(activeVoice)}&language=${encodeURIComponent(activeLang)}`;
    ws = new WebSocket(wsUrl);
    ws.binaryType = 'arraybuffer';

    ws.onopen = () => {
      isConnected = true;
      isIntentionalDisconnect = false;
      btnToggle.disabled = false;
      updateUIState('LISTENING');
      console.log('Connected to Riva Gateway');
    };

    micNode.port.onmessage = (event) => {
      if (ws && ws.readyState === WebSocket.OPEN && !isMuted) {
        ws.send(event.data);
      }
    };

    ws.onmessage = async (event) => {
      let data = event.data;
      if (data instanceof Blob) {
        data = await data.arrayBuffer();
      }
      if (typeof data === 'string') {
        try {
          const msg = JSON.parse(data);
          handleServerEvent(msg);
        } catch (e) {
          console.error('Error parsing JSON event:', e);
        }
      } else if (data instanceof ArrayBuffer) {
        handleIncomingAudio(data);
      }
    };

    ws.onclose = (e) => {
      console.warn('WebSocket closed:', e);
      // Circuit breaker: do NOT auto-reconnect in a fast loop
      // Cleanly teardown audio graph and let the user restart or cooldown
      disconnect();
      if (!isIntentionalDisconnect) {
        statusLabel.innerText = 'Disconnected (Click Start to reconnect)';
      }
    };

    ws.onerror = (err) => {
      console.error('WebSocket Error:', err);
    };

  } catch (err) {
    console.error('Connection failed:', err);
    showToast(err.message);
    btnToggle.disabled = false;
    updateUIState('IDLE');
  }
}

function handleServerEvent(msg) {
  if (msg.type === 'barge_in' || msg.type === 'interrupted') {
    if (msg.epoch) clientEpoch = msg.epoch;
    stopAllAudio();
    updateUIState('LISTENING');
  } else if (msg.type === 'state') {
    if (!isMuted) updateUIState(msg.state);
  } else if (msg.type === 'transcript') {
    if (msg.text) showTranscript(msg.text);
  } else if (msg.type === 'action_card') {
    handleActionCard(msg);
  } else if (msg.type === 'open_url') {
    if (msg.url) {
      try {
        window.open(msg.url, '_blank');
      } catch (e) {
        console.warn('[Riva] Browser window.open blocked:', e);
      }
    }
  } else if (msg.type === 'error') {
    isIntentionalDisconnect = true;
    disconnect();
    const isQuota = (msg.message || '').toLowerCase().includes('quota') || (msg.message || '').toLowerCase().includes('exhausted') || (msg.message || '').toLowerCase().includes('cooldown');
    if (isQuota) {
      statusLabel.innerText = '⚠️ Rate limit reached (Wait ~45s cooldown)';
      showToast(msg.message || '⚠️ Gemini API rate limit reached. Please wait ~45s before retrying.');
    } else {
      showToast(msg.message || 'AI service error');
    }
  }
}

// ─── LIVE ACTION CARD — Pure DOM Injection (No HTML/CSS files touched) ───────

let _rivaActionCardEl = null;
let _rivaCardDismissTimer = null;

function _ensureActionCardStyles() {
  if (document.getElementById('riva-action-card-styles')) return;
  const style = document.createElement('style');
  style.id = 'riva-action-card-styles';
  style.textContent = `
    #riva-action-card {
      position: fixed;
      bottom: 28px;
      right: 28px;
      z-index: 99999;
      min-width: 320px;
      max-width: 420px;
      background: rgba(10, 10, 20, 0.82);
      backdrop-filter: blur(24px) saturate(160%);
      -webkit-backdrop-filter: blur(24px) saturate(160%);
      border: 1px solid rgba(255,255,255,0.10);
      border-radius: 16px;
      padding: 16px 18px;
      box-shadow: 0 8px 40px rgba(0,0,0,0.55), 0 0 0 1px rgba(120,100,255,0.12);
      font-family: -apple-system, 'Inter', 'Segoe UI', sans-serif;
      color: #e8e8f0;
      transform: translateY(20px);
      opacity: 0;
      transition: transform 0.32s cubic-bezier(.22,1,.36,1), opacity 0.28s ease;
      pointer-events: auto;
    }
    #riva-action-card.visible {
      transform: translateY(0);
      opacity: 1;
    }
    #riva-action-card .rac-header {
      display: flex;
      align-items: center;
      gap: 10px;
      margin-bottom: 8px;
    }
    #riva-action-card .rac-icon {
      font-size: 22px;
      line-height: 1;
      flex-shrink: 0;
    }
    #riva-action-card .rac-title {
      font-size: 13.5px;
      font-weight: 600;
      color: #c8c0ff;
      letter-spacing: 0.01em;
      line-height: 1.3;
    }
    #riva-action-card .rac-spinner {
      width: 14px; height: 14px;
      border: 2px solid rgba(180,160,255,0.25);
      border-top-color: #a78bfa;
      border-radius: 50%;
      animation: rac-spin 0.7s linear infinite;
      flex-shrink: 0;
      margin-left: auto;
    }
    @keyframes rac-spin { to { transform: rotate(360deg); } }
    #riva-action-card .rac-subject {
      font-size: 12px;
      color: rgba(255,255,255,0.5);
      margin-bottom: 4px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
    }
    #riva-action-card .rac-preview {
      font-size: 12.5px;
      color: rgba(230,225,255,0.75);
      line-height: 1.5;
      border-left: 2px solid rgba(167,139,250,0.45);
      padding-left: 10px;
      margin-top: 6px;
      word-break: break-word;
    }
    #riva-action-card .rac-bar {
      margin-top: 12px;
      height: 2px;
      border-radius: 2px;
      background: rgba(255,255,255,0.07);
      overflow: hidden;
    }
    #riva-action-card .rac-bar-fill {
      height: 100%;
      border-radius: 2px;
      background: linear-gradient(90deg, #7c3aed, #a78bfa);
      width: 0%;
      transition: width 0.4s ease;
    }
    #riva-action-card.status-done .rac-bar-fill { width: 100%; background: linear-gradient(90deg,#059669,#34d399); }
    #riva-action-card.status-done .rac-title { color: #6ee7b7; }
    #riva-action-card.status-done .rac-spinner { display: none; }
  `;
  document.head.appendChild(style);
}

function _escapeHtml(str) {
  if (!str) return '';
  return String(str).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

function handleActionCard(msg) {
  _ensureActionCardStyles();

  // Create card element if not present
  if (!_rivaActionCardEl) {
    _rivaActionCardEl = document.createElement('div');
    _rivaActionCardEl.id = 'riva-action-card';
    document.body.appendChild(_rivaActionCardEl);
  }

  const card = _rivaActionCardEl;
  const isDone = msg.status === 'done';

  // Automatically attempt opening URL in browser tab on running state
  if (msg.url && !isDone && !msg._hasOpened) {
    msg._hasOpened = true;
    try {
      window.open(msg.url, '_blank');
    } catch (e) {
      console.warn('[Riva] Browser window.open popup blocked:', e);
    }
  }

  // Clear existing dismiss timer if updating same card
  if (_rivaCardDismissTimer) {
    clearTimeout(_rivaCardDismissTimer);
    _rivaCardDismissTimer = null;
  }

  // Build inner HTML
  let inner = `
    <div class="rac-header">
      <span class="rac-icon">${msg.icon || '⚡'}</span>
      <span class="rac-title">${msg.title || ''}</span>
      ${!isDone ? '<span class="rac-spinner"></span>' : '<button onclick="if (_rivaActionCardEl) { _rivaActionCardEl.remove(); _rivaActionCardEl=null; }" style="background:none; border:none; color:rgba(255,255,255,0.45); font-size:14px; cursor:pointer; margin-left:auto; line-height:1; padding:2px 6px;" title="Close">✕</button>'}
    </div>`;

  if (msg.recipient) {
    inner += `<div class="rac-subject" style="color:#a78bfa;">To: ${_escapeHtml(msg.recipient)}</div>`;
  }
  if (msg.subject) {
    inner += `<div class="rac-subject">Subject: ${_escapeHtml(msg.subject)}</div>`;
  }
  if (msg.preview && !msg.result) {
    inner += `<div class="rac-preview">${_escapeHtml(msg.preview)}</div>`;
  }

  // If rich DOM result is present, display scrollable inspection box
  if (msg.result) {
    inner += `
      <div style="margin-top: 8px; max-height: 220px; overflow-y: auto; background: rgba(0,0,0,0.55); border: 1px solid rgba(167,139,250,0.25); border-radius: 8px; padding: 10px 12px; font-family: 'JetBrains Mono', monospace; font-size: 11px; line-height: 1.55; color: #e2e8f0; white-space: pre-wrap; word-break: break-word;">
        ${_escapeHtml(msg.result)}
      </div>`;
  }

  if (msg.url) {
    card.style.cursor = 'pointer';
    card.title = 'Click to open in browser';
    card.onclick = (e) => {
      if (e.target.tagName !== 'A' && e.target.tagName !== 'BUTTON') {
        window.open(msg.url, '_blank');
      }
    };
    let displayHost = msg.url;
    try {
      const u = new URL(msg.url);
      displayHost = u.hostname + (u.pathname.length > 1 ? u.pathname : '');
    } catch (_) {}
    inner += `
      <div style="margin-top: 10px; display: flex; align-items: center; justify-content: space-between; gap: 8px;">
        <span style="font-size: 11px; color: rgba(255,255,255,0.45); font-family: 'JetBrains Mono', monospace; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; max-width: 170px;">${_escapeHtml(displayHost)}</span>
        <a href="${msg.url}" target="_blank" rel="noopener noreferrer" style="display: inline-flex; align-items: center; gap: 5px; padding: 6px 13px; background: linear-gradient(90deg, #10b981, #059669); border: 1px solid rgba(52,211,153,0.6); border-radius: 8px; color: #ffffff; font-size: 12px; font-weight: 700; text-decoration: none; cursor: pointer; box-shadow: 0 2px 10px rgba(16,185,129,0.35); flex-shrink: 0;">
          ↗ Open Tab
        </a>
      </div>`;
  } else {
    card.style.cursor = 'default';
    card.title = '';
    card.onclick = null;
  }

  inner += `<div class="rac-bar"><div class="rac-bar-fill" id="rac-fill"></div></div>`;

  card.innerHTML = inner;
  card.className = isDone ? 'visible status-done' : 'visible';

  // Animate progress bar on running state
  if (!isDone) {
    setTimeout(() => {
      const fill = document.getElementById('rac-fill');
      if (fill) fill.style.width = '65%';
    }, 80);
  }

  // Auto-dismiss after done (extended for rich DOM cards so user can inspect)
  if (isDone) {
    const dismissDelay = msg.result ? 35000 : (msg.url ? 8000 : 4500);
    _rivaCardDismissTimer = setTimeout(() => {
      card.style.opacity = '0';
      card.style.transform = 'translateY(16px)';
      setTimeout(() => {
        if (card.parentNode) card.parentNode.removeChild(card);
        _rivaActionCardEl = null;
      }, 400);
    }, dismissDelay);
  }
}



function handleIncomingAudio(arrayBuffer) {
  if (!outputAudioCtx || arrayBuffer.byteLength < 4) return;

  const dataView = new DataView(arrayBuffer);
  const chunkEpoch = dataView.getUint32(0, false);

  if (chunkEpoch < clientEpoch) return;

  const pcm16Bytes = new Uint8Array(arrayBuffer, 4);
  const int16Array = new Int16Array(pcm16Bytes.buffer, pcm16Bytes.byteOffset, pcm16Bytes.byteLength / 2);
  
  const float32Array = new Float32Array(int16Array.length);
  for (let i = 0; i < int16Array.length; i++) {
    float32Array[i] = int16Array[i] / 32768.0;
  }

  const audioBuffer = outputAudioCtx.createBuffer(1, float32Array.length, 24000);
  audioBuffer.copyToChannel(float32Array, 0);

  const source = outputAudioCtx.createBufferSource();
  source.buffer = audioBuffer;
  source.connect(masterGainNode);

  const now = outputAudioCtx.currentTime;
  const startTime = Math.max(now, nextPlayTime);
  source.start(startTime);
  nextPlayTime = startTime + audioBuffer.duration;

  activeSources.push(source);
  source.onended = () => {
    const idx = activeSources.indexOf(source);
    if (idx !== -1) activeSources.splice(idx, 1);
  };
}

function stopAllAudio() {
  for (const src of activeSources) {
    try {
      src.stop();
      src.disconnect();
    } catch (e) {}
  }
  activeSources = [];
  if (outputAudioCtx) {
    nextPlayTime = outputAudioCtx.currentTime;
  }
}

function disconnect() {
  isIntentionalDisconnect = true;
  isConnected = false;
  isMuted = false;
  stopAllAudio();

  if (ws) {
    ws.onopen = null;
    ws.onmessage = null;
    ws.onerror = null;
    ws.onclose = null;
    try {
      ws.close();
    } catch (e) {}
    ws = null;
  }

  if (micStream) {
    try {
      micStream.getTracks().forEach(t => t.stop());
    } catch (e) {}
    micStream = null;
  }

  if (inputAudioCtx) {
    try {
      inputAudioCtx.close();
    } catch (e) {}
    inputAudioCtx = null;
  }

  if (outputAudioCtx) {
    try {
      outputAudioCtx.close();
    } catch (e) {}
    outputAudioCtx = null;
  }

  updateUIState('IDLE');
}

// Global Keyboard Shortcut: Space to Toggle
window.addEventListener('keydown', (e) => {
  if (e.code === 'Space' && e.target.tagName !== 'INPUT' && e.target.tagName !== 'TEXTAREA') {
    e.preventDefault();
    toggleSession();
  }
});

// Initialize Raymarcher and Preferences on DOM load
window.addEventListener('DOMContentLoaded', () => {
  initRaymarcher();
  refreshSettingsUI();
});
