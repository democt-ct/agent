window.speechModule = (function () {
  let currentAudioUrl = "";

  function getSpeechMode() {
    return state.speechMode === "tts" ? "tts" : "browser";
  }

  function persistSpeechMode(mode) {
    try { localStorage.setItem("agentTesterSpeechMode", mode); } catch (_) {}
  }

  function updateSpeechModeButtons() {
    const mode = getSpeechMode();
    document.querySelectorAll("[data-speech-mode]").forEach((button) => {
      const active = button.dataset.speechMode === mode;
      button.classList.toggle("active", active);
      button.setAttribute("aria-pressed", String(active));
    });
    const playBtn = document.getElementById("playAnswerBtn");
    if (playBtn) playBtn.textContent = mode === "tts" ? "用 TTS 播报" : "播放播报";
  }

  function setSpeechMode(mode) {
    state.speechMode = mode === "tts" ? "tts" : "browser";
    persistSpeechMode(state.speechMode);
    updateSpeechModeButtons();
    setStatus("speechStatus", state.speechMode === "tts" ? "当前使用后端 TTS。" : "当前使用浏览器语音合成。", false);
  }

  function revokeAudioUrl() {
    if (currentAudioUrl) {
      URL.revokeObjectURL(currentAudioUrl);
      currentAudioUrl = "";
    }
  }

  function stopAnswerPlayback() {
    const audioPlayer = document.getElementById("answerAudioPlayer");
    if (audioPlayer) {
      audioPlayer.pause();
      audioPlayer.currentTime = 0;
      audioPlayer.removeAttribute("src");
      audioPlayer.load();
    }
    revokeAudioUrl();
    if ("speechSynthesis" in window) window.speechSynthesis.cancel();
    setStatus("speechStatus", "已停止播报。", false);
  }

  function decodeAudioBase64(base64Text, mimeType) {
    const binary = atob(base64Text);
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return new Blob([bytes], { type: mimeType || "audio/mpeg" });
  }

  async function playBrowserSpeech(text, sourceLabel = "回答") {
    if (!("speechSynthesis" in window)) throw new Error("当前浏览器不支持语音合成。");
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = "zh-CN";
    utterance.rate = 1;
    utterance.pitch = 1;
    utterance.volume = 1;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(utterance);
    setStatus("speechStatus", `${sourceLabel} 已开始浏览器播报。`, false);
    setOutput("浏览器播报已输出", { source: sourceLabel, mode: "browser_speech_synthesis" });
  }

  async function playBackendSpeech(text, sourceLabel = "回答") {
    const data = await request("/api/v1/mcp/agent/speech", {
      method: "POST",
      body: JSON.stringify({ text, response_format: "mp3" }),
    });
    const audioPlayer = document.getElementById("answerAudioPlayer");
    const audioBlob = decodeAudioBase64(data.audio_base64, data.mime_type);
    currentAudioUrl = URL.createObjectURL(audioBlob);
    if (audioPlayer) {
      audioPlayer.src = currentAudioUrl;
      await audioPlayer.play();
    }
    setStatus("speechStatus", `${sourceLabel} 已开始后端 TTS 播报，voice = ${data.voice}。`, false);
    setOutput("后端播报详情", { model: data.model, voice: data.voice, mime_type: data.mime_type, response_format: data.response_format });
  }

  async function playTextAsSpeech(text, sourceLabel = "回答") {
    if (!text || text === "暂无回答") {
      setStatus("speechStatus", `${sourceLabel}没有可播报的内容。`, true);
      return;
    }
    stopAnswerPlayback();
    const mode = getSpeechMode();
    const modeLabel = mode === "tts" ? "后端 TTS" : "浏览器播报";
    setStatus("speechStatus", `正在使用${modeLabel}...`, false);

    if (mode === "browser") {
      try { await playBrowserSpeech(text, sourceLabel); return; } catch (browserError) {
        setStatus("speechStatus", "浏览器播报失败，正在切换到后端 TTS...", false);
        try { await playBackendSpeech(text, sourceLabel); return; } catch (ttsError) {
          setStatus("speechStatus", ttsError.message || browserError.message, true);
          return;
        }
      }
    }
    try { await playBackendSpeech(text, sourceLabel); } catch (backendError) {
      try { await playBrowserSpeech(text, sourceLabel); } catch (browserError) {
        setStatus("speechStatus", backendError.message || browserError.message, true);
      }
    }
  }

  function playAnswerAsSpeech() {
    const answerBoxEl = document.getElementById("answerBox");
    const text = (state.lastSpeechText || answerBoxEl?.textContent || "").trim();
    return playTextAsSpeech(text, "当前回答");
  }

  function init() {
    document.querySelectorAll("[data-speech-mode]").forEach((button) => {
      button.addEventListener("click", () => setSpeechMode(button.dataset.speechMode));
    });
    updateSpeechModeButtons();
    setStatus("speechStatus", state.speechMode === "tts" ? "当前使用后端 TTS。" : "当前使用浏览器语音合成。", false);

    document.getElementById("playAnswerBtn")?.addEventListener("click", playAnswerAsSpeech);
    document.getElementById("stopAnswerBtn")?.addEventListener("click", stopAnswerPlayback);

    const chatTranscript = document.getElementById("chatTranscript");
    if (chatTranscript) {
      chatTranscript.addEventListener("click", async (event) => {
        const speakBtn = event.target.closest(".message-speak-btn");
        if (speakBtn) {
          const index = Number(speakBtn.dataset.messageIndex);
          const message = Number.isInteger(index) ? state.chatMessages[index] : null;
          const text = message ? stripMarkdownMarkers(message.content || "") : "";
          await playTextAsSpeech(String(text || "").trim(), "该消息");
          return;
        }
        const stopBtn = event.target.closest(".message-stop-btn");
        if (stopBtn) stopAnswerPlayback();
      });
    }

    const audioPlayer = document.getElementById("answerAudioPlayer");
    if (audioPlayer) audioPlayer.addEventListener("ended", revokeAudioUrl);
  }

  return { init, playTextAsSpeech, stopAnswerPlayback };
})();
