
/* SMARTMOP - camera.js
 * ESP32-CAM -> Flask Railway -> YOLO26 -> Supabase
 * Website mengambil frame terbaru dari backend.
 */

(function (SM) {
  "use strict";

  const $ = (id) => document.getElementById(id);

  const CONFIG = {
    deviceCode: "ESP32_CAM_01",
    endpoint: "/camera/latest-frame",
    interval: 1500
  };

  let timer = null;
  let loading = false;
  let lastFrame = "";
  let lastImage = "";

  function setText(id, value) {
    const el = $(id);
    if (el) el.textContent = value;
  }

  function setStatus(status, message) {
    setText("camInfo", message);
    setText(
      "cameraStatus",
      status === "online" ? "Online" :
      status === "offline" ? "Offline" : "Menghubungkan..."
    );

    const el = $("cameraStatus");
    if (el) {
      el.classList.remove("online", "offline", "loading");
      el.classList.add(status);
    }
  }

  function resolveImageUrl(path) {
    if (!path) return "";

    try {
      if (/^https?:\/\//i.test(path)) return path;

      const base = new URL(SM.apiBase());
      return new URL(path, base.origin).href;
    } catch {
      return "";
    }
  }

  function showPlaceholder(message) {
    const feed = $("mainFeed");
    if (!feed) return;

    let placeholder = $("cameraPlaceholder");

    if (!placeholder) {
      placeholder = document.createElement("div");
      placeholder.id = "cameraPlaceholder";
      placeholder.className = "camera-placeholder";
      feed.appendChild(placeholder);
    }

    placeholder.textContent = message;
    placeholder.hidden = false;
  }

  function hidePlaceholder() {
    const el = $("cameraPlaceholder");
    if (el) el.hidden = true;
  }

  function getImageElement() {
    const feed = $("mainFeed");
    if (!feed) return null;

    let img = $("cameraBackendFrame");

    if (!img) {
      img = document.createElement("img");
      img.id = "cameraBackendFrame";
      img.className = "stream";
      img.alt = "Live Camera SMARTMOP";
      img.style.width = "100%";
      img.style.height = "auto";
      img.style.objectFit = "contain";

      feed.prepend(img);
    }

    img.onload = () => {
      hidePlaceholder();
      setStatus("online", "Terhubung ke backend YOLO26.");
    };

    img.onerror = () => {
      setStatus("offline", "Gagal memuat gambar dari backend.");
    };

    return img;
  }

  function percentage(value) {
    const n = Number(value);
    return Number.isFinite(n) ? `${Math.round(n * 100)}%` : "-";
  }

  function renderDetection(data) {
    const detections = Array.isArray(data.detections)
      ? data.detections : [];

    const spill = detections.find(item =>
      String(item.class_name || "").toLowerCase() === "liquid_spill"
    );

    const hasSpill = typeof data.has_spill === "boolean"
      ? data.has_spill : Boolean(spill);

    const confidence = data.highest_spill_confidence ??
      spill?.confidence;

    setText(
      "cameraDetection",
      hasSpill ? "Tumpahan terdeteksi" : "Tidak ada tumpahan"
    );

    setText("cameraConfidence", percentage(confidence));

    setText(
      "cameraInference",
      data.inference_ms != null ? `${data.inference_ms} ms` : "-"
    );

    setText("cameraModel", data.model_name || "YOLO26");

    setText(
      "cameraCapturedAt",
      data.captured_at
        ? new Date(data.captured_at).toLocaleString("id-ID")
        : "-"
    );

    const result = $("cameraResult");

    if (result) {
      result.textContent = hasSpill
        ? `Terdeteksi liquid_spill (${percentage(confidence)})`
        : "Tidak ditemukan tumpahan cairan";

      result.classList.toggle("detected", hasSpill);
      result.classList.toggle("clear", !hasSpill);
    }

    renderBoundingBox(spill, data);
  }

  function renderBoundingBox(detection, data) {
    const feed = $("mainFeed");
    const img = $("cameraBackendFrame");

    if (!feed || !img) return;

    let overlay = $("cameraBboxOverlay");

    if (!overlay) {
      overlay = document.createElement("div");
      overlay.id = "cameraBboxOverlay";
      overlay.style.position = "absolute";
      overlay.style.inset = "0";
      overlay.style.pointerEvents = "none";
      overlay.style.overflow = "hidden";

      if (getComputedStyle(feed).position === "static") {
        feed.style.position = "relative";
      }

      feed.appendChild(overlay);
    }

    overlay.innerHTML = "";

    if (!detection || data.show_bbox === false) return;

    const x = Number(detection.bbox_x);
    const y = Number(detection.bbox_y);
    const w = Number(detection.bbox_width);
    const h = Number(detection.bbox_height);

    if (![x, y, w, h].every(Number.isFinite)) return;
    if (x < 0 || y < 0 || w <= 0 || h <= 0 ||
        x + w > 1.001 || y + h > 1.001) return;

    const box = document.createElement("div");

    Object.assign(box.style, {
      position: "absolute",
      left: `${x * 100}%`,
      top: `${y * 100}%`,
      width: `${w * 100}%`,
      height: `${h * 100}%`,
      border: "2px solid #ef4444",
      boxSizing: "border-box"
    });

    const label = document.createElement("span");

    label.textContent =
      `liquid_spill ${percentage(detection.confidence)}`;

    Object.assign(label.style, {
      position: "absolute",
      left: "0",
      top: "-24px",
      background: "#ef4444",
      color: "#fff",
      padding: "3px 6px",
      fontSize: "12px",
      whiteSpace: "nowrap"
    });

    box.appendChild(label);
    overlay.appendChild(box);
  }

  async function loadCamera() {
    if (loading || document.hidden) return;

    loading = true;

    try {
      const query =
        `?device_code=${encodeURIComponent(CONFIG.deviceCode)}`;

      const response = await SM.getData(
        CONFIG.endpoint + query,
        { timeout: 10000 }
      );

      // SM.getData() mengembalikan null ketika API menjawab data: null
      // (artinya belum ada frame, bukan server error).
      if (response == null) {
        lastFrame = "";
        lastImage = "";
        const oldImage = $("cameraBackendFrame");
        if (oldImage) oldImage.hidden = true;
        showPlaceholder("Belum ada frame dari ESP32-CAM.");
        setStatus("loading", "Menunggu frame pertama dari ESP32-CAM...");
        const overlay = $("cameraBboxOverlay");
        if (overlay) overlay.innerHTML = "";
        return;
      }
      if (typeof response !== "object") {
        throw new Error("Respons backend tidak valid.");
      }

      // Mendukung respons berbentuk {success:true, data:{...}}
      // maupun objek data langsung.
      const data = response.data || response;

      const imageUrl = resolveImageUrl(
        data.image_url || data.frame_url || data.image_path
      );

      if (!imageUrl) {
        throw new Error("URL gambar terbaru belum tersedia.");
      }

      const frameKey = String(
        data.frame_id || data.captured_at || imageUrl
      );

      if (frameKey !== lastFrame || imageUrl !== lastImage) {
        const img = getImageElement();

        if (!img) return;

        img.hidden = false;
        img.src = imageUrl;
        lastFrame = frameKey;
        lastImage = imageUrl;
      }

      renderDetection(data);
      setStatus("online", "Kamera terhubung melalui backend SMARTMOP.");

      document.dispatchEvent(
        new CustomEvent("sm:camera-frame", { detail: data })
      );

    } catch (error) {
      setStatus("offline", `Kamera: ${error.message}`);

      if (!lastImage) {
        showPlaceholder(
          "Menunggu frame dari ESP32-CAM melalui backend..."
        );
      }

    } finally {
      loading = false;
    }
  }

  function setupButtons() {
    $("icoPhoto") && (
      $("icoPhoto").innerHTML = SM.icon("camera")
    );

    $("icoRec") && (
      $("icoRec").innerHTML = SM.icon("video")
    );

    $("icoFull") && (
      $("icoFull").innerHTML = SM.icon("expand")
    );

    $("btnPhoto")?.addEventListener("click", () => {
      if (!lastImage) {
        SM.toast("Belum ada gambar kamera.", "warn");
        return;
      }

      const link = document.createElement("a");
      link.href = lastImage;
      link.download = `smartmop-${Date.now()}.jpg`;
      link.target = "_blank";
      link.rel = "noopener";
      link.click();
    });

    const recordButton = $("btnRec");

    if (recordButton) {
      recordButton.disabled = true;
      recordButton.title = "Fitur rekam video belum tersedia.";
      setText("recLabel", "Rekam belum tersedia");
    }

    $("btnHD")?.addEventListener("click", () => {
      SM.toast(
        "Resolusi diatur melalui konfigurasi kamera ESP32-CAM.",
        "info"
      );
    });

    $("btnFull")?.addEventListener("click", () => {
      const feed = $("mainFeed");
      if (!feed) return;

      if (document.fullscreenElement) {
        document.exitFullscreen?.();
      } else {
        feed.requestFullscreen?.();
      }
    });
  }

  function start() {
    if (!$("mainFeed")) return;

    setupButtons();

    setStatus("loading", "Menghubungkan ke kamera...");
    showPlaceholder("Menunggu frame dari ESP32-CAM...");

    loadCamera();
    timer = setInterval(loadCamera, CONFIG.interval);
  }

  document.addEventListener("DOMContentLoaded", start);

  document.addEventListener("visibilitychange", () => {
    if (!document.hidden) loadCamera();
  });

  window.addEventListener("beforeunload", () => {
    if (timer) clearInterval(timer);
  });

})(window.SM);
