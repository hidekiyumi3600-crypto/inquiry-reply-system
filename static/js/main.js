document.addEventListener("DOMContentLoaded", function () {
  const btnGenerate = document.getElementById("btn-generate");
  const btnRegenerate = document.getElementById("btn-regenerate");
  const btnSend = document.getElementById("btn-send");
  const btnComplete = document.getElementById("btn-complete");
  const replyBody = document.getElementById("reply-body");
  const spinner = document.getElementById("generate-spinner");
  const alertArea = document.getElementById("alert-area");

  if (!btnGenerate) return; // ダッシュボードページでは何もしない

  function showAlert(message, type) {
    alertArea.innerHTML =
      '<div class="alert alert-' +
      type +
      ' alert-dismissible fade show">' +
      message +
      '<button type="button" class="btn-close" data-bs-dismiss="alert"></button></div>';
  }

  // AI下書き生成
  function generateDraft() {
    const inquiryNumber = btnGenerate.dataset.inquiry;
    spinner.style.display = "block";
    replyBody.style.display = "none";
    btnGenerate.disabled = true;

    fetch("/api/generate-draft/" + inquiryNumber, { method: "POST" })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        spinner.style.display = "none";
        replyBody.style.display = "block";
        btnGenerate.disabled = false;

        if (data.success) {
          replyBody.value = data.draft;
          btnRegenerate.style.display = "inline-block";
        } else {
          showAlert("生成エラー: " + data.error, "danger");
        }
      })
      .catch(function (err) {
        spinner.style.display = "none";
        replyBody.style.display = "block";
        btnGenerate.disabled = false;
        showAlert("通信エラーが発生しました。", "danger");
      });
  }

  btnGenerate.addEventListener("click", generateDraft);
  btnRegenerate.addEventListener("click", generateDraft);

  // 返信送信
  btnSend.addEventListener("click", function () {
    const body = replyBody.value.trim();
    if (!body) {
      showAlert("返信内容を入力してください。", "warning");
      return;
    }

    if (!confirm("この内容で返信を送信しますか？")) return;

    const inquiryNumber = btnSend.dataset.inquiry;
    btnSend.disabled = true;

    fetch("/api/send-reply/" + inquiryNumber, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body: body }),
    })
      .then(function (r) {
        return r.json();
      })
      .then(function (data) {
        btnSend.disabled = false;
        if (data.success) {
          showAlert("返信を送信しました。", "success");
          setTimeout(function () {
            location.reload();
          }, 1500);
        } else {
          showAlert("送信エラー: " + data.error, "danger");
        }
      })
      .catch(function (err) {
        btnSend.disabled = false;
        showAlert("通信エラーが発生しました。", "danger");
      });
  });

  // 対応完了
  if (btnComplete) {
    btnComplete.addEventListener("click", function () {
      if (!confirm("この問い合わせを対応完了にしますか？")) return;

      const inquiryNumber = btnComplete.dataset.inquiry;
      btnComplete.disabled = true;

      fetch("/api/mark-complete/" + inquiryNumber, { method: "POST" })
        .then(function (r) {
          return r.json();
        })
        .then(function (data) {
          btnComplete.disabled = false;
          if (data.success) {
            showAlert("対応完了にしました。", "success");
            setTimeout(function () {
              location.reload();
            }, 1500);
          } else {
            showAlert("エラー: " + data.error, "danger");
          }
        })
        .catch(function (err) {
          btnComplete.disabled = false;
          showAlert("通信エラーが発生しました。", "danger");
        });
    });
  }
});
