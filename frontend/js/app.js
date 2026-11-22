// === 1. CENA 3D (THREE.JS + SUPORTE A TOQUE NO CELULAR) ===
const container = document.getElementById('canvas3d');
const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, window.innerWidth / window.innerHeight, 0.1, 1000);

const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
container.appendChild(renderer.domElement);

function ajustarCamera() {
    const aspect = window.innerWidth / window.innerHeight;
    camera.aspect = aspect;
    camera.position.z = aspect < 1 ? Math.max(4.8, 2.85 / aspect) : 2.65;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
}

ajustarCamera();
window.addEventListener('resize', ajustarCamera);

const geoWire = new THREE.IcosahedronGeometry(1.18, 3);
const matWire = new THREE.MeshBasicMaterial({ color: 0x0ea5e9, wireframe: true, transparent: true, opacity: 0.32 });
const brainMesh = new THREE.Mesh(geoWire, matWire);
scene.add(brainMesh);

const partCount = 1200;
const posArray = new Float32Array(partCount * 3);
const colArray = new Float32Array(partCount * 3);
const paletteBlue = [new THREE.Color(0x1d4ed8), new THREE.Color(0x0284c7), new THREE.Color(0x38bdf8), new THREE.Color(0xbae6fd)];

for (let i = 0; i < partCount * 3; i += 3) {
    const r = 1.08 * Math.cbrt(Math.random());
    const theta = Math.random() * 2 * Math.PI;
    const phi = Math.acos(2 * Math.random() - 1);
    posArray[i] = r * Math.sin(phi) * Math.cos(theta);
    posArray[i + 1] = r * Math.sin(phi) * Math.sin(theta);
    posArray[i + 2] = r * Math.cos(phi);
    const c = paletteBlue[Math.floor(Math.random() * paletteBlue.length)];
    colArray[i] = c.r;
    colArray[i + 1] = c.g;
    colArray[i + 2] = c.b;
}

const partGeo = new THREE.BufferGeometry();
partGeo.setAttribute('position', new THREE.BufferAttribute(posArray, 3));
partGeo.setAttribute('color', new THREE.BufferAttribute(colArray, 3));
const particles = new THREE.Points(partGeo, new THREE.PointsMaterial({ size: 0.028, vertexColors: true, transparent: true, opacity: 0.92 }));
scene.add(particles);

const ring = new THREE.Mesh(new THREE.TorusGeometry(1.52, 0.008, 16, 120), new THREE.MeshBasicMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.65 }));
ring.rotation.x = Math.PI / 2.25;
scene.add(ring);

const ring2 = new THREE.Mesh(new THREE.TorusGeometry(1.36, 0.005, 16, 100), new THREE.MeshBasicMaterial({ color: 0x2563eb, transparent: true, opacity: 0.45 }));
ring2.rotation.x = -Math.PI / 3;
ring2.rotation.y = Math.PI / 6;
scene.add(ring2);

let isDragging = false, prevPointer = { x: 0, y: 0 }, rotSpeed = 0.004, pulseScale = 1;

function startDrag(x, y) { isDragging = true; prevPointer = { x, y }; }
function moveDrag(x, y) {
    if (!isDragging) return;
    brainMesh.rotation.y += (x - prevPointer.x) * 0.008;
    brainMesh.rotation.x += (y - prevPointer.y) * 0.008;
    particles.rotation.y += (x - prevPointer.x) * 0.008;
    prevPointer = { x, y };
}
function endDrag() { isDragging = false; }

container.addEventListener('mousedown', (e) => startDrag(e.clientX, e.clientY));
window.addEventListener('mousemove', (e) => moveDrag(e.clientX, e.clientY));
window.addEventListener('mouseup', endDrag);

container.addEventListener('touchstart', (e) => { if (e.touches.length === 1) startDrag(e.touches[0].clientX, e.touches[0].clientY); }, { passive: true });
window.addEventListener('touchmove', (e) => { if (isDragging && e.touches.length === 1) moveDrag(e.touches[0].clientX, e.touches[0].clientY); }, { passive: true });
window.addEventListener('touchend', endDrag);

