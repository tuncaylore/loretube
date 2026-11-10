(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const els = {
    body: document.body,
    form: $("inspect-form"),
    urlInput: $("url-input"),
    urlHelp: $("url-help"),
    pasteBtn: $("paste-btn"),
    inspectBtn: $("inspect-btn"),
    videoCard: $("video-card"),
    videoMedia: $("video-media"),
    videoThumb: $("video-thumb"),
    videoTitle: $("video-title"),
    videoUploader: $("video-uploader"),
    videoDuration: $("video-duration"),
    formatTabs: $("format-tabs"),
    qualityPanel: $("quality-panel"),
    qualityNote: $("quality-note"),
    qualityOptions: $("quality-options"),
    formatReason: $("format-reason"),
    downloadBtn: $("download-btn"),
    downloadError: $("download-error"),
    jobCard: $("job-card"),
    jobStateChip: $("job-state-chip"),
    jobFile: $("job-file"),
    stageList: $("stage-list"),
    progressTrack: $("progress-track"),
    progressFill: $("progress-fill"),
    progressPercent: $("progress-percent"),
    progressBytes: $("progress-bytes"),
    metricDownloaded: $("metric-downloaded"),
    metricTotal: $("metric-total"),
    metricSpeed: $("metric-speed"),
    metricEta: $("metric-eta"),
    jobError: $("job-error"),
    jobErrorText: $("job-error-text"),
    jobDownload: $("job-download"),
    jobRetry: $("job-retry"),
    historyBody: $("history-body"),
    historyCount: $("history-count"),
    qrIdle: $("qr-idle"),
    qrActive: $("qr-active"),
    qrActiveStage: $("qr-active-stage"),
    qrReady: $("qr-ready"),
    qrImage: $("qr-image"),
    qrUrl: $("qr-url"),
    qrCopy: $("qr-copy"),
    qrExpiry: $("qr-expiry"),
    qrCopyStatus: $("qr-copy-status"),
    qrError: $("qr-error"),
    qrErrorText: $("qr-error-text"),
    qrDisabled: $("qr-disabled"),
    qrDisabledText: $("qr-disabled-text"),
  };

  const state = {
    video: null,
    mode: null,
    quality: null,
    job: null,
    jobActive: false,
    pollTimer: null,
    pollAttempts: 0,
    inspectController: null,
    lanAvailable: els.body.dataset.lanAvailable === "true",
    ffmpegAvailable: els.body.dataset.ffmpegAvailable === "true",
    thumbFailed: false,
  };

  const MODE_LABELS = { mp3: "MP3", audio: "Yalnızca ses", video: "MP4 video" };
  const STAGE_STATE_LABELS = {
    done: "Tamamlandı",
    active: "Sürüyor",
    pending: "Bekliyor",
    skipped: "Gerekmiyor",
    error: "Hata",
  };
  const STATUS_CHIPS = {
    queued: { text: "Sırada", className: "chip" },
    downloading: { text: "İndiriliyor", className: "chip chip--active" },
    merging: { text: "Birleştiriliyor", className: "chip chip--active" },
    converting: { text: "Dönüştürülüyor", className: "chip chip--active" },
    ready: { text: "Hazır", className: "chip chip--success" },
    error: { text: "Hata", className: "chip chip--error" },
  };

  const numberFormat = new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 });
  const dateFormat = new Intl.DateTimeFormat("tr-TR", {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const dateTimeFormat = new Intl.DateTimeFormat("tr-TR", {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

  function formatBytes(bytes) {
    if (bytes === null || bytes === undefined || Number.isNaN(Number(bytes))) {
      return "Bilinmiyor";
    }
    const value = Number(bytes);
    if (value <= 0) {
      return "0 B";
    }
    const units = ["B", "KB", "MB", "GB", "TB"];
    let scaled = value;
    let index = 0;
    while (scaled >= 1024 && index < units.length - 1) {
      scaled /= 1024;
      index += 1;
    }
    return `${numberFormat.format(scaled)} ${units[index]}`;
  }

  function formatSpeed(bytesPerSecond) {
    if (!bytesPerSecond || bytesPerSecond <= 0) {
      return "Bilinmiyor";
    }
    return `${formatBytes(bytesPerSecond)}/sn`;
  }

  function formatEta(seconds) {
    if (seconds === null || seconds === undefined || Number.isNaN(Number(seconds))) {
      return "Bilinmiyor";
    }
    const total = Math.max(0, Math.round(Number(seconds)));
    if (total === 0) {
      return "Tamamlandı";
    }
    if (total < 60) {
      return `${total} sn`;
    }
    const minutes = Math.floor(total / 60);
    const rest = total % 60;
    if (minutes < 60) {
      return `${minutes} dk ${rest} sn`;
    }
    const hours = Math.floor(minutes / 60);
    return `${hours} sa ${minutes % 60} dk`;
  }

  function formatDate(iso) {
    if (!iso) {
      return "";
    }
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? "" : dateFormat.format(date);
  }

  function formatDateTime(iso) {
    if (!iso) {
      return "";
    }
    const date = new Date(iso);
    return Number.isNaN(date.getTime()) ? "" : dateTimeFormat.format(date);
  }

  function makeIcon(symbolId, size) {
    const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    svg.setAttribute("class", "icon");
    svg.setAttribute("width", String(size || 20));
    svg.setAttribute("height", String(size || 20));
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
    use.setAttribute("href", `#${symbolId}`);
    svg.appendChild(use);
    return svg;
  }

  function setBusy(button, busy, busyLabel) {
    if (busy) {
      if (!button.dataset.defaultLabel) {
        button.dataset.defaultLabel = button.querySelector(".btn__label").textContent;
      }
      button.querySelector(".btn__label").textContent = busyLabel;
      button.classList.add("is-busy");
      button.setAttribute("aria-busy", "true");
    } else {
      if (button.dataset.defaultLabel) {
        button.querySelector(".btn__label").textContent = button.dataset.defaultLabel;
      }
      button.classList.remove("is-busy");
      button.removeAttribute("aria-busy");
    }
  }

  function showUrlError(message) {
    els.urlHelp.textContent = message;
    els.urlHelp.classList.add("helper--error");
    els.urlInput.setAttribute("aria-invalid", "true");
  }

  function clearUrlError() {
    els.urlHelp.textContent = "";
    els.urlHelp.classList.remove("helper--error");
    els.urlInput.removeAttribute("aria-invalid");
  }

  function showDownloadError(message) {
    els.downloadError.textContent = message;
    els.downloadError.hidden = !message;
  }

  function clearDownloadError() {
    els.downloadError.textContent = "";
    els.downloadError.hidden = true;
  }

  function showQrState(name) {
    const states = {
      idle: els.qrIdle,
      active: els.qrActive,
      ready: els.qrReady,
      error: els.qrError,
      disabled: els.qrDisabled,
    };
    Object.entries(states).forEach(([key, element]) => {
      element.hidden = key !== name;
    });
  }

  function updateDownloadEnabled() {
    const section = state.video && state.video.formats ? state.video.formats[state.mode] : null;
    const canStart = Boolean(section && section.available && state.quality) && !state.jobActive;
    els.downloadBtn.disabled = !canStart;
    const label = state.jobActive ? "İşlem sürüyor" : "İndirmeyi başlat";
    els.downloadBtn.querySelector(".btn__label").textContent = label;
  }

  function preferredVideoQuality(qualities) {
    if (!qualities.length) {
      return null;
    }
    const values = qualities.map((item) => item.value);
    for (const candidate of ["720", "1080"]) {
      if (values.includes(candidate)) {
        return candidate;
      }
    }
    const numeric = qualities
      .map((item) => Number(item.value))
      .filter((value) => Number.isFinite(value));
    if (!numeric.length) {
      return qualities[0].value;
    }
    const under = numeric.filter((value) => value <= 1080);
    const chosen = under.length ? Math.max(...under) : Math.max(...numeric);
    return String(chosen);
  }

  function renderVideo() {
    const video = state.video;
    if (!video) {
      return;
    }
    els.videoTitle.textContent = video.title || "Bilinmeyen video";
    if (video.uploader) {
      els.videoUploader.textContent = video.uploader;
      els.videoUploader.hidden = false;
    } else {
      els.videoUploader.textContent = "";
      els.videoUploader.hidden = true;
    }
    if (video.duration_text) {
      els.videoDuration.textContent = video.duration_text;
      els.videoDuration.hidden = false;
    } else {
      els.videoDuration.textContent = "";
      els.videoDuration.hidden = true;
    }

    state.thumbFailed = false;
    if (video.thumbnail) {
      els.videoThumb.src = video.thumbnail;
      els.videoThumb.alt = "";
      els.videoMedia.classList.remove("video-card__media--empty");
    } else {
      els.videoThumb.removeAttribute("src");
      els.videoMedia.classList.add("video-card__media--empty");
    }

    els.videoCard.hidden = false;

    const order = ["mp3", "audio", "video"];
    const firstAvailable = order.find((mode) => video.formats[mode] && video.formats[mode].available);
    if (!firstAvailable) {
      state.mode = null;
      state.quality = null;
      els.qualityOptions.replaceChildren();
      els.formatReason.textContent = "Bu video için indirilebilir bir ses veya görüntü formatı bulunamadı.";
      els.formatReason.hidden = false;
      updateTabs();
      updateDownloadEnabled();
      return;
    }
    setMode(firstAvailable);
  }

  function updateTabs() {
    const tabs = Array.from(els.formatTabs.querySelectorAll(".tab"));
    tabs.forEach((tab) => {
      const mode = tab.dataset.mode;
      const section = state.video && state.video.formats ? state.video.formats[mode] : null;
      const available = Boolean(section && section.available);
      const selected = mode === state.mode;
      tab.setAttribute("aria-selected", selected ? "true" : "false");
      tab.tabIndex = selected ? 0 : -1;
      if (available) {
        tab.removeAttribute("aria-disabled");
        tab.removeAttribute("title");
      } else {
        tab.setAttribute("aria-disabled", "true");
        tab.title = (section && section.reason) || "Bu seçenek bu video için kullanılamıyor.";
      }
    });
    if (state.mode) {
      els.qualityPanel.setAttribute("aria-labelledby", `tab-${state.mode}`);
    }
  }

  function setMode(mode, announceReason) {
    const section = state.video && state.video.formats ? state.video.formats[mode] : null;
    if (!section || !section.available) {
      const reason = (section && section.reason) || "Bu seçenek bu video için kullanılamıyor.";
      els.formatReason.textContent = reason;
      els.formatReason.hidden = false;
      if (announceReason) {
        els.formatReason.focus && els.formatReason.focus();
      }
      return;
    }
    state.mode = mode;
    els.formatReason.hidden = true;
    els.formatReason.textContent = "";
    updateTabs();
    renderQualities();
  }

  function renderQualities() {
    const video = state.video;
    const section = video && video.formats ? video.formats[state.mode] : null;
    els.qualityOptions.replaceChildren();
    if (!section || !section.available) {
      state.quality = null;
      els.qualityNote.textContent = "";
      els.formatReason.textContent = (section && section.reason) || "Bu seçenek kullanılamıyor.";
      els.formatReason.hidden = false;
      updateDownloadEnabled();
      return;
    }

    const qualities = section.qualities || [];
    if (!qualities.length) {
      state.quality = null;
      els.qualityNote.textContent = "";
      els.formatReason.textContent = "Bu tür için kaynakta uygun bir kalite bulunamadı.";
      els.formatReason.hidden = false;
      updateDownloadEnabled();
      return;
    }

    let preferred = null;
    if (state.mode === "mp3") {
      preferred = qualities.some((item) => item.value === "320") ? "320" : qualities[0].value;
    } else if (state.mode === "video") {
      preferred = preferredVideoQuality(qualities);
    } else {
      preferred = qualities[0].value;
    }
    state.quality = preferred;

    if (state.mode === "mp3") {
      els.qualityNote.textContent = state.ffmpegAvailable
        ? "Dönüştürme FFmpeg ile yapılır."
        : "FFmpeg olmadan MP3 üretilemez.";
    } else if (state.mode === "audio") {
      els.qualityNote.textContent = "Kaynaktaki ses akışları.";
    } else {
      els.qualityNote.textContent = "Kaynakta bulunan çözünürlükler.";
    }

    qualities.forEach((quality) => {
      const label = document.createElement("label");
      label.className = "quality-option";
      const input = document.createElement("input");
      input.type = "radio";
      input.name = "quality";
      input.value = quality.value;
      input.id = `quality-${state.mode}-${quality.value}`;
      input.checked = quality.value === state.quality;
      input.addEventListener("change", () => {
        if (input.checked) {
          state.quality = quality.value;
          updateDownloadEnabled();
        }
      });
      const text = document.createElement("span");
      text.textContent = quality.label;
      label.append(input, text);
      els.qualityOptions.append(label);
    });

    updateDownloadEnabled();
  }

  async function inspect() {
    const raw = els.urlInput.value.trim();
    if (!raw) {
      showUrlError("Bir YouTube bağlantısı yapıştırın.");
      els.urlInput.focus();
      return;
    }
    if (state.inspectController) {
      state.inspectController.abort();
    }
    const controller = new AbortController();
    state.inspectController = controller;
    setBusy(els.inspectBtn, true, "İnceleniyor…");
    clearUrlError();
    clearDownloadError();
    els.urlHelp.textContent = "Bağlantı inceleniyor…";
    els.urlHelp.classList.remove("helper--error");

    state.video = null;
    state.mode = null;
    state.quality = null;
    els.videoCard.hidden = true;
    updateDownloadEnabled();

    try {
      const response = await fetch("/api/inspect", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: raw }),
        signal: controller.signal,
      });
      const data = await response.json().catch(() => ({ ok: false, error: "Sunucu yanıtı okunamadı." }));
      if (!response.ok || !data.ok) {
        showUrlError(data.error || "Bağlantı incelenemedi.");
        return;
      }
      state.video = data.video;
      els.urlHelp.textContent = "";
      els.urlHelp.classList.remove("helper--error");
      renderVideo();
    } catch (error) {
      if (error.name === "AbortError") {
        return;
      }
      showUrlError("Sunucuya ulaşılamadı. Uygulamanın açık olduğunu kontrol edip yeniden deneyin.");
    } finally {
      if (state.inspectController === controller) {
        state.inspectController = null;
        setBusy(els.inspectBtn, false);
      }
    }
  }

  async function startDownload(override) {
    const selection = override || {
      url: state.video ? state.video.url : null,
      mode: state.mode,
      quality: state.quality,
    };
    if (!selection.url || !selection.mode || !selection.quality) {
      return;
    }
    if (state.pollTimer) {
      clearTimeout(state.pollTimer);
      state.pollTimer = null;
    }
    state.jobActive = true;
    els.downloadBtn.disabled = true;
    setBusy(els.downloadBtn, true, "Başlatılıyor…");
    clearDownloadError();
    els.jobRetry.hidden = true;

    try {
      const response = await fetch("/api/download", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(selection),
      });
      const data = await response.json().catch(() => ({ ok: false, error: "Sunucu yanıtı okunamadı." }));
      if (!response.ok || !data.ok) {
        state.jobActive = false;
        showDownloadError(data.error || "İndirme başlatılamadı.");
        return;
      }
      state.job = data.job;
      state.pollAttempts = 0;
      renderJob(data.job);
      renderQr(data.job);
      els.jobCard.hidden = false;
      schedulePoll();
    } catch (error) {
      state.jobActive = false;
      showDownloadError("Sunucuya ulaşılamadı. İndirme başlatılamadı.");
    } finally {
      setBusy(els.downloadBtn, false);
      updateDownloadEnabled();
    }
  }

  function schedulePoll() {
    if (state.pollTimer) {
      clearTimeout(state.pollTimer);
    }
    state.pollTimer = setTimeout(pollJob, 1000);
  }

  async function pollJob() {
    if (!state.job || !state.job.id) {
      return;
    }
    const jobId = state.job.id;
    try {
      const response = await fetch(`/api/jobs/${jobId}`);
      const data = await response.json().catch(() => ({ ok: false, error: "Sunucu yanıtı okunamadı." }));
      if (!response.ok || !data.ok) {
        state.pollAttempts += 1;
        if (state.pollAttempts >= 3) {
          state.jobActive = false;
          els.jobErrorText.textContent = data.error || "İş durumu alınamadı.";
          els.jobError.hidden = false;
          updateDownloadEnabled();
          return;
        }
        schedulePoll();
        return;
      }
      state.pollAttempts = 0;
      state.job = data.job;
      renderJob(data.job);
      renderQr(data.job);

      if (data.job.status === "ready" || data.job.status === "error") {
        state.jobActive = false;
        updateDownloadEnabled();
        if (data.job.status === "ready") {
          loadHistory();
        }
        return;
      }
      schedulePoll();
    } catch (error) {
      state.pollAttempts += 1;
      if (state.pollAttempts >= 5) {
        state.jobActive = false;
        els.jobErrorText.textContent = "Sunucuya ulaşılamıyor. Bağlantıyı kontrol edip yeniden deneyin.";
        els.jobError.hidden = false;
        updateDownloadEnabled();
        return;
      }
      schedulePoll();
    }
  }

  function renderJob(job) {
    if (!job) {
      return;
    }
    els.jobCard.hidden = false;
    els.jobFile.textContent = [job.title, job.mode_label, job.quality_label].filter(Boolean).join(", ");

    const chip = STATUS_CHIPS[job.status] || STATUS_CHIPS.queued;
    els.jobStateChip.textContent = chip.text;
    els.jobStateChip.className = chip.className;

    els.stageList.replaceChildren();
    (job.stages || []).forEach((stage) => {
      const item = document.createElement("li");
      item.className = `stage stage--${stage.state}`;
      const label = document.createElement("span");
      label.className = "stage__label";
      label.textContent = stage.label;
      const stageState = document.createElement("span");
      stageState.className = "stage__state";
      stageState.textContent = STAGE_STATE_LABELS[stage.state] || "";
      item.append(label, stageState);
      els.stageList.append(item);
    });

    const hasPercent = typeof job.percent === "number" && Number.isFinite(job.percent);
    const progress = els.progressTrack.parentElement;
    if (hasPercent) {
      progress.classList.remove("is-indeterminate");
      const percent = Math.max(0, Math.min(100, job.percent));
      els.progressFill.style.transform = `scaleX(${percent / 100})`;
      els.progressPercent.textContent = `${Math.round(percent)}%`;
      els.progressTrack.setAttribute("aria-valuenow", String(Math.round(percent)));
      els.progressTrack.removeAttribute("aria-valuetext");
    } else {
      progress.classList.add("is-indeterminate");
      els.progressFill.style.transform = "";
      els.progressPercent.textContent = job.status === "ready" ? "100%" : "Hesaplanıyor";
      els.progressTrack.removeAttribute("aria-valuenow");
      els.progressTrack.setAttribute("aria-valuetext", "Toplam boyut bilinmiyor");
    }

    if (job.total_bytes && job.downloaded_bytes !== null && job.downloaded_bytes !== undefined) {
      els.progressBytes.textContent = `${formatBytes(job.downloaded_bytes)} / ${formatBytes(job.total_bytes)}`;
    } else if (job.downloaded_bytes) {
      els.progressBytes.textContent = `${formatBytes(job.downloaded_bytes)} indirildi`;
    } else if (job.total_bytes) {
      els.progressBytes.textContent = `Toplam ${formatBytes(job.total_bytes)}`;
    } else {
      els.progressBytes.textContent = "Toplam boyut bilinmiyor";
    }

    els.metricDownloaded.textContent = job.downloaded_bytes
      ? formatBytes(job.downloaded_bytes)
      : "Bilinmiyor";
    els.metricTotal.textContent = job.total_bytes || job.size ? formatBytes(job.total_bytes || job.size) : "Bilinmiyor";
    els.metricSpeed.textContent = job.status === "ready" ? "Tamamlandı" : formatSpeed(job.speed);
    els.metricEta.textContent = job.status === "ready" ? "Tamamlandı" : formatEta(job.eta);

    if (job.status === "error" && job.error) {
      els.jobErrorText.textContent = job.error;
      els.jobError.hidden = false;
    } else {
      els.jobError.hidden = true;
    }

    if (job.status === "ready" && job.download_url) {
      els.jobDownload.href = job.download_url;
      els.jobDownload.hidden = false;
      els.jobRetry.hidden = true;
    } else if (job.status === "error") {
      els.jobDownload.hidden = true;
      els.jobRetry.hidden = false;
    } else {
      els.jobDownload.hidden = true;
      els.jobRetry.hidden = true;
    }
  }

  function renderQr(job) {
    if (!job) {
      showQrState(state.lanAvailable ? "idle" : "disabled");
      return;
    }
    if (job.status === "ready") {
      if (job.qr && job.qr.available) {
        const cacheBust = job.finished_at ? encodeURIComponent(job.finished_at) : Date.now();
        els.qrImage.src = `${job.qr.image}?v=${cacheBust}`;
        els.qrImage.alt = `Telefonda indirmek için QR kod: ${job.title}`;
        els.qrUrl.value = job.qr.url;
        const expiry = formatDateTime(job.qr.expires_at);
        els.qrExpiry.textContent = expiry
          ? `Bağlantı ${expiry} tarihine kadar geçerli.`
          : "Bağlantı sürelidir.";
        showQrState("ready");
      } else {
        els.qrDisabledText.textContent =
          (job.qr && job.qr.reason) || "Yerel ağ adresi bulunamadı. Telefon aktarımı devre dışı.";
        showQrState("disabled");
      }
      return;
    }
    if (job.status === "error") {
      els.qrErrorText.textContent = job.error || "İşlem başarısız oldu.";
      showQrState("error");
      return;
    }
    if (!state.lanAvailable) {
      showQrState("disabled");
      return;
    }
    const percentText = typeof job.percent === "number" ? `, %${Math.round(job.percent)}` : "";
    els.qrActiveStage.textContent = `${job.stage_label}${percentText}`;
    showQrState("active");
  }

  function announceCopy(message) {
    els.qrCopyStatus.textContent = message;
    window.setTimeout(() => {
      els.qrCopyStatus.textContent = "";
    }, 3000);
  }

  async function copyQrLink() {
    const value = els.qrUrl.value;
    if (!value) {
      return;
    }
    try {
      await navigator.clipboard.writeText(value);
      announceCopy("Bağlantı kopyalandı.");
      return;
    } catch (error) {
      els.qrUrl.select();
      try {
        document.execCommand("copy");
        announceCopy("Bağlantı kopyalandı.");
        return;
      } catch (fallbackError) {
        announceCopy("Bağlantı kopyalanamadı. Bağlantıyı elle seçin.");
      }
    }
  }

  async function pasteFromClipboard() {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        els.urlInput.value = text.trim();
        clearUrlError();
      }
      els.urlInput.focus();
    } catch (error) {
      els.urlInput.focus();
      showUrlError("Pano okunamadı. Bağlantıyı Ctrl+V ile yapıştırın.");
    }
  }

  function createStateBlock(title, text, actionLabel, actionHandler) {
    const block = document.createElement("div");
    block.className = "state";
    const heading = document.createElement("p");
    heading.className = "state__title";
    heading.textContent = title;
    const body = document.createElement("p");
    body.className = "state__text";
    body.textContent = text;
    block.append(heading, body);
    if (actionLabel && actionHandler) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "btn btn--quiet btn--small";
      button.textContent = actionLabel;
      button.addEventListener("click", actionHandler);
      block.append(button);
    }
    return block;
  }

  function renderHistorySkeleton() {
    els.historyCount.textContent = "";
    const wrap = document.createElement("div");
    wrap.className = "skeleton";
    wrap.setAttribute("aria-hidden", "true");
    for (let index = 0; index < 3; index += 1) {
      const row = document.createElement("div");
      row.className = "skeleton__row";
      wrap.append(row);
    }
    els.historyBody.replaceChildren(wrap);
    const sr = document.createElement("p");
    sr.className = "visually-hidden";
    sr.setAttribute("role", "status");
    sr.textContent = "Geçmiş yükleniyor…";
    els.historyBody.append(sr);
  }

  function renderHistoryEmpty() {
    els.historyCount.textContent = "";
    const block = createStateBlock(
      "Henüz indirme yok",
      "İlk indirmeniz tamamlandığında burada küçük resmi, formatı ve tekrar indirme bağlantısıyla listelenir.",
      null,
      null
    );
    const icon = makeIcon("i-history", 24);
    block.prepend(icon);
    els.historyBody.replaceChildren(block);
  }

  function renderHistoryError(message) {
    els.historyCount.textContent = "";
    const block = createStateBlock(
      "Geçmiş yüklenemedi",
      message || "Sunucuya ulaşılamadı. Uygulamanın açık olduğunu kontrol edip yeniden deneyin.",
      "Yeniden dene",
      loadHistory
    );
    els.historyBody.replaceChildren(block);
  }

  function makeThumbnail(item) {
    if (item.thumbnail) {
      const img = document.createElement("img");
      img.className = "history__thumb";
      img.src = item.thumbnail;
      img.alt = "";
      img.width = 96;
      img.height = 54;
      img.loading = "lazy";
      img.addEventListener("error", () => {
        const fallback = makeThumbFallback(item.title);
        if (img.parentElement) {
          img.replaceWith(fallback);
        }
      });
      return img;
    }
    return makeThumbFallback(item.title);
  }

  function makeThumbFallback(title) {
    const span = document.createElement("span");
    span.className = "history__thumb history__thumb--fallback";
    span.setAttribute("aria-hidden", "true");
    span.textContent = (title || "T").trim().charAt(0).toUpperCase();
    return span;
  }

  function renderHistoryList(items) {
    els.historyCount.textContent = `${items.length} kayıt`;
    const list = document.createElement("ul");
    list.className = "history__list";
    items.forEach((item) => {
      const row = document.createElement("li");
      row.className = "history__item";

      row.append(makeThumbnail(item));

      const info = document.createElement("div");
      info.className = "history__info";
      const title = document.createElement("p");
      title.className = "history__title";
      title.textContent = item.title || "Bilinmeyen video";
      const meta = document.createElement("p");
      meta.className = "history__meta";
      const parts = [item.mode_label, item.quality_label, formatBytes(item.size), formatDate(item.finished_at)];
      meta.textContent = parts.filter(Boolean).join(", ");
      info.append(title, meta);
      row.append(info);

      if (item.available && item.download_url) {
        const link = document.createElement("a");
        link.className = "btn btn--quiet btn--small history__action";
        link.href = item.download_url;
        link.textContent = "Bilgisayara indir";
        row.append(link);
      } else {
        const note = document.createElement("span");
        note.className = "history__meta history__action";
        note.textContent = "Dosya silinmiş";
        row.append(note);
      }
      list.append(row);
    });
    els.historyBody.replaceChildren(list);
  }

  async function loadHistory() {
    renderHistorySkeleton();
    try {
      const response = await fetch("/api/history");
      const data = await response.json().catch(() => ({ ok: false, error: "Sunucu yanıtı okunamadı." }));
      if (!response.ok || !data.ok) {
        renderHistoryError(data.error || "Geçmiş yüklenemedi.");
        return;
      }
      const items = Array.isArray(data.items) ? data.items : [];
      if (!items.length) {
        renderHistoryEmpty();
        return;
      }
      renderHistoryList(items);
    } catch (error) {
      renderHistoryError("Sunucuya ulaşılamadı. Uygulamanın açık olduğunu kontrol edip yeniden deneyin.");
    }
  }

  function onTabKeydown(event) {
    const tabs = Array.from(els.formatTabs.querySelectorAll(".tab"));
    const currentIndex = tabs.indexOf(document.activeElement);
    if (currentIndex < 0) {
      return;
    }
    let nextIndex = null;
    if (event.key === "ArrowRight") {
      nextIndex = (currentIndex + 1) % tabs.length;
    } else if (event.key === "ArrowLeft") {
      nextIndex = (currentIndex - 1 + tabs.length) % tabs.length;
    } else if (event.key === "Home") {
      nextIndex = 0;
    } else if (event.key === "End") {
      nextIndex = tabs.length - 1;
    }
    if (nextIndex !== null) {
      event.preventDefault();
      tabs[nextIndex].focus();
    }
  }

  els.form.addEventListener("submit", (event) => {
    event.preventDefault();
    inspect();
  });

  els.urlInput.addEventListener("input", () => {
    clearUrlError();
    els.urlHelp.textContent = "";
  });

  els.pasteBtn.addEventListener("click", pasteFromClipboard);
  els.downloadBtn.addEventListener("click", () => startDownload());
  els.qrCopy.addEventListener("click", copyQrLink);
  els.jobRetry.addEventListener("click", () => {
    if (state.job) {
      startDownload({
        url: state.job.url || (state.video ? state.video.url : null),
        mode: state.job.mode,
        quality: state.job.quality,
      });
    }
  });

  els.formatTabs.addEventListener("click", (event) => {
    const tab = event.target.closest(".tab");
    if (!tab) {
      return;
    }
    if (tab.getAttribute("aria-disabled") === "true") {
      setMode(tab.dataset.mode, true);
      return;
    }
    setMode(tab.dataset.mode);
  });

  els.formatTabs.addEventListener("keydown", onTabKeydown);

  els.videoThumb.addEventListener("error", () => {
    if (state.thumbFailed) {
      return;
    }
    state.thumbFailed = true;
    els.videoMedia.classList.add("video-card__media--empty");
  });

  els.qrImage.addEventListener("error", () => {
    els.qrErrorText.textContent = "QR görseli yüklenemedi. Sayfayı yenileyip yeniden deneyin.";
    showQrState("error");
  });

  if (!state.lanAvailable) {
    showQrState("disabled");
  } else {
    showQrState("idle");
  }

  loadHistory();
})();
