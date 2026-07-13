/**
 * OCRデモ画面 JS
 *
 * 役割:
 * - 画像1〜3枚の選択（4枚以上は明確なエラー表示）
 * - ドラッグ&ドロップ
 * - ファイルバリデーション（Content-Type, サイズ）
 * - OCR API呼び出し（多重送信防止）
 * - result.data を固定フォームへ反映
 * - JSONデバッグ表示
 * - リセット
 */
(function () {
  "use strict";

  // ========================================
  // 定数
  // ========================================
  const API_ENDPOINT = "/ocr";
  const PROPERTY_TYPE = "overview";
  const MAX_FILES = 3;
  const MAX_FILE_SIZE_BYTES = 1 * 1024 * 1024; // 1MB
  const ALLOWED_TYPES = ["image/jpeg", "image/png", "image/gif", "image/webp"];

  // ========================================
  // DOM
  // ========================================
  const dropZone = document.getElementById("dropZone");
  const imageInput = document.getElementById("imageInput");

  const fileList = document.getElementById("fileList");
  const fileListItems = document.getElementById("fileListItems");

  const ocrBtn = document.getElementById("ocrBtn");
  const resetBtn = document.getElementById("resetBtn");

  const statusArea = document.getElementById("statusArea");

  const resultForm = document.getElementById("resultForm");
  const resultJson = document.getElementById("resultJson");
  const toggleRawBtn = document.getElementById("toggleRawBtn");

  let selectedFiles = [];
  let isProcessing = false; // 多重送信防止フラグ

  // ========================================
  // Escape HTML
  // ========================================
  function escapeHtml(value) {
    const div = document.createElement("div");
    div.textContent = String(value);
    return div.innerHTML;
  }

  // ========================================
  // ファイル選択
  // ========================================
  function handleFiles(files) {
    hideStatus();

    const allFiles = Array.from(files);

    // Content-Typeフィルタ
    const imageFiles = allFiles.filter(function (file) {
      return ALLOWED_TYPES.includes(file.type);
    });

    // 非画像ファイルが含まれていた場合の警告
    if (imageFiles.length < allFiles.length) {
      const rejected = allFiles.length - imageFiles.length;
      showStatus(
        '<i class="bi bi-exclamation-triangle-fill"></i> ' +
          escapeHtml(
            rejected +
              "件のファイルは対応していない形式のため除外されました（JPEG/PNG/GIF/WebPのみ）",
          ),
        "warning",
      );
    }

    // 4枚以上選択された場合のエラー
    if (imageFiles.length > MAX_FILES) {
      showStatus(
        '<i class="bi bi-exclamation-triangle-fill"></i> ' +
          escapeHtml(
            "画像は最大" +
              MAX_FILES +
              "枚までです。最初の" +
              MAX_FILES +
              "枚のみ選択されます。",
          ),
        "warning",
      );
    }

    // サイズチェック
    const validFiles = [];
    for (let i = 0; i < Math.min(imageFiles.length, MAX_FILES); i++) {
      const file = imageFiles[i];
      if (file.size > MAX_FILE_SIZE_BYTES) {
        showStatus(
          '<i class="bi bi-exclamation-triangle-fill"></i> ' +
            escapeHtml(
              file.name +
                " はファイルサイズが1MBを超えているため除外されました。",
            ),
          "warning",
        );
        continue;
      }
      if (file.size === 0) {
        showStatus(
          '<i class="bi bi-exclamation-triangle-fill"></i> ' +
            escapeHtml(file.name + " は空ファイルのため除外されました。"),
          "warning",
        );
        continue;
      }
      validFiles.push(file);
    }

    selectedFiles = validFiles;
    renderFileList();
    ocrBtn.disabled = selectedFiles.length === 0 || isProcessing;
  }

  function renderFileList() {
    if (selectedFiles.length === 0) {
      fileList.style.display = "none";
      fileListItems.innerHTML = "";
      return;
    }

    fileList.style.display = "block";

    fileListItems.innerHTML = selectedFiles
      .map(function (file) {
        const sizeKb = (file.size / 1024).toFixed(0);
        return (
          '<li class="list-group-item d-flex justify-content-between align-items-center">' +
          "<span>" +
          '<i class="bi bi-image text-primary me-2"></i>' +
          escapeHtml(file.name) +
          "</span>" +
          '<span class="badge bg-secondary">' +
          sizeKb +
          " KB</span>" +
          "</li>"
        );
      })
      .join("");
  }

  // ========================================
  // Drag & Drop
  // ========================================
  dropZone.addEventListener("dragover", function (event) {
    event.preventDefault();
    dropZone.classList.add("dragover");
  });

  dropZone.addEventListener("dragleave", function () {
    dropZone.classList.remove("dragover");
  });

  dropZone.addEventListener("drop", function (event) {
    event.preventDefault();
    dropZone.classList.remove("dragover");
    if (isProcessing) return;
    handleFiles(event.dataTransfer.files);
  });

  dropZone.addEventListener("click", function (event) {
    if (event.target.closest("label")) return;
    if (isProcessing) return;
    imageInput.click();
  });

  dropZone.addEventListener("keydown", function (event) {
    if (event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (!isProcessing) imageInput.click();
    }
  });

  imageInput.addEventListener("change", function () {
    if (isProcessing) return;
    handleFiles(imageInput.files);
  });

  // ========================================
  // ステータス
  // ========================================
  function showStatus(message, type) {
    statusArea.style.display = "block";
    statusArea.className = "status-area alert alert-" + type;
    statusArea.innerHTML = message;
  }

  function hideStatus() {
    statusArea.style.display = "none";
    statusArea.innerHTML = "";
  }

  // ========================================
  // フォーム初期化
  // ========================================
  function resetResultForm() {
    var fields = resultForm.querySelectorAll("input, select, textarea");
    fields.forEach(function (field) {
      if (field.type === "checkbox" || field.type === "radio") {
        field.checked = false;
        return;
      }
      if (field.tagName === "SELECT") {
        field.selectedIndex = 0;
        return;
      }
      field.value = "";
    });
  }

  // ========================================
  // Select値設定
  // ========================================
  function setSelectValue(field, value) {
    var stringValue = String(value).trim();
    for (var i = 0; i < field.options.length; i++) {
      if (String(field.options[i].value).trim() === stringValue) {
        field.value = field.options[i].value;
        return true;
      }
    }
    for (var j = 0; j < field.options.length; j++) {
      if (field.options[j].textContent.trim() === stringValue) {
        field.value = field.options[j].value;
        return true;
      }
    }
    return false;
  }

  // ========================================
  // 固定フォームへOCR結果反映
  // ========================================
  function fillResultForm(data) {
    if (!data || typeof data !== "object") return;

    Object.entries(data).forEach(function (entry) {
      var name = entry[0];
      var value = entry[1];
      if (value === null || value === undefined || value === "") return;

      var escapedName =
        window.CSS && CSS.escape ? CSS.escape(name) : name.replace(/"/g, '\\"');
      var field = resultForm.querySelector('[name="' + escapedName + '"]');
      if (!field) return;

      if (field.type === "checkbox" || field.type === "radio") {
        field.checked = Boolean(value);
      } else if (field.tagName === "SELECT") {
        setSelectValue(field, value);
      } else {
        field.value =
          typeof value === "object" ? JSON.stringify(value) : String(value);
      }

      field.dispatchEvent(new Event("change", { bubbles: true }));
      field.dispatchEvent(new Event("input", { bubbles: true }));
    });
  }

  // ========================================
  // JSON表示
  // ========================================
  toggleRawBtn.addEventListener("click", function () {
    var isHidden =
      resultJson.style.display === "none" || resultJson.style.display === "";
    resultJson.style.display = isHidden ? "block" : "none";
    toggleRawBtn.textContent = isHidden ? "JSON非表示" : "JSON表示";
  });

  // ========================================
  // OCR実行
  // ========================================
  ocrBtn.addEventListener("click", async function () {
    if (selectedFiles.length === 0 || isProcessing) return;

    isProcessing = true;
    ocrBtn.disabled = true;
    resetBtn.disabled = true;

    ocrBtn.innerHTML =
      '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>' +
      "解析中（" +
      selectedFiles.length +
      "枚）...";

    hideStatus();
    resetResultForm();
    resultJson.textContent = "";
    resultJson.style.display = "none";
    toggleRawBtn.textContent = "JSON表示";

    var formData = new FormData();
    selectedFiles.forEach(function (file) {
      formData.append("images", file);
    });
    formData.append("property_type", PROPERTY_TYPE);

    try {
      var response = await fetch(API_ENDPOINT, {
        method: "POST",
        body: formData,
      });

      var result;
      try {
        result = await response.json();
      } catch (jsonError) {
        throw new Error(
          "APIレスポンスをJSONとして解析できませんでした: " + response.status,
        );
      }

      if (!response.ok) {
        showStatus(
          '<i class="bi bi-exclamation-triangle-fill"></i> ' +
            escapeHtml(
              result.message || "OCR APIエラー (" + response.status + ")",
            ),
          "danger",
        );
        return;
      }

      if (result.success && result.data && typeof result.data === "object") {
        console.log("OCR result.data:", result.data);
        fillResultForm(result.data);
        resultJson.textContent = JSON.stringify(result.data, null, 2);
        showStatus(
          '<i class="bi bi-check-circle-fill"></i> ' +
            escapeHtml(
              result.message ||
                selectedFiles.length + "枚の画像から物件情報を読み込みました",
            ),
          "success",
        );
      } else {
        showStatus(
          '<i class="bi bi-exclamation-triangle-fill"></i> ' +
            escapeHtml(result.message || "OCR処理に失敗しました"),
          "danger",
        );
      }
    } catch (error) {
      console.error("OCR API error:", error);
      showStatus(
        '<i class="bi bi-exclamation-triangle-fill"></i> 通信エラーが発生しました',
        "danger",
      );
    } finally {
      isProcessing = false;
      ocrBtn.disabled = selectedFiles.length === 0;
      resetBtn.disabled = false;
      ocrBtn.innerHTML = '<i class="bi bi-cpu"></i> OCRを実行';
    }
  });

  // ========================================
  // リセット
  // ========================================
  resetBtn.addEventListener("click", function () {
    if (isProcessing) return;

    selectedFiles = [];
    imageInput.value = "";
    renderFileList();
    ocrBtn.disabled = true;
    hideStatus();
    resetResultForm();
    resultJson.textContent = "";
    resultJson.style.display = "none";
    toggleRawBtn.textContent = "JSON表示";
  });
})();