function animate3D() {
    requestAnimationFrame(animate3D);
    if (!isDragging) {
        brainMesh.rotation.y += rotSpeed;
        brainMesh.rotation.x += rotSpeed * 0.4;
        particles.rotation.y -= rotSpeed * 0.7;
    }
    ring.rotation.z += rotSpeed * 1.5;
    ring2.rotation.z -= rotSpeed * 1.1;
    const s = 1 + Math.sin(Date.now() * 0.004) * 0.03 * pulseScale;
    brainMesh.scale.set(s, s, s);
    renderer.render(scene, camera);
}
animate3D();

// === 2. MENU GAVETA MOBILE & SYNC DE TOGGLES ===
function toggleMenuMobile(abrir) {
    const drawer = document.getElementById('mobileDrawer');
    if (!drawer) return;
    drawer.classList.toggle('hidden', !abrir);
}

function syncToggle(targetId, checked) {
    const el = document.getElementById(targetId);
    if (el) el.checked = checked;
}

// === 3. ÁUDIO, MICROFONE (PC + MOBILE) E ONDA ===
let axelFalando = false, isRecording = false, mediaRecorder, audioChunks = [];
let silenceTimer = null, audioCtxSilencio = null;
let memoriaConversa = [];

const player = document.getElementById('axelAudio');
const btnStop = document.getElementById('btnStopAudio');
const coreBadge = document.getElementById('coreBadge');

player.onplay = () => { axelFalando = true; btnStop.classList.remove('hidden'); };
player.onended = () => { axelFalando = false; btnStop.classList.add('hidden'); };

function setBadgeRecording(ativo) {
    if (!coreBadge) return;
    if (ativo) {
        coreBadge.classList.remove('border-sky-400/45');
        coreBadge.classList.add('border-rose-400', 'shadow-[0_0_45px_rgba(244,63,94,0.55)]');
    } else {
        coreBadge.classList.remove('border-rose-400', 'shadow-[0_0_45px_rgba(244,63,94,0.55)]');
        coreBadge.classList.add('border-sky-400/45');
    }
}

function pararAudio() {
    if (!player.paused) {
        player.pause();
        player.currentTime = 0;
        axelFalando = false;
        btnStop.classList.add('hidden');
        const chatBox = document.getElementById('chatBox');
        chatBox.innerHTML += `<div class="text-xs text-rose-400 bg-rose-950/40 p-2 rounded border border-rose-500/30">🛑 <b>Axel foi interrompido.</b></div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
    }
}

function repetirAudio() {
    if (player.src && player.src !== "") {
        player.currentTime = 0;
        player.play();
    }
}

document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
        if (axelFalando) pararAudio();
        if (isRecording) ativarMicrofoneWhisper('CANCELADO');
        toggleMenuMobile(false);
    }
});

async function ativarMicrofoneWhisper(origem = "MANUAL") {
    if (isRecording) {
        if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
        return;
    }
    if (axelFalando) pararAudio();

    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        const chatBox = document.getElementById('chatBox');
        chatBox.innerHTML += `<div class="text-xs text-amber-300 bg-amber-950/40 p-2 rounded border border-amber-500/30">⚠️ <b>Microfone bloqueado pelo navegador:</b> No celular, acesse pelo link <b>HTTPS</b> do Tailscale (<code>https://...ts.net</code>).</div>`;
        chatBox.scrollTop = chatBox.scrollHeight;
        return;
    }

    isRecording = true;
    audioChunks = [];
    matWire.color.setHex(0xf43f5e);
    matWire.opacity = 0.55;
    rotSpeed = 0.02;
    pulseScale = 2.0;
    setBadgeRecording(true);

    document.getElementById('subStatus').innerText = '🎙️ OUVINDO... (TOQUE EM AXEL PARA ENVIAR)';

    try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        const mimeType = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm' : 'audio/mp4';
        const ext = mimeType.includes('mp4') ? 'm4a' : 'webm';

        mediaRecorder = new MediaRecorder(stream, { mimeType });
        mediaRecorder.ondataavailable = e => { if (e.data.size > 0) audioChunks.push(e.data); };
        mediaRecorder.onstop = async () => {
            isRecording = false;
            setBadgeRecording(false);
            if (audioCtxSilencio) { audioCtxSilencio.close(); audioCtxSilencio = null; }
            clearTimeout(silenceTimer);

            document.getElementById('subStatus').innerText = '🧠 WHISPER TRANSCREVENDO O ÁUDIO...';

            const audioBlob = new Blob(audioChunks, { type: mimeType });
            const formData = new FormData();
            formData.append('audio', audioBlob, `voz.${ext}`);

            try {
                const res = await fetch('/api/transcribe', { method: 'POST', body: formData });
                const data = await res.json();
                if (data.text && data.text.trim().length > 1) {
                    document.getElementById('comandoInput').value = data.text;
                    enviarComando();
                } else {
                    document.getElementById('subStatus').innerText = '❌ ÁUDIO VAZIO OU CANCELADO.';
                    restaurarVisuais();
                }
            } catch (e) {
                restaurarVisuais();
            }
            stream.getTracks().forEach(t => t.stop());
        };

        mediaRecorder.start();

        audioCtxSilencio = new (window.AudioContext || window.webkitAudioContext)();
        const source = audioCtxSilencio.createMediaStreamSource(stream);
        const analyser = audioCtxSilencio.createAnalyser();
        source.connect(analyser);
        const dataArray = new Uint8Array(analyser.frequencyBinCount);

        function checkSilence() {
            if (!isRecording) return;
            requestAnimationFrame(checkSilence);
            analyser.getByteTimeDomainData(dataArray);
            let maxPeak = 0;
            for (let i = 0; i < dataArray.length; i++) {
                if (Math.abs(dataArray[i] - 128) > maxPeak) maxPeak = Math.abs(dataArray[i] - 128);
            }
            if (maxPeak > 10) {
                clearTimeout(silenceTimer);
                silenceTimer = setTimeout(() => {
                    if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
                }, 2500);
            }
        }
        silenceTimer = setTimeout(() => {
            if (mediaRecorder && mediaRecorder.state === "recording") mediaRecorder.stop();
        }, 6000);
        checkSilence();
    } catch (e) {
        isRecording = false;
        restaurarVisuais();
        document.getElementById('subStatus').innerText = '❌ PERMISSÃO DE MICROFONE NEGADA';
    }
}

function restaurarVisuais() {
    setBadgeRecording(false);
    matWire.color.setHex(0x0ea5e9);
    matWire.opacity = 0.32;
    rotSpeed = 0.004;
    pulseScale = 1;
    document.getElementById('subStatus').innerText = '⚡ CLIQUE EM AXEL PARA FALAR';
}

const wCanvas = document.getElementById('waveCanvas');
if (wCanvas) {
    const wCtx = wCanvas.getContext('2d');
    let waveOffset = 0;
    function drawWave() {
        wCtx.clearRect(0, 0, wCanvas.width, wCanvas.height);
        wCtx.beginPath();
        wCtx.strokeStyle = isRecording ? '#fb7185' : '#38bdf8';
        wCtx.lineWidth = 2;
        for (let x = 0; x < wCanvas.width; x++) {
            const y = 22 + Math.sin((x + waveOffset) * 0.06) * (9 * pulseScale) * Math.sin(x * 0.02);
            x === 0 ? wCtx.moveTo(x, y) : wCtx.lineTo(x, y);
        }
        wCtx.stroke();
        waveOffset += 4;
        requestAnimationFrame(drawWave);
    }
    drawWave();
}

// === 4. CONSOLE, MEMÓRIA E HISTÓRICO DO SUPABASE ===
function minimizarConsole() {
    const w = document.getElementById('chatWrapper');
    w.classList.toggle('chat-minimized');
    document.getElementById('btnMin').innerText = w.classList.contains('chat-minimized') ? '[ □ ]' : '[ _ ]';
}

function limparConsole() {
    document.getElementById('chatBox').innerHTML = '<div class="text-xs text-sky-300"><b>AXEL:</b> Contexto neural limpo. Qual é o próximo assunto?</div>';
    memoriaConversa = [];
}

function abrirModalMemoria() { document.getElementById('modalMemoria').classList.remove('hidden'); }
function fecharModalMemoria() { document.getElementById('modalMemoria').classList.add('hidden'); }

async function salvarMemoria() {
    const titulo = document.getElementById('memTitulo').value.trim();
    const conteudo = document.getElementById('memConteudo').value.trim();
    if (!titulo || !conteudo) return;
    await fetch('/api/memory', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ titulo, conteudo })
    });
    document.getElementById('memTitulo').value = '';
    document.getElementById('memConteudo').value = '';
    fecharModalMemoria();
    document.getElementById('chatBox').innerHTML += `<div class="text-xs text-emerald-300 bg-emerald-950/40 p-2 rounded">♾️ Salvo no Obsidian & Supabase!</div>`;
}

async function enviarArquivoWorkspace() {
    const f = document.getElementById('fileInput');
    if (!f.files.length) return;
    const formData = new FormData();
    formData.append('file', f.files[0]);
    await fetch('/api/upload', { method: 'POST', body: formData });
    document.getElementById('chatBox').innerHTML += `<div class="text-xs text-sky-300 bg-sky-950/40 p-2 rounded">📎 Arquivo anexado na workspace!</div>`;
}

let agenteAtual = 'AUTO';
function selecionarAgente(codigo, el, fecharMenu = false) {
    agenteAtual = codigo;
    document.querySelectorAll('.agent-card').forEach(c => c.classList.remove('agent-active'));
    el.classList.add('agent-active');
    document.getElementById('subStatus').innerText = `AGENT: ${codigo} ENGAGED`;

    const badgeMobile = document.getElementById('mobileActiveAgent');
    if (badgeMobile) badgeMobile.innerText = codigo === 'AUTO' ? 'AXEL (AUTO)' : codigo;
    if (fecharMenu) toggleMenuMobile(false);
}

async function carregarHistoricoNuvem() {
    try {
        const res = await fetch('/api/history?session_id=default&limite=12');
        if (!res.ok) return;
        const data = await res.json();
        const mensagens = data.historico || data || [];
        if (!Array.isArray(mensagens) || mensagens.length === 0) return;

        const chatBox = document.getElementById('chatBox');
        chatBox.innerHTML = '';
        mensagens.forEach(m => {
            if (m.role === 'user') {
                chatBox.innerHTML += `<div class="text-xs text-sky-200 bg-blue-950/40 p-2 rounded border border-blue-500/30"><b>VOCÊ:</b> ${m.content}</div>`;
            } else {
                const esp = m.especialista || 'AXEL';
                const modBadge = m.modelo ? `<span class="bg-slate-800 text-sky-300 px-1 rounded text-[9px] ml-1">${m.modelo}</span>` : '';
                chatBox.innerHTML += `<div class="text-xs text-slate-200 bg-sky-950/30 p-2.5 rounded border border-sky-500/30 space-y-1"><div class="text-[10px] text-sky-400 font-bold">AXEL [${esp}] ${modBadge}:</div><div>${marked.parse(m.content || '')}</div></div>`;
            }
            memoriaConversa.push({ role: m.role, content: m.content });
        });
        chatBox.scrollTop = chatBox.scrollHeight;
    } catch (e) {}
}

async function enviarComando() {
    const input = document.getElementById('comandoInput');
    const texto = input.value.trim();
    if (!texto) return;
    input.value = '';
    isRecording = false;
    restaurarVisuais();

    const wrapper = document.getElementById('chatWrapper');
    if (wrapper.classList.contains('chat-minimized')) minimizarConsole();

    const chatBox = document.getElementById('chatBox');
    chatBox.innerHTML += `<div class="text-xs text-sky-200 bg-blue-950/40 p-2 rounded border border-blue-500/30"><b>VOCÊ:</b> ${texto}</div>`;
    chatBox.scrollTop = chatBox.scrollHeight;

    rotSpeed = 0.028;
    pulseScale = 2.4;
    matWire.color.setHex(0x38bdf8);
    matWire.opacity = 0.6;
    document.getElementById('subStatus').innerText = '⚡ PROCESSANDO ORDEM NEURAL...';

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                prompt: texto,
                especialista: agenteAtual,
                conclave: document.getElementById('toggleConclave').checked,
                modo_foco: document.getElementById('toggleFoco').checked,
                voz: document.getElementById('toggleVoz').checked,
                historico: memoriaConversa
            })
        });

        if (!res.ok) throw new Error("Erro de Servidor (HTTP " + res.status + ")");
        const data = await res.json();
        restaurarVisuais();

        if (data.status === "permissao_pendente") {
            chatBox.innerHTML += `<div class="text-xs bg-amber-950/70 p-3 rounded"><b>⚠️ PERMISSÃO:</b><br><code>${data.command}</code><br><button onclick="aprovar('${data.tool_call_id}', true)" class="bg-sky-500 text-black px-2 py-1 rounded mt-2">✅ Autorizar</button> <button onclick="aprovar('${data.tool_call_id}', false)" class="bg-rose-500 text-white px-2 py-1 rounded mt-2">❌ Bloquear</button></div>`;
        } else {
            const badge = data.is_offline ? `<span class="bg-purple-600 text-white px-1 rounded">LOCAL MODE</span>` : "";
            const especialista_ativo = data.especialista_real || agenteAtual;
            chatBox.innerHTML += `<div class="text-xs text-slate-200 bg-sky-950/30 p-2.5 rounded border border-sky-500/30 space-y-1"><div class="text-[10px] text-sky-400 font-bold">AXEL [${especialista_ativo}] ${badge}:</div><div>${marked.parse(data.resposta || data.erro || "Sem resposta.")}</div></div>`;
            if (data.audio_url) { player.src = data.audio_url; player.play(); }

            if (data.resposta) {
                memoriaConversa.push({ role: "user", content: texto });
                memoriaConversa.push({ role: "assistant", content: data.resposta });
                if (memoriaConversa.length > 10) memoriaConversa.splice(0, memoriaConversa.length - 10);
            }
        }
    } catch (erroCritico) {
        restaurarVisuais();
        chatBox.innerHTML += `<div class="text-xs text-rose-300 bg-rose-950/40 p-2.5 rounded border border-rose-500/30"><b>❌ ERRO DE COMUNICAÇÃO:</b> Verifique se o servidor Python está rodando.</div>`;
    }
    chatBox.scrollTop = chatBox.scrollHeight;
}

async function aprovar(id, ok) {
    const res = await fetch('/api/approve', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tool_call_id: id, command: "recuperado_da_ram", approved: ok })
    });
    const data = await res.json();
    document.getElementById('chatBox').innerHTML += `<div class="text-xs text-sky-200 bg-slate-900 p-2 rounded">${marked.parse(data.resposta || 'Concluído.')}</div>`;
}

// === 5. TELEMETRIA ===
setInterval(async () => {
    try {
        const r = await fetch('/api/telemetry');
        const t = await r.json();
        document.getElementById('cpuVal').innerText = `${t.cpu}%`;
        document.getElementById('cpuBar').style.width = `${t.cpu}%`;
        document.getElementById('ramVal').innerText = `${t.ram_percent}% (${t.ram_gb}GB)`;
        document.getElementById('ramBar').style.width = `${t.ram_percent}%`;
        if (t.intel_usage !== undefined) document.getElementById('intelVal').innerText = t.intel_usage ? `${t.intel_usage}%` : 'Standby';
        if (t.nvidia_usage !== undefined) {
            document.getElementById('gpuVal').innerText = `${t.nvidia_usage}% (${t.nvidia_vram}GB / 4.0GB)`;
            document.getElementById('gpuBar').style.width = `${t.nvidia_usage}%`;
        }
        document.getElementById('contadorMem').innerText = `${t.memorias} notas`;

        const mobTel = document.getElementById('mobileTelemetry');
        if (mobTel) mobTel.innerText = `CPU ${t.cpu}% | RAM ${t.ram_percent}%`;

        const netStatus = document.getElementById('netStatus');
        if (!t.online) {
            netStatus.classList.remove('hidden');
            netStatus.innerHTML = "⚠️ OFFLINE: OLLAMA ENGAGED";
            netStatus.classList.replace('text-emerald-400', 'text-amber-400');
        } else {
            netStatus.classList.add('hidden');
        }
    } catch (e) {}
}, 2000);

window.addEventListener('DOMContentLoaded', carregarHistoricoNuvem);