(function () {
  var mode = "log";
  var chatBusy = false;
  var petBusy = false;
  var petTick = null;
  var petStarted = 0;
  var lastPetSecs = 0;
  var setupBusy = false;
  var lastSetupLog = "";
  var setupTick = null;
  var setupStarted = 0;
  var setupLastGot = 0;
  var setupLastAt = 0;
  var chatAi = null;
  var chatWatch = null;
  var loginTimer = null;
  var loginBridgeTimer = null;
  var petOut = document.getElementById("pout");
  var lastUser = null;
  var lastPetText = "";
  var histKind = "petition";
  var histItems = [];
  var histSel = 0;
  var histTimer = null;
  var lastHw = null;
  var lastConnect = null;
  var lastDeskNote = "claudeNote";
  document.addEventListener("wheel", function (ev) {
    var login = document.getElementById("view-login");
    if (!login || login.hidden) return;
    var t = ev.target;
    if (t && t.closest && t.closest(".log, .petition, .setup-log, textarea")) return;
    login.scrollTop += ev.deltaY;
  }, { passive: true });

  function el(id) {
    return document.getElementById(id);
  }

  function webview() {
    return window.chrome && window.chrome.webview ? window.chrome.webview : null;
  }

  function send(msg) {
    var wv = webview();
    if (!wv) {
      failAuth("Uygulama köprüsü yok. BetterSaul.exe içinden açın.");
      return false;
    }
    try {
      wv.postMessage(JSON.stringify(msg));
      return true;
    } catch (err) {
      try {
        wv.postMessage(msg);
        return true;
      } catch (err2) {
        failAuth("Köprü hatası: " + (err2.message || err.message || err2));
        return false;
      }
    }
  }

  function failAuth(text) {
    resetLoginButtons();
    var el = mode === "reg" ? document.getElementById("rerr") : document.getElementById("lerr");
    if (el) el.textContent = text;
  }

  function show(id) {
    document.getElementById("view-login").hidden = id !== "login";
    document.getElementById("view-app").hidden = id !== "app";
  }

  function setAuth(next) {
    mode = next;
    document.getElementById("form-reg").hidden = mode !== "reg";
    document.getElementById("form-login").hidden = mode !== "log";
    document.getElementById("authTitle").textContent = mode === "reg" ? "Hesap oluştur" : "Giriş yap";
    document.getElementById("authHint").textContent = mode === "reg"
      ? "Ücretsiz hesap açın. Aynı hesapla web sürümü de açılır. Verileriniz paylaşılmaz; bu bilgisayarda kalır."
      : "bettersaul.ai e-posta ve şifreniz. Yönetici hesabı da kullanılabilir. Verileriniz paylaşılmaz; bu bilgisayarda kalır.";
    document.getElementById("swap").textContent = mode === "reg"
      ? "Zaten hesabım var — giriş yap"
      : "Hesabım yok — kayıt ol";
  }

  document.getElementById("swap").onclick = function () {
    setAuth(mode === "reg" ? "log" : "reg");
  };

  function showUpdateWall(s) {
    var wall = document.getElementById("updateWall");
    if (!wall) return;
    var on = !!(s && (s.updateRequired || s.event === "update-required"));
    wall.hidden = !on;
    var txt = document.getElementById("updateWallText");
    if (txt && s && s.updateMessage) txt.textContent = s.updateMessage;
    if (on) {
      document.getElementById("view-login").hidden = true;
      document.getElementById("view-app").hidden = true;
    }
  }

  var updateBtn = document.getElementById("updateWallBtn");
  if (updateBtn) {
    updateBtn.onclick = function () {
      send({ cmd: "open-update" });
    };
  }

  function applySession(s) {
    if (s && s.updateRequired) {
      showUpdateWall(s);
      return;
    }
    if (loginTimer) { clearTimeout(loginTimer); loginTimer = null; }
    show("app");
    lastUser = s.user || null;
    document.getElementById("whoName").textContent = (s.user && (s.user.name || s.user.email)) || "";
    fillTemplates(s.templates || []);
    renderHardware(s.hardware, s.mcpConnect);
    renderMcp(s.mcp);
    if (!s.mcp || !(s.mcp.connected || s.mcp.running))
      send(Object.assign({ cmd: "mcp-start" }, mcpFields()));
    else
      send({ cmd: "mcp-status" });
    send({ cmd: "archive-list", kind: "petition", q: "" });
    setReady(!!s.setupReady);
    renderClaude(s);
    if (!s.setupReady) {
      switchTab("setup");
      if (!setupBusy) {
        setupBusy = true;
        var btn = document.getElementById("setupBtn");
        if (btn) {
          btn.disabled = true;
          btn.textContent = "Kuruluyor…";
        }
        var log = document.getElementById("setupLog");
        if (log) log.textContent = "";
        lastSetupLog = "";
        markPhase(1);
        send({ cmd: "setup" });
      }
    } else switchTab("guide");
  }

  function lawyerProfile() {
    try { return JSON.parse(localStorage.getItem("bs.lawyer") || "{}") || {}; }
    catch (e) { return {}; }
  }

  function fillLawyer(user) {
    var saved = lawyerProfile();
    var name = saved.lawyerName || (user && user.name) || "";
    var set = function (id, val) {
      var el = document.getElementById(id);
      if (el && !el.value) el.value = val || "";
    };
    set("plawyer", name);
    set("pbar", saved.lawyerBar);
    set("pbarno", saved.lawyerBarNo);
    set("plphone", saved.lawyerPhone);
    set("pladdr", saved.lawyerAddress);
  }

  function readLawyer() {
    var data = {
      lawyerName: document.getElementById("plawyer").value.trim(),
      lawyerBar: document.getElementById("pbar").value.trim(),
      lawyerBarNo: document.getElementById("pbarno").value.trim(),
      lawyerPhone: document.getElementById("plphone").value.trim(),
      lawyerAddress: document.getElementById("pladdr").value.trim(),
      lawyerEmail: (lastUser && lastUser.email) || "",
    };
    try { localStorage.setItem("bs.lawyer", JSON.stringify(data)); } catch (e) {}
    return data;
  }

  function stripJunk(s) {
    if (!s) return "";
    var lines = String(s).split(/\r?\n/);
    var out = [];
    for (var i = 0; i < lines.length; i++) {
      var t = lines[i];
      if (/^\s*(build|model)\s*:/i.test(t)) continue;
      if (/BETTER~1|b9999-/i.test(t)) continue;
      if (/\[ ?Prompt:|Generation:\s*[\d.]+\s*t\/s/i.test(t)) continue;
      if (/biçim ve içerik disiplini|Araç Kullanımı|MCP araçlarıyla|Basit selamlaşmada|Yargı MCP|Sen "Be|Sen "BetterSaul|available commands|Loading model|im_start|Ufuk Tekin|Dilekçenin Anatomisi|Halüsinasyon yasağı|Kullanılabilir araçlar|search_bedesten|search_corpus_deep|get_bedesten_document|search_emsal|search_mevzuat|get_mevzuat_article|list_mevzuat_catalog|search_anayasa|get_anayasa_document|search_resmi_gazete|get_resmi_gazete_fihrist|get_resmi_gazete_document|scan_source|petition_guide|petition_skeleton|format_petition|check_petition|review_petition|save_petition_history|save_petition_pdf/i.test(t))
        continue;
      out.push(t);
    }
    return out.join("\n").replace(/\n{3,}/g, "\n\n").replace(/^\s+/, "");
  }

  function showPdfBtn() {
    var btn = document.getElementById("ppdf");
    if (btn) btn.hidden = !(lastPetText || (petOut && petOut.innerText) || "").trim();
  }

  function escPet(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
  }

  function fmtPetSure(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    var m = Math.floor(sec / 60);
    var s = sec % 60;
    if (m <= 0) return s + " saniye";
    if (s === 0) return m + " dakika";
    return m + " dakika " + s + " saniye";
  }

  function fmtPetSureDone(sec) {
    sec = Math.max(0, Math.floor(sec || 0));
    var m = Math.floor(sec / 60);
    var s = sec % 60;
    if (m <= 0) return s + " saniyede";
    if (s === 0) return m + " dakikada";
    return m + " dakika " + s + " saniyede";
  }

  function paintPetSure(running) {
    var el = document.getElementById("ptime");
    if (!el) return;
    var sec = lastPetSecs;
    if (running) el.textContent = "Geçen süre: " + fmtPetSure(sec);
    else if (sec > 0) el.textContent = "Dilekçe " + fmtPetSureDone(sec) + " hazırlandı.";
    else el.textContent = "";
  }

  function tickPetSure() {
    if (!petStarted) return;
    lastPetSecs = Math.max(0, Math.floor((Date.now() - petStarted) / 1000));
    paintPetSure(true);
  }

  function startPetSure() {
    petStarted = Date.now();
    lastPetSecs = 0;
    if (petTick) clearInterval(petTick);
    paintPetSure(true);
    petTick = setInterval(tickPetSure, 1000);
  }

  function stopPetSure(ok) {
    if (petTick) {
      clearInterval(petTick);
      petTick = null;
    }
    if (petStarted) lastPetSecs = Math.max(0, Math.floor((Date.now() - petStarted) / 1000));
    petStarted = 0;
    paintPetSure(false);
    var rec = {
      at: new Date().toISOString(),
      title: ((document.getElementById("ptitle") || {}).value || "").trim(),
      petitionType: ((document.getElementById("ptype") || {}).value || "").trim(),
      seconds: lastPetSecs,
      minutes: Math.round((lastPetSecs / 60) * 10) / 10,
      ok: !!ok
    };
    try {
      var arr = JSON.parse(localStorage.getItem("bs.petitionTimings") || "[]");
      if (!Array.isArray(arr)) arr = [];
      arr.unshift(rec);
      localStorage.setItem("bs.petitionTimings", JSON.stringify(arr.slice(0, 80)));
    } catch (e) {}
    var box = document.getElementById("presearch");
    if (box && lastPetSecs > 0) {
      box.hidden = false;
      box.textContent += (ok ? "Hazırlanma süresi: " : "Kesilen süre: ") + fmtPetSure(lastPetSecs) + ".\n";
      box.scrollTop = box.scrollHeight;
    }
    return rec;
  }

  function findPetTiming(item) {
    try {
      var arr = JSON.parse(localStorage.getItem("bs.petitionTimings") || "[]");
      var title = ((item && item.title) || "").trim();
      var when = item && item.createdAt ? Date.parse(item.createdAt) : 0;
      var i;
      for (i = 0; i < arr.length; i++) {
        if (arr[i].ok === false) continue;
        if (title && arr[i].title === title) {
          if (!when || Math.abs(Date.parse(arr[i].at) - when) < 20 * 60 * 1000) return arr[i];
        }
      }
    } catch (e) {}
    return null;
  }

  function partyKey(raw) {
    var t = String(raw || "");
    if (/VEK/i.test(t)) return "DAVACI VEKİLİ";
    if (/^DAVAC/i.test(t)) return "DAVACI";
    if (/^DAVAL/i.test(t)) return "DAVALI";
    if (/KONU/i.test(t)) return "DAVA KONUSU";
    if (/^HARCA/i.test(t)) return "HARCA ESAS DEĞER";
    return t;
  }

  function petitionHtml(raw) {
    var lines = String(raw || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n").split("\n");
    var i = 0;
    var html = [];
    var partyRe = /^(DAVACI(?:\s+VEK[İI]L[İI]?)?|VEK[İI]L[İI]?|DAVALI|DAVA\s+KONUSU|HARCA\s+ESAS(?:\s+DE[ĞG]ER)?|KONU|Ad Soyad|T\.C\.\s*Kimlik No|Adres)\s*[:：]\s*(.*)$/i;
    var headRe = /^(DAVACI(?:\s+VEK[İI]L[İI]?)?|DAVALI|KONU)\s*$/i;
    var partyContRe = /^(Adres|E-posta|Eposta|Tel|Telefon|T\.C\.|Mahalle|Baro|Sicil|B[üu]ro|Ad Soyad)\b/i;
    var secRe = /^(A[ÇC]IKLAMALAR|HUKUK[İI]\s+(SEBEPLER|NEDENLER|DAYANAKLAR)|DEL[İI]LLER|SONU[CÇ]\s+VE\s+[İI]STEM|EKLER|KONU|DAVA\s+[ŞS]ARTI)\s*:?\s*$/i;
    var metaRe = /^\s*(Delil|Hukuki dayanak|Hukuki sonuç)\s*[:：]/i;
    var dateRe = /^\d{1,2}(\s+\S+\s+\d{4}|\.\d{1,2}\.\d{4})\s*$/;
    function skipBlank() { while (i < lines.length && !String(lines[i]).trim()) i++; }
    skipBlank();
    if (i < lines.length && /^T\.C\.\s*$/i.test(lines[i].trim())) {
      html.push('<div class="p-tc"><b>T.C.</b></div>');
      i++;
      skipBlank();
    }
    if (i < lines.length && /MAHKEME|BAŞKANLIĞI|DANIŞTAY|SAVCILIK/i.test(lines[i])) {
      html.push('<div class="p-court"><b>' + escPet(lines[i].trim()) + "</b></div>");
      i++;
      skipBlank();
      while (i < lines.length && /TALEPL[İI]D[İI]R|^—.+—$/.test(lines[i].trim())) {
        html.push('<div class="p-banner"><b>' + escPet(lines[i].trim()) + "</b></div>");
        i++;
        skipBlank();
      }
      if (i < lines.length && /^DAVA D[İI]LEK/i.test(lines[i].trim())) {
        i++;
      }
      skipBlank();
      if (
        i < lines.length &&
        lines[i].trim().length > 2 &&
        lines[i].trim().length < 80 &&
        !partyRe.test(lines[i].trim()) &&
        !headRe.test(lines[i].trim()) &&
        !secRe.test(lines[i].trim()) &&
        lines[i].indexOf(":") < 0 &&
        /(dilekçe|davası|iptali|alacağı|tahliye|tazminat|boşanma)/i.test(lines[i])
      ) {
        html.push('<div class="p-kind"><b>' + escPet(lines[i].trim()) + "</b></div>");
        i++;
      }
    }
    while (i < lines.length) {
      var rawLine = lines[i];
      var t = String(rawLine).trim();
      if (!t) { i++; continue; }
      if (/TALEPL[İI]D[İI]R|^—.+—$/.test(t)) {
        html.push('<div class="p-banner"><b>' + escPet(t) + "</b></div>");
        i++;
        continue;
      }
      if (headRe.test(t)) {
        html.push('<div class="sec"><b>' + escPet(t) + "</b></div>");
        i++;
        var body = [];
        while (i < lines.length && String(lines[i]).trim()) {
          var lt = String(lines[i]).trim();
          if (headRe.test(lt) || secRe.test(lt)) break;
          if (partyRe.test(lt) && /^(DAVACI|DAVALI|VEK|KONU|HARCA)/i.test(lt)) break;
          body.push(lt);
          i++;
        }
        if (body.length) html.push('<div class="lawyer">' + body.map(escPet).join("<br>") + "</div>");
        continue;
      }
      if (/^[IVX]+\.\s+/.test(t)) {
        html.push('<div class="vakia-h"><b>' + escPet(t) + "</b></div>");
        i++;
        continue;
      }
      var pm = t.match(partyRe);
      if (pm) {
        var vals = [];
        if (String(pm[2] || "").trim()) vals.push(pm[2].trim());
        i++;
        while (i < lines.length) {
          var n = lines[i];
          if (!String(n).trim()) break;
          var nt = String(n).trim();
          if (partyRe.test(nt) || secRe.test(nt) || metaRe.test(nt)) break;
          if (n.length && (/\s/.test(n.charAt(0)) || nt.indexOf(":") < 0 || partyContRe.test(nt))) {
            vals.push(nt);
            i++;
            continue;
          }
          break;
        }
        html.push(
          '<div class="row"><span class="k"><b>' +
            escPet(partyKey(pm[1])) +
            '</b></span><span class="v">' +
            vals.map(escPet).join("<br>") +
            "</span></div>"
        );
        continue;
      }
      if (secRe.test(t)) {
        html.push('<div class="sec"><b>' + escPet(t.replace(/:+\s*$/, "") + " :") + "</b></div>");
        i++;
        continue;
      }
      if (metaRe.test(t)) {
        html.push('<div class="meta">' + escPet(t.replace(/\s+/g, " ")) + "</div>");
        i++;
        continue;
      }
      if (dateRe.test(t) || /^Av\./.test(t) || /^Davac[ıi] Vekili/i.test(t)) {
        var sign = [];
        while (i < lines.length) {
          var s = String(lines[i]).trim();
          if (!s) { i++; continue; }
          if (secRe.test(s) || partyRe.test(s)) break;
          sign.push(s);
          i++;
        }
        if (sign.length)
          html.push('<div class="lawyer">' + sign.map(escPet).join("<br>") + "</div>");
        continue;
      }
      if (/^\d{1,2}[\.\)\-]/.test(t)) {
        var head = t;
        var bits = [];
        i++;
        while (i < lines.length) {
          var nx = lines[i];
          if (!String(nx).trim()) break;
          var nxt = String(nx).trim();
          if (/^\d{1,2}[\.\)\-]/.test(nxt) || secRe.test(nxt) || partyRe.test(nxt) || metaRe.test(nxt) || dateRe.test(nxt))
            break;
          bits.push(nxt);
          i++;
        }
        html.push(
          '<div class="vakia"><div class="vakia-h"><b>' +
            escPet(head) +
            "</b></div>" +
            (bits.length ? '<div class="vakia-b">' + escPet(bits.join(" ")) + "</div>" : "") +
            "</div>"
        );
        continue;
      }
      var para = [t];
      i++;
      while (i < lines.length && String(lines[i]).trim()) {
        var pt = String(lines[i]).trim();
        if (partyRe.test(pt) || secRe.test(pt) || metaRe.test(pt) || dateRe.test(pt) || /^\d{1,2}[\.\)\-]/.test(pt))
          break;
        para.push(pt);
        i++;
      }
      html.push('<div class="p">' + escPet(para.join(" ")) + "</div>");
    }
    return html.join("");
  }

  function renderPetition(raw) {
    lastPetText = stripJunk(raw || "");
    if (petOut) petOut.innerHTML = petitionHtml(lastPetText);
  }

  var typeHints = {
    "Boşanma Davası": {
      court: "… Aile Mahkemesi'ne",
      parties: "DAVACI: Ad Soyad, TCKN, tebliğ adresi\nDAVALI: Ad Soyad, TCKN, tebliğ adresi\nOrtak çocuk: ad, doğum tarihi",
      requests: "1) Boşanma (TMK m. 166)\n2) Velayet\n3) Tedbir / yoksulluk nafakası\n4) Maddi ve manevi tazminat\n5) Ziynet iadesi",
      extra: "Evlilik ve ayrılık tarihi, kusur olayları, gelir. Tutar ve ziynet tablosunu aşağıdaki nispi alanlara yazın.",
    },
    "İş Davası": {
      court: "… İş Mahkemesi'ne",
      parties: "DAVACI (işçi): [Ad Soyad, TCKN, adres]\nDAVALI (işveren): [unvan, MERSİS, adres]",
      requests: "1) Ödenmeyen ücret alacağı (HMK m. 107 belirsiz alacak / net tutar)\n2) 4857 m. 34 en yüksek mevduat faizi",
      extra: "İşe giriş, ödenmeyen dönem (çalışma süresiyle karıştırmayın), net/brüt ücret, fesih şekli varsa, arabuluculuk büro no / son tutanak tarihi. Tutar ve tutanak no uydurmayın.",
    },
    "Alacak Davası": {
      court: "… Asliye Hukuk Mahkemesi'ne",
      parties: "DAVACI: [Ad Soyad / unvan]\nDAVALI: [Ad Soyad / unvan]",
      requests: "1) Asıl alacak\n2) Temerrüt faizi",
      extra: "Sözleşme/fatura tarihi, ihtar ve bakiye tutarı yazın.",
    },
    "İcra Hukuku": {
      court: "… İcra Hukuk Mahkemesi'ne",
      parties: "ALACAKLI: […]\nBORÇLU: […]\nİcra dosyası: [daire / esas]",
      requests: "1) İtirazın iptali / kaldırılması\n2) Takiğin devamı",
      extra: "Ödeme emri tebliğ tarihi ve itirazın kapsamını yazın.",
    },
    "İdare Hukuku": {
      court: "… İdare Mahkemesi Başkanlığı'na",
      parties: "DAVACI: […]\nDAVALI İDARE: […]",
      requests: "1) İşlemin iptali\n2) Tam yargı (varsa)",
      extra: "İşlem tarih/sayı, tebliğ ve varsa idari başvuru yazın. İvedi / YD / adli yardım istenirse işaretleyin.",
    },
    "Tazminat Davası": {
      court: "… Asliye Hukuk Mahkemesi'ne",
      parties: "DAVACI: […]\nDAVALI: […]",
      requests: "1) Maddi tazminat\n2) Manevi tazminat",
      extra: "Olay tarihi, kusur, zarar kalemleri ve raporları yazın.",
    },
    "Ceza Hukuku": {
      court: "… Asliye Ceza / Ağır Ceza Mahkemesi'ne",
      parties: "KATILAN: […]\nŞÜPHELİ / SANIK: […]",
      requests: "1) Kamu davasına katılma\n2) Tazminat / tedbir",
      extra: "Suç tarihi, soruşturma/esas no ve zarar yazın.",
    },
    "Kira / Tahliye": {
      court: "… Sulh Hukuk Mahkemesi'ne",
      parties: "DAVACI (kiralayan): […]\nDAVALI (kiracı): […]\nTaşınmaz: [adres]",
      requests: "1) Tahliye\n2) Birikmiş kira",
      extra: "Sözleşme tarihi, kira bedeli, ihtar ve temerrüt yazın.",
    },
    "Tüketici Hukuku": {
      court: "… Tüketici Mahkemesi'ne",
      parties: "DAVACI (tüketici): […]\nDAVALI (satıcı): […]",
      requests: "1) Bedel iadesi / değişim / onarım\n2) Tazminat",
      extra: "Fatura tarihi, ayıp ve satıcıya bildirim yazın.",
    },
    "Diğer": {
      court: "… Mahkemesi'ne",
      parties: "DAVACI: […]\nDAVALI: […]",
      requests: "1) Taleplerin kabulü",
      extra: "Uyuşmazlığı kronolojik ve somut yazın.",
    },
  };

  function stripWebFluencyFlag(extra) {
    return String(extra || "").replace(/\n?WEB_FLUENCY\s*:\s*[01]\s*/gi, "\n").trim();
  }

  function packPetitionPrompt(extra, prompt) {
    extra = String(extra || "").trim();
    prompt = String(prompt || "").trim();
    if (!prompt) return extra;
    return "KULLANICI_PROMPT:\n" + prompt + "\n---\n" + extra;
  }

  function unpackPetitionPrompt(raw) {
    raw = String(raw || "");
    var fluency = !/WEB_FLUENCY\s*:\s*0/i.test(raw);
    raw = stripWebFluencyFlag(raw);
    var m = raw.match(/^\s*KULLANICI_PROMPT:\s*\n([\s\S]*?)\n---\s*\n?/);
    if (!m) return { prompt: "", extra: raw.trim(), fluency: fluency };
    return { prompt: m[1].trim(), extra: raw.slice(m[0].length).trim(), fluency: fluency };
  }

  function extractPromptFromArchive(prompt) {
    var t = String(prompt || "");
    var m = t.match(/Kullanıcı prompt[’']u:\s*\n([\s\S]*?)(?:\n\nDilekçe başlığı:|$)/);
    return m ? m[1].trim() : "";
  }

  function applyTypeHints(force) {
    if (!document.getElementById("ptype")) return;
    var hint = typeHints[document.getElementById("ptype").value] || typeHints["Diğer"];
    var fill = function (id, val) {
      var el = document.getElementById(id);
      if (!el) return;
      if (force || !el.value.trim()) el.value = val || "";
    };
    fill("pcourt", hint.court);
    fill("pparties", hint.parties);
    fill("preq", hint.requests);
    fill("pextra", hint.extra);
    showClaimGroups(document.getElementById("ptype").value);
  }

  function showClaimGroups(type) {
    var g = {
      tazminat: /Boşanma|Tazminat|İdare|Ceza|Tüketici/.test(type),
      aile: /Boşanma/.test(type),
      is: /İş/.test(type),
      alacak: /Alacak|İcra|Kira|Tüketici|Diğer|İş/.test(type),
      ziynet: /Boşanma|Alacak|Diğer/.test(type),
      harc: true
    };
    document.querySelectorAll("[data-g]").forEach(function (el) {
      var key = el.getAttribute("data-g");
      el.hidden = !g[key];
    });
  }

  function parseTl(s) {
    var t = String(s || "").replace(/[^\d.,]/g, "");
    if (!t) return 0;
    if (t.indexOf(",") >= 0 && t.indexOf(".") >= 0) t = t.replace(/\./g, "").replace(",", ".");
    else if (t.indexOf(",") >= 0) t = t.replace(",", ".");
    else if ((t.match(/\./g) || []).length > 1) t = t.replace(/\./g, "");
    var n = parseFloat(t);
    return isFinite(n) ? n : 0;
  }

  function hasAmt(id) {
    var el = document.getElementById(id);
    return !!(el && /\d/.test(el.value || ""));
  }

  function addZiynetRow(row) {
    var tb = document.querySelector("#ziynetTable tbody");
    if (!tb) return;
    var tr = document.createElement("tr");
    ["cins", "adet", "ayar", "gram", "tl"].forEach(function (k) {
      var td = document.createElement("td");
      var inp = document.createElement("input");
      inp.dataset.z = k;
      inp.value = (row && row[k]) || "";
      if (k === "tl" || k === "adet" || k === "gram") inp.inputMode = "decimal";
      inp.oninput = syncHarc;
      td.appendChild(inp);
      tr.appendChild(td);
    });
    tb.appendChild(tr);
  }

  function ziynetRows() {
    var rows = [];
    document.querySelectorAll("#ziynetTable tbody tr").forEach(function (tr) {
      var item = {};
      var any = false;
      tr.querySelectorAll("input").forEach(function (inp) {
        item[inp.dataset.z] = (inp.value || "").trim();
        if (item[inp.dataset.z]) any = true;
      });
      if (any) rows.push(item);
    });
    return rows;
  }

  function ziynetComplete() {
    var rows = ziynetRows();
    if (!rows.length) return false;
    return rows.every(function (r) {
      return r.cins && r.adet && r.gram && /\d/.test(r.tl || "");
    });
  }

  function looksLabor() {
    var type = (document.getElementById("ptype") || {}).value || "";
    var blob = (
      type + " " +
      ((document.getElementById("psummary") || {}).value || "") + " " +
      ((document.getElementById("preq") || {}).value || "") + " " +
      ((document.getElementById("pextra") || {}).value || "")
    ).toLowerCase();
    return /iş dava|işçi|işveren|iş yer|işyeri|maaş|ücret|kıdem|4857|ödememi alamad/.test(blob);
  }

  function syncHarc() {
    var harc = document.getElementById("pamt-harc");
    if (!harc || harc.dataset.manual === "1") return;
    var ids = ["pamt-kidem", "pamt-ihbar", "pamt-mesai", "pamt-ubgt", "pamt-izin", "pamt-alacak"];
    if (!looksLabor()) ids = ["pamt-maddi", "pamt-manevi"].concat(ids);
    var sum = 0;
    ids.forEach(function (id) { sum += parseTl((document.getElementById(id) || {}).value); });
    if (!looksLabor()) ziynetRows().forEach(function (r) { sum += parseTl(r.tl); });
    harc.value = sum > 0 ? String(Math.round(sum * 100) / 100) : "";
  }

  function readClaimValues() {
    syncHarc();
    return {
      maddi: (document.getElementById("pamt-maddi") || {}).value || "",
      manevi: (document.getElementById("pamt-manevi") || {}).value || "",
      tedbirDavaci: (document.getElementById("pamt-tedbir-d") || {}).value || "",
      tedbirCocuk: (document.getElementById("pamt-tedbir-c") || {}).value || "",
      yoksulluk: (document.getElementById("pamt-yoksul") || {}).value || "",
      istirak: (document.getElementById("pamt-istirak") || {}).value || "",
      kidem: (document.getElementById("pamt-kidem") || {}).value || "",
      ihbar: (document.getElementById("pamt-ihbar") || {}).value || "",
      fazlaMesai: (document.getElementById("pamt-mesai") || {}).value || "",
      ubgt: (document.getElementById("pamt-ubgt") || {}).value || "",
      yillikIzin: (document.getElementById("pamt-izin") || {}).value || "",
      alacak: (document.getElementById("pamt-alacak") || {}).value || "",
      harcaEsas: (document.getElementById("pamt-harc") || {}).value || "",
      ziynet: ziynetRows()
    };
  }

  function hmk119Gaps() {
    var type = document.getElementById("ptype").value;
    var blob = (
      document.getElementById("psummary").value + " " +
      document.getElementById("preq").value + " " +
      document.getElementById("pextra").value + " " +
      document.getElementById("pparties").value
    ).toLowerCase().replace(/ortak çocuk:\s*ad,?\s*doğum tarihi/g, "");
    var miss = [];
    if (/kıdem/.test(blob) && !hasAmt("pamt-kidem")) miss.push("kıdem tutarı");
    if (/ihbar/.test(blob) && !hasAmt("pamt-ihbar")) miss.push("ihbar tutarı");
    if (/fazla mesai/.test(blob) && !hasAmt("pamt-mesai")) miss.push("fazla mesai tutarı");
    if (/ubgt/.test(blob) && !hasAmt("pamt-ubgt")) miss.push("UBGT tutarı");
    if (/yıllık izin/.test(blob) && !hasAmt("pamt-izin")) miss.push("yıllık izin tutarı");
    if ((/asıl alacak|alacağın|kira bedel|ink[aâ]r tazminat/.test(blob) || hasAmt("pamt-alacak")) && !hasAmt("pamt-alacak") && !hasAmt("pamt-harc")) {
      miss.push("asıl alacak / harca esas tutarı");
    }
    if (/ziynet|altın|bilezik|gerdanlık/.test(blob) || ziynetRows().length) {
      if (!ziynetComplete()) miss.push("ziynet tablosu (cins, adet, gram, TL)");
    }
    syncHarc();
    var nispi = hasAmt("pamt-maddi") || hasAmt("pamt-manevi") || hasAmt("pamt-kidem") || hasAmt("pamt-alacak") || ziynetRows().length;
    if (nispi && !hasAmt("pamt-harc")) miss.push("harca esas değer");
    return miss;
  }

  function fillTemplates(rows) {
    var sel = document.getElementById("ptpl");
    if (!sel) return;
    sel.innerHTML = '<option value="">Şablon kullanma</option>';
    rows.forEach(function (t) {
      var o = document.createElement("option");
      o.value = t.id || "";
      o.textContent = t.name || t.id;
      if (t.description) o.dataset.desc = t.description;
      sel.appendChild(o);
    });
  }

  function setReady(ready) {
    var wiz = document.querySelector(".wiz");
    var st = document.getElementById("setupState");
    if (st) st.textContent = ready
      ? "BetterSaul MCP hazır. Ayar yazılırken ilgili masaüstü kapanır; yazılınca yeniden açılır."
      : "Kurulum Claude / ChatGPT / Gemini Desktop + BetterSaul MCP ile biter.";
    var btn = document.getElementById("setupBtn");
    if (btn) {
      btn.disabled = !!ready || setupBusy;
      btn.hidden = !!ready;
    }
    if (wiz) wiz.classList.toggle("ready", !!ready && !setupBusy);
    if (ready && !setupBusy) {
      stopSetupClock();
      var title = el("setupTitle");
      var stage = el("setupStage");
      var kicker = el("setupKicker");
      if (title) title.textContent = "MCP hazır — yapay zekânızı bağlayın";
      if (stage) stage.textContent = "Yapay zekâ ayarları için sayfada aşağı inin. Claude Desktop’ı indirmeniz yeterlidir; ardından “Ayarları yaz” butonuyla bağlayın. Ayar yazılırken seçtiğiniz masaüstü kapanır; yazılınca yeniden açılır. Yeni sohbet açın.";
      if (kicker) kicker.textContent = "Aşağıdan devam edin";
      markPhase(4);
    }
  }

  function renderClaude(s) {
    renderDesk(s, "claude", "Claude");
    renderDesk(s, "chatgpt", "ChatGPT");
    renderDesk(s, "gemini", "Gemini");
  }

  function renderDesk(s, key, title) {
    s = s || {};
    var c = s.mcpConnect || lastConnect || {};
    var installed = !!(s[key + "Installed"] || c[key + "Installed"]);
    var running = !!(s[key + "Running"] || c[key + "Running"]);
    var cfg = !!(s[key + "ConfigReady"] || c[key + "ConfigReady"]);
    var leftover = !!(c[key + "Profile"] || s[key + "Profile"]);
    var st = document.getElementById(key + "State");
    var det = document.getElementById(key + "Detect");
    var note = document.getElementById(key + "Note");
    var dl = document.getElementById(key + "DownloadBtn");
    var launch = document.getElementById(key + "LaunchBtn");
    if (st) {
      st.classList.toggle("ok", !!installed);
      st.classList.toggle("bad", !installed);
      if (running && cfg) st.textContent = title + " yüklü ve açık. Ayar yazılırsa kapanır, yazılır, sonra tekrar kapanıp açılır.";
      else if (running) st.textContent = title + " yüklü ve açık. Ayar için kapanacak, yazılacak, yeniden başlatılacak.";
      else if (installed && cfg) st.textContent = title + " yüklü, ayar yazılmış. Açınca bir kez kapanıp açılmalı; yeni sohbet açın.";
      else if (installed) st.textContent = title + " Desktop yüklü. Ayarları yazın; kapanır, yazar, tekrar kapanıp açılır.";
      else if (leftover) st.textContent = title + " yüklü değil (eski profil kalıntısı var). İndirip kurun; ücretsiz hesap yeter.";
      else st.textContent = title + " Desktop yüklü değil. İndirip kurun; ücretsiz hesap yeter.";
    }
    if (det) {
      det.textContent = c[key + "Summary"] || s[key + "Summary"] || (c[key + "Source"] ? ("Kaynak: " + c[key + "Source"]) : "");
    }
    if (dl) dl.hidden = !!installed;
    if (launch) launch.hidden = !installed;
    var mine = lastDeskNote === key + "Note";
    if (note && mine && s.detail) note.textContent = s.detail;
    if (note && mine && s.error) note.textContent = s.error;
  }

  function bytes(n) {
    if (!n) return "";
    if (n < 1024 * 1024) return Math.round(n / 1024) + " KB";
    if (n < 1024 * 1024 * 1024) return (n / (1024 * 1024)).toFixed(1) + " MB";
    return (n / (1024 * 1024 * 1024)).toFixed(2) + " GB";
  }

  function fmtTime(sec) {
    sec = Math.max(0, Math.floor(sec));
    var m = Math.floor(sec / 60);
    var s = sec % 60;
    return m + ":" + (s < 10 ? "0" : "") + s;
  }

  function markPhase(n) {
    document.querySelectorAll("#setupSteps li").forEach(function (li) {
      var k = parseInt(li.getAttribute("data-k"), 10);
      li.classList.toggle("done", k < n);
      li.classList.toggle("on", k === n);
    });
    var titles = {
      1: ["Ortam hazırlanıyor", "Python ve çalışma zamanı kuruluyor."],
      2: ["BetterSaul MCP", "İçtihat araçları ve Python paketleri yükleniyor."],
      3: ["Masaüstü ayarı", "Claude / ChatGPT / Gemini ayarı yazılıyor; yoksa indirin."],
      4: ["MCP hazır", "Yapay zekâ ayarları için aşağı inin; Claude Desktop’ı indirmeniz yeterlidir."]
    };
    if (titles[n] && setupBusy) {
      document.getElementById("setupTitle").textContent = titles[n][0];
      document.getElementById("setupKicker").textContent = "Adım " + n + " / 4";
    }
  }

  function phaseOf(pct, stage) {
    var src = String(stage || "");
    if (pct >= 100 || /tamam|hazır|done/i.test(src)) return 4;
    if (/claude/i.test(src) || (pct >= 72 && pct < 100)) return 3;
    if (/mcp|python|paket/i.test(src) || (pct >= 40 && pct < 72)) return 2;
    return 1;
  }

  function startSetupClock() {
    setupStarted = Date.now();
    setupLastGot = 0;
    setupLastAt = Date.now();
    clearInterval(setupTick);
    setupTick = setInterval(function () {}, 500);
  }

  function stopSetupClock() {
    clearInterval(setupTick);
    setupTick = null;
  }

  function openProSite(ev) {
    if (ev) ev.preventDefault();
    send({ cmd: "open-site" });
  }
  document.querySelectorAll(".js-open-pro").forEach(function (n) {
    n.addEventListener("click", openProSite);
  });

  // Giriş ekranı: şifremi unuttum (tarayıcıda açılır) + KVKK popup'ı.
  var forgotLink = document.getElementById("forgotLink");
  if (forgotLink) {
    forgotLink.addEventListener("click", function (ev) {
      ev.preventDefault();
      send({ cmd: "open-forgot" });
    });
  }
  var kvkkLoginBtn = document.getElementById("kvkkLoginBtn");
  var kvkkDialog = document.getElementById("kvkkDialog");
  if (kvkkLoginBtn && kvkkDialog) {
    kvkkLoginBtn.addEventListener("click", function () {
      var src = document.querySelector("#form-reg .kvkk-body");
      var dst = document.getElementById("kvkkDialogBody");
      if (src && dst && !dst.innerHTML) dst.innerHTML = src.innerHTML;
      kvkkDialog.showModal();
    });
    var kvkkClose = document.getElementById("kvkkClose");
    if (kvkkClose) kvkkClose.addEventListener("click", function () { kvkkDialog.close(); });
    kvkkDialog.addEventListener("click", function (ev) {
      if (ev.target === kvkkDialog) kvkkDialog.close();
    });
  }
  var setupProTab = document.getElementById("setupProTab");
  if (setupProTab) setupProTab.onclick = function () { switchTab("pro"); };

  function switchTab(id) {
    ["guide", "history", "setup", "pro"].forEach(function (t) {
      var el = document.getElementById("tab-" + t);
      if (el) el.hidden = t !== id;
    });
    document.querySelectorAll(".tabs button").forEach(function (b) {
      b.classList.toggle("on", b.getAttribute("data-tab") === id);
    });
    if (id === "setup") {
      send({ cmd: "mcp-status" });
      send({ cmd: "mcp-export" });
    }
    if (id === "history") loadHistory();
  }

  document.querySelectorAll(".tabs button").forEach(function (b) {
    b.onclick = function () { switchTab(b.getAttribute("data-tab")); };
  });
  var guideClaude = document.getElementById("guideClaudeBtn");
  if (guideClaude) {
    guideClaude.onclick = function () {
      lastDeskNote = "claudeNote";
      var cn = document.getElementById("claudeNote");
      if (cn) cn.textContent = "Claude kapatılıyor, ayar yazılıyor, ardından Claude yeniden başlatılıyor…";
      send({ cmd: "launch-claude" });
    };
  }
  var guideChatgpt = document.getElementById("guideChatgptBtn");
  if (guideChatgpt) {
    guideChatgpt.onclick = function () {
      lastDeskNote = "chatgptNote";
      send({ cmd: "launch-chatgpt" });
    };
  }
  var guideGemini = document.getElementById("guideGeminiBtn");
  if (guideGemini) {
    guideGemini.onclick = function () {
      lastDeskNote = "geminiNote";
      send({ cmd: "launch-gemini" });
    };
  }
  var guideSetup = document.getElementById("guideSetupBtn");
  if (guideSetup) guideSetup.onclick = function () { switchTab("setup"); };
  var guideHist = document.getElementById("guideHistBtn");
  if (guideHist) guideHist.onclick = function () { switchTab("history"); };
  var GUIDE_ASK =
    "Ben dilekçeyi başka bir yerde, tek seferde yazdıracağım. Sen dilekçe yazma.\n" +
    "Mahkemeye sunulacak, usulüne uygun, çok iyi bir Türkçe dilekçe için bana tek seferlik bir yazım prompt’u çıkar.\n" +
    "Soru sorma. Parça parça anlatma. Yalnızca prompt’u ver.\n" +
    "Prompt; dava türü, mahkeme, DAVACI, DAVALI, TCKN, vekil, olay, talepler, adli yardım, ivedilik/YD, deliller için boş satırlar içersin.\n" +
    "Prompt’a şunu da yaz: sohbette dava gizliliği için takma ad ve farklı TC kullanılabilir; dilekçe bittikten sonra kullanıcı gerçek ad/TC’yi kendisi değiştirir.\n" +
    "Prompt’un sonunda şunu yaz: bilgileri doldurunca soru sormadan BetterSaul MCP ile dilekçeyi yaz; bilmediğin tanık, tutar veya tarihi uydurma.\n" +
    "Prompt’un en sonuna şunu da ekle: dilekçe BetterSaul Geçmiş’e kaydedilmediyse şu prompt’u ver — BetterSaul MCP ile dilekçeyi kaydet.";
  var GUIDE_PROMPT =
    "Aşağıdaki bilgiler tamam. Soru sorma. Parça parça sorma. BetterSaul MCP ile dilekçeyi yaz.\n" +
    "Bilmediğin tanık, tutar veya tarihi uydurma.\n\n" +
    "Dilekçe türü:\n" +
    "Mahkeme:\n" +
    "DAVACI (sohbette takma ad soyad):\n" +
    "DAVALI (sohbette takma ad):\n" +
    "TCKN (sohbette farklı / takma TC; gerçek TC yazma):\n" +
    "Vekil adı soyadı:\n" +
    "Baro / sicil no:\n" +
    "Büro adresi:\n" +
    "Telefon / e-posta:\n" +
    "Olay (ne oldu, nerede, ne zaman — yalnızca bildiğiniz):\n" +
    "Talepler:\n" +
    "Adli yardım: var / yok\n" +
    "İvedilik veya YD: var / yok\n" +
    "Harca esas değer (yalnızca gerçek; yoksa boş):\n" +
    "Eldeki deliller (yoksa yok yaz):\n" +
    "Tanık / resmi künye yoksa yazma, uydurma.\n" +
    "Dilekçe bitince kullanıcı takma ad ve takma TC’yi kendisi değiştirir.\n" +
    "Dilekçe BetterSaul Geçmiş’e kaydedilmediyse şu prompt’u vereceğim, uygula: BetterSaul MCP ile dilekçeyi kaydet.";
  var guideAsk = document.getElementById("guideAskPrompt");
  if (guideAsk) guideAsk.value = GUIDE_ASK;
  var guideAskCopy = document.getElementById("guideCopyAsk");
  if (guideAskCopy) {
    guideAskCopy.onclick = function () {
      var el = document.getElementById("guideAskNote");
      var done = function () { if (el) el.textContent = "Kopyalandı. Bunu başka bir yapay zekâya yapıştırın; dilekçe masaüstünde tek seferde yazılacak."; };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(GUIDE_ASK).then(done).catch(function () {
          if (el) el.textContent = "Kopyalanamadı; metni seçip kopyalayın.";
        });
      } else if (el) el.textContent = "Kopyalanamadı; metni seçip kopyalayın.";
    };
  }
  var guidePrompt = document.getElementById("guidePrompt");
  if (guidePrompt) guidePrompt.value = GUIDE_PROMPT;
  var guideCopy = document.getElementById("guideCopyPrompt");
  if (guideCopy) {
    guideCopy.onclick = function () {
      var n = document.getElementById("guideCopyNote");
      var t = (guidePrompt && guidePrompt.value) || GUIDE_PROMPT;
      var done = function () { if (n) n.textContent = "Şablon kopyalandı. Doldurup Claude, ChatGPT veya Gemini’ye tek mesajda yapıştırın; BetterSaul MCP ile dilekçeyi yaz deyin. Geçmiş’e düşmezse: BetterSaul MCP ile dilekçeyi kaydet."; };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(t).then(done).catch(function () {
          if (guidePrompt) { guidePrompt.focus(); guidePrompt.select(); }
          if (n) n.textContent = "Kopyalanamadı; metni seçip kopyalayın.";
        });
      } else {
        if (guidePrompt) { guidePrompt.focus(); guidePrompt.select(); }
        if (n) n.textContent = "Metni seçip kopyalayın.";
      }
    };
  }
  function fmtWhen(iso) {
    if (!iso) return "";
    var d = new Date(iso);
    if (isNaN(d.getTime())) return iso;
    return d.toLocaleString("tr-TR", { dateStyle: "short", timeStyle: "short" });
  }

  function loadHistory() {
    var q = (document.getElementById("histQ") && document.getElementById("histQ").value) || "";
    send({ cmd: "archive-list", kind: histKind, q: q.trim() });
  }

  function paintHistMeta(archive) {
    var el = document.getElementById("histMeta");
    if (!el) return;
    var p = archive && archive.petitions != null ? archive.petitions : "";
    var c = archive && archive.chats != null ? archive.chats : "";
    el.textContent = p !== "" ? (p + " dilekçe") : "";
  }

  function paintHistList(items) {
    histItems = items || [];
    var box = document.getElementById("histList");
    if (!box) return;
    if (!histItems.length) {
      box.innerHTML = '<p class="hist-empty" style="padding:14px">Kayıt yok. Sohbette dilekçe varsa yazın: BetterSaul MCP ile dilekçeyi kaydet.</p>';
      return;
    }
    box.innerHTML = histItems.map(function (it) {
      return (
        '<button type="button" class="hist-item' + (it.id === histSel ? " on" : "") + '" data-id="' + it.id + '">' +
          "<b>" + escPet(it.title || (histKind === "chat" ? "Sohbet" : "Dilekçe")) + "</b>" +
          "<small>" + escPet(fmtWhen(it.createdAt) + (it.petitionType ? " · " + it.petitionType : "") + (function () { var tm = findPetTiming(it); return tm ? " · " + fmtPetSure(tm.seconds) : ""; })() + (it.modelName ? " · " + it.modelName : "")) + "</small>" +
          "<span>" + escPet(it.preview || "") + "</span>" +
        "</button>"
      );
    }).join("");
    box.querySelectorAll(".hist-item").forEach(function (b) {
      b.onclick = function () {
        histSel = parseInt(b.getAttribute("data-id"), 10) || 0;
        send({ cmd: "archive-get", kind: histKind, id: histSel });
      };
    });
  }

  function paintHistItem(item) {
    var box = document.getElementById("histDetail");
    if (!box || !item) return;
    histSel = item.id || histSel;
    paintHistList(histItems);
    if (item.kind === "chat") {
      box.innerHTML =
        '<p class="hist-kicker">Sohbet prompt’u</p>' +
        "<h3>" + escPet(fmtWhen(item.createdAt)) + "</h3>" +
        '<p class="hist-meta">' + escPet(item.modelName || "") + "</p>" +
        '<div class="hist-actions"><button type="button" class="ghost" id="histDel">Sil</button></div>' +
        '<div class="hist-block"><h4>Prompt</h4><pre class="hist-pre">' + escPet(item.prompt) + "</pre></div>" +
        '<div class="hist-block"><h4>Yanıt</h4><pre class="hist-pre">' + escPet(item.reply) + "</pre></div>";
      document.getElementById("histDel").onclick = function () {
        if (confirm("Bu sohbet kaydı silinsin mi?")) send({ cmd: "archive-delete", kind: "chat", id: item.id });
      };
      return;
    }
    box.innerHTML =
      '<p class="hist-kicker">' + escPet(item.petitionType || "Dilekçe") + "</p>" +
      "<h3>" + escPet(item.title || "Dilekçe") + "</h3>" +
      '<p class="hist-meta">' + escPet(fmtWhen(item.createdAt) + (item.modelName ? " · " + item.modelName : "") + (function () { var tm = findPetTiming(item); return tm ? " · " + fmtPetSureDone(tm.seconds) + " hazırlandı" : ""; })()) + "</p>" +
      (item.pdfPath ? '<p class="hist-meta">PDF: ' + escPet(item.pdfPath) + "</p>" : "") +
      '<div class="hist-actions">' +
        '<button type="button" class="btn-ink" id="histPdf">PDF</button>' +
        '<button type="button" class="ghost" id="histDocx">Word (DOCX)</button>' +
        '<button type="button" class="ghost" id="histUdf">UYAP (UDF)</button>' +
        '<button type="button" class="ghost" id="histDel">Sil</button>' +
      "</div>" +
      '<p class="hist-meta">UDF uyarısı: UDF dosyası yalnızca editöre sürüklenerek açılır. Çift tıklamayın; UYAP Kelime İşlemci’yi açıp .udf dosyasını editörün üzerine sürükleyin.</p>' +
      '<div class="hist-block"><h4>Prompt / form</h4><pre class="hist-pre">' + escPet(item.prompt || "") + "</pre></div>" +
      (item.research
        ? '<div class="hist-block"><h4>İçtihat / tarama</h4><pre class="hist-pre">' + escPet(item.research) + "</pre></div>"
        : "") +
      '<div class="hist-block"><h4>Üretilen dilekçe</h4><article class="petition">' + petitionHtml(item.body || "") + "</article></div>";
    function exportPet(fmt) {
      lastPetText = item.body || "";
      var meta = document.getElementById("histMeta");
      if (meta) meta.textContent = fmt.toUpperCase() + " hazırlanıyor…";
      send({
        cmd: "export-petition",
        format: fmt,
        title: item.title || "dilekce",
        text: lastPetText,
        html: petitionHtml(lastPetText),
      });
    }
    document.getElementById("histPdf").onclick = function () { exportPet("pdf"); };
    document.getElementById("histDocx").onclick = function () { exportPet("docx"); };
    document.getElementById("histUdf").onclick = function () {
      alert("UDF uyarısı: UDF dosyası yalnızca editöre sürüklenerek açılır.\nÇift tıklamayın; UYAP Kelime İşlemci’yi açıp kaydettiğiniz .udf dosyasını editörün üzerine sürükleyin.");
      exportPet("udf");
    };
    document.getElementById("histDel").onclick = function () {
      if (confirm("Bu dilekçe kaydı silinsin mi?")) send({ cmd: "archive-delete", kind: "petition", id: item.id });
    };
  }

  function loadPetitionIntoForm(item) {
    var set = function (id, val) {
      var el = document.getElementById(id);
      if (el) el.value = val || "";
    };
    set("ptitle", item.title);
    set("ptype", item.petitionType);
    set("pcourt", item.court);
    set("pparties", item.parties);
    set("psummary", item.caseSummary);
    set("preq", item.requests);
    var packed = unpackPetitionPrompt(item.extraInstructions);
    set("pprompt", item.userPrompt || packed.prompt || extractPromptFromArchive(item.prompt));
    set("pextra", packed.extra);
    var wf = document.getElementById("pwebfluency");
    if (wf) wf.checked = packed.fluency !== false;
    set("plawyer", item.lawyerName);
    set("pbar", item.lawyerBar);
    set("pbarno", item.lawyerBarNo);
    set("plphone", item.lawyerPhone);
    set("pladdr", item.lawyerAddress);
    if (item.body) renderPetition(item.body);
    showPdfBtn();
    switchTab("history");
  }

  document.getElementById("histPetBtn").onclick = function () {
    histKind = "petition";
    histSel = 0;
    document.getElementById("histPetBtn").classList.add("on");
    document.getElementById("histDetail").innerHTML = '<p class="hist-empty">Soldan bir dilekçe seçin.</p>';
    loadHistory();
  };
  document.getElementById("histQ").oninput = function () {
    clearTimeout(histTimer);
    histTimer = setTimeout(loadHistory, 250);
  };

  ["chatLog", "tab-petition", "tab-setup", "histList", "histDetail"].forEach(function (id) {
    var el = document.getElementById(id);
    if (!el) return;
    el.addEventListener("wheel", function (ev) {
      if (el.scrollHeight <= el.clientHeight) return;
      el.scrollTop += ev.deltaY;
      ev.preventDefault();
    }, { passive: false });
  });

  function armLoginWait() {
    if (loginTimer) clearTimeout(loginTimer);
    loginTimer = setTimeout(function () {
      failAuth("Sunucu yanıt vermedi. İnternet bağlantınızı kontrol edip tekrar deneyin.");
    }, 25000);
  }

  function loginViaBridge(email, password) {
    try {
      var wv = webview();
      var host = wv && wv.hostObjects && wv.hostObjects.sync && wv.hostObjects.sync.bs;
      if (!host || !host.Login) return false;
      var raw = host.Login(email, password);
      onMsg(typeof raw === "string" ? JSON.parse(raw) : raw);
      return true;
    } catch (e) {
      return false;
    }
  }

  document.getElementById("form-login").addEventListener("submit", function (ev) {
    ev.preventDefault();
    ev.stopPropagation();
    var btn = document.getElementById("lbtn");
    document.getElementById("lerr").textContent = "";
    btn.disabled = true;
    btn.textContent = "Giriş yapılıyor…";
    armLoginWait();
    var email = document.getElementById("lemail").value.trim();
    var password = document.getElementById("lpassword").value;
    // Önce eşzamansız yol: arayüz donmaz. Senkron köprü yalnızca
    // mesaj kanalı yanıt vermezse 7 sn sonra yedek olarak denenir.
    send({ cmd: "login", email: email, password: password });
    if (loginBridgeTimer) clearTimeout(loginBridgeTimer);
    loginBridgeTimer = setTimeout(function () {
      loginBridgeTimer = null;
      var b = document.getElementById("lbtn");
      if (b && b.disabled) loginViaBridge(email, password);
    }, 7000);
    return false;
  });

  document.getElementById("form-reg").addEventListener("submit", function (ev) {
    ev.preventDefault();
    ev.stopPropagation();
    var btn = document.getElementById("rbtn");
    document.getElementById("rerr").textContent = "";
    btn.disabled = true;
    btn.textContent = "Hesap oluşturuluyor…";
    armLoginWait();
    send({
      cmd: "register",
      name: document.getElementById("rname").value.trim(),
      email: document.getElementById("remail").value.trim(),
      phone: document.getElementById("rphone").value.trim(),
      password: document.getElementById("rpassword").value,
      consent: document.getElementById("rconsent").checked,
    });
    return false;
  });

  document.getElementById("logout").onclick = function () { send({ cmd: "logout" }); };

  function addBubble(role, text) {
    var log = document.getElementById("chatLog");
    if (!log) return null;
    var el = document.createElement("div");
    el.className = "bubble " + (role === "user" ? "user" : "ai");
    el.textContent = text;
    log.appendChild(el);
    el.scrollIntoView({ block: "end" });
    return el;
  }

  function endChat(status) {
    chatBusy = false;
    if (chatWatch) { clearTimeout(chatWatch); chatWatch = null; }
    var btn = document.getElementById("chatBtn");
    if (btn) btn.disabled = false;
    if (status != null) document.getElementById("chatStatus").textContent = status;
  }

  function armChatWatch() {
    if (chatWatch) clearTimeout(chatWatch);
    chatWatch = setTimeout(function () {
      if (!chatBusy) return;
      endChat("Yanıt ekranda. Yeni mesaj yazabilirsiniz.");
    }, 120000);
  }

  var ptypeEl = document.getElementById("ptype");
  if (ptypeEl) ptypeEl.onchange = function () { applyTypeHints(true); };

  var petForm = document.getElementById("form-petition");
  if (petForm) petForm.onsubmit = function (ev) {
    ev.preventDefault();
    if (petBusy) return;
    var gaps = hmk119Gaps();
    if (gaps.length) {
      document.getElementById("pstatus").textContent =
        "HMK m. 119: " + gaps.join(", ") + " yazılmadan dilekçe üretilemez (mahkeme kesin süre verir).";
      return;
    }
    petBusy = true;
    startPetSure();
    petOut.textContent = "Derin içtihat taraması ve dilekçe hazırlanıyor…";
    var rs = document.getElementById("presearch");
    if (rs) { rs.hidden = false; rs.textContent = "BetterSaul MCP derin tarama başlıyor…\n"; }
    document.getElementById("pbtn").disabled = true;
    document.getElementById("pstatus").textContent = "Resmî kaynaklar derin taranıyor…";
    var lawyer = readLawyer();
    document.getElementById("ppdf").hidden = true;
    var extra = document.getElementById("pextra").value.trim();
    var userPrompt = ((document.getElementById("pprompt") || {}).value || "").trim();
    var usul = [];
    if (document.getElementById("pivedi").checked) usul.push("İVEDİ VE ÖNCELİKLİ İNCELEME");
    if (document.getElementById("pyd").checked) usul.push("YÜRÜTMEYİ DURDURMA");
    if (document.getElementById("padli").checked) usul.push("ADLİ YARDIM");
    if (document.getElementById("ptedbir").checked) usul.push("İHTİYATİ TEDBİR");
    if (document.getElementById("phaciz").checked) usul.push("İHTİYATİ HACİZ");
    if (usul.length) extra = (extra + "\n" + usul.join("\n")).trim();
    extra = packPetitionPrompt(extra, userPrompt);
    extra = (extra + "\nWEB_FLUENCY:" + (document.getElementById("pwebfluency") && document.getElementById("pwebfluency").checked ? "1" : "0")).trim();
    send({
      cmd: "petition",
      title: document.getElementById("ptitle").value.trim(),
      petitionType: document.getElementById("ptype").value,
      templateId: document.getElementById("ptpl").value,
      templateName: document.getElementById("ptpl").selectedOptions[0]
        ? document.getElementById("ptpl").selectedOptions[0].textContent
        : "",
      templateHint: document.getElementById("ptpl").selectedOptions[0]
        ? (document.getElementById("ptpl").selectedOptions[0].dataset.desc || "")
        : "",
      court: document.getElementById("pcourt").value.trim(),
      parties: document.getElementById("pparties").value.trim(),
      caseSummary: document.getElementById("psummary").value.trim(),
      requests: document.getElementById("preq").value.trim(),
      extraInstructions: extra,
      userPrompt: userPrompt,
      webFluency: !!(document.getElementById("pwebfluency") && document.getElementById("pwebfluency").checked),
      claimValues: readClaimValues(),
      lawyerName: lawyer.lawyerName,
      lawyerBar: lawyer.lawyerBar,
      lawyerBarNo: lawyer.lawyerBarNo,
      lawyerAddress: lawyer.lawyerAddress,
      lawyerPhone: lawyer.lawyerPhone,
      lawyerEmail: lawyer.lawyerEmail,
    });
  };

  var ppdfEl = document.getElementById("ppdf");
  if (ppdfEl) ppdfEl.onclick = function () {
    var text = (lastPetText || petOut.innerText || "").trim();
    if (!text) return;
    document.getElementById("pstatus").textContent = "PDF hazırlanıyor…";
    send({
      cmd: "save-pdf",
      title: document.getElementById("ptitle").value.trim(),
      text: text,
      html: petOut.innerHTML || petitionHtml(text),
    });
  };

  function mcpFields() {
    var url = (document.getElementById("mcpUrl").value || "").trim() || "https://127.0.0.1:8000/mcp";
    var port = 8000;
    var m = url.match(/:(\d+)/);
    if (m) port = parseInt(m[1], 10) || 8000;
    return { url: url, port: port, autoStart: !!document.getElementById("mcpAuto").checked };
  }

  function renderMcp(mcp) {
    if (!mcp) return;
    if (mcp.url) document.getElementById("mcpUrl").value = mcp.url;
    if (typeof mcp.autoStart === "boolean") document.getElementById("mcpAuto").checked = mcp.autoStart;
    var el = document.getElementById("mcpState");
    var note = document.getElementById("mcpNote");
    var ok = !!(mcp.connected || (mcp.running && mcp.toolCount));
    el.classList.toggle("ok", ok);
    el.classList.toggle("bad", !ok);
    if (ok) {
      el.textContent = "BetterSaul MCP açık · " + (mcp.toolCount || 0) + " araç hazır.";
    } else if (mcp.running) {
      el.textContent = "MCP açıldı, araçlar yükleniyor…";
    } else if (mcp.error) {
      el.textContent = "MCP açılamadı: " + mcp.error;
    } else {
      el.textContent = "BetterSaul MCP başlatılıyor…";
    }
    var tools = Array.isArray(mcp.tools) ? mcp.tools.filter(Boolean).join(", ") : "";
    note.textContent = tools || mcp.detail || mcp.error || "";
  }

  document.getElementById("mcpStart").onclick = function () {
    document.getElementById("mcpNote").textContent = "BetterSaul MCP başlatılıyor…";
    send(Object.assign({ cmd: "mcp-start" }, mcpFields()));
  };
  document.getElementById("mcpStop").onclick = function () {
    send({ cmd: "mcp-stop" });
  };
  document.getElementById("mcpTest").onclick = function () {
    document.getElementById("mcpNote").textContent = "Bağlantı deneniyor…";
    send(Object.assign({ cmd: "mcp-test" }, mcpFields()));
  };
  document.getElementById("mcpAuto").onchange = function () {
    send(Object.assign({ cmd: "mcp-save" }, mcpFields()));
  };

  function renderHardware(hw, connect) {
    lastHw = hw || lastHw;
    if (connect) renderConnect(connect);
    var box = document.getElementById("hwBox");
    if (box) box.hidden = true;
    var title = document.getElementById("setupTitle");
    var stage = document.getElementById("setupStage");
    var kicker = document.getElementById("setupKicker");
    var btn = document.getElementById("setupBtn");
    if (title && !document.querySelector(".wiz.ready")) title.textContent = "Masaüstü + MCP";
    if (kicker && !setupBusy) kicker.textContent = "Kurulum";
    if (btn && !setupBusy) btn.textContent = "Kurulumu başlat";
    if (stage && !setupBusy && !document.querySelector(".wiz.ready"))
      stage.textContent = "BetterSaul MCP kurulur. Claude, ChatGPT veya Gemini ayarı yazılırken o uygulama kapanır; yazılınca yeniden açılır.";
    renderClaude({ mcpConnect: lastConnect });
  }

  function renderConnect(c) {
    lastConnect = c || lastConnect;
    c = lastConnect;
    if (!c) return;
    var url = document.getElementById("connectUrl");
    var stdio = document.getElementById("connectStdio");
    var claude = document.getElementById("connectClaude");
    if (url) url.value = c.url || "";
    if (stdio) stdio.value = c.stdioCommand || "";
    if (claude) claude.value = c.claudeJson || "";
    var gpt = document.getElementById("connectChatgpt");
    var gem = document.getElementById("connectGemini");
    if (gpt) gpt.value = c.chatgptJson || "";
    if (gem) gem.value = c.geminiJson || "";
  }

  function copyText(t, note) {
    var el = document.getElementById("connectNote");
    var done = function () { if (el) el.textContent = note || "Kopyalandı."; };
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(t || "").then(done).catch(function () {
        if (el) el.textContent = "Kopyalanamadı; metni seçip kopyalayın.";
      });
    } else if (el) el.textContent = "Kopyalanamadı; metni seçip kopyalayın.";
  }

  var copyBtn = document.getElementById("connectCopy");
  if (copyBtn) {
    copyBtn.onclick = function () {
      copyText((lastConnect && lastConnect.claudeJson) || (document.getElementById("connectClaude") || {}).value, "Claude JSON kopyalandı. claude_desktop_config.json içine yapıştırın.");
    };
  }
  function askDeskConsent(app, path, extra) {
    return confirm(
      "Erişim izni gerekli — " + app + "\n\n" +
      "Onay verirseniz şunlar yapılır:\n" +
      "• " + app + " (arka plan dahil) kapatılır ve yeniden başlatılır.\n" +
      "• Şu ayar dosyasına BetterSaul MCP kaydı eklenir (mevcut ayarlarınız silinmez):\n   " + path + "\n" +
      (extra ? "• " + extra + "\n" : "") +
      "\nBu işlemi onaylıyor musunuz?"
    );
  }
  var CONSENT_CLAUDE = ["Claude Desktop", "%APPDATA%\\Claude\\claude_desktop_config.json", ""];
  var CONSENT_CHATGPT = ["ChatGPT Desktop", "%USERPROFILE%\\.codex\\config.toml",
    "Türkçe hukuki taleplerde BetterSaul kullanılması talimatı ve BetterSaul araçlarının onaysız (auto) çalışması ayarı eklenir."];
  var CONSENT_GEMINI = ["Gemini Desktop", "%USERPROFILE%\\.gemini\\settings.json", ""];
  var claudeBtn = document.getElementById("connectClaudeBtn");
  if (claudeBtn) {
    claudeBtn.onclick = function () {
      if (!askDeskConsent(CONSENT_CLAUDE[0], CONSENT_CLAUDE[1], CONSENT_CLAUDE[2])) return;
      lastDeskNote = "claudeNote";
      var n = document.getElementById("connectNote");
      if (n) n.textContent = "Claude kapatılıyor, ayar yazılıyor…";
      var cn = document.getElementById("claudeNote");
      if (cn) cn.textContent = "Claude kapatılıyor, ayar yazılıyor, ardından Claude yeniden başlatılıyor…";
      send({ cmd: "mcp-install-claude" });
    };
  }
  var claudeDl = document.getElementById("claudeDownloadBtn");
  if (claudeDl) {
    claudeDl.onclick = function () {
      lastDeskNote = "claudeNote";
      var cn = document.getElementById("claudeNote");
      if (cn) cn.textContent = "Claude Desktop indirme sayfası açılıyor…";
      send({ cmd: "open-claude-download" });
    };
  }
  var claudeLaunch = document.getElementById("claudeLaunchBtn");
  if (claudeLaunch) {
    claudeLaunch.onclick = function () {
      if (!askDeskConsent(CONSENT_CLAUDE[0], CONSENT_CLAUDE[1], CONSENT_CLAUDE[2])) return;
      lastDeskNote = "claudeNote";
      var cn = document.getElementById("claudeNote");
      if (cn) cn.textContent = "Claude kapatılıyor, ayar yazılıyor, sonra Claude açılıyor…";
      send({ cmd: "launch-claude" });
    };
  }
  var chatgptBtn = document.getElementById("connectChatgptBtn");
  if (chatgptBtn) {
    chatgptBtn.onclick = function () {
      if (!askDeskConsent(CONSENT_CHATGPT[0], CONSENT_CHATGPT[1], CONSENT_CHATGPT[2])) return;
      lastDeskNote = "chatgptNote";
      var n = document.getElementById("chatgptNote");
      if (n) n.textContent = "ChatGPT kapatılıyor, ayar yazılıyor, ardından yeniden başlatılıyor…";
      send({ cmd: "mcp-install-chatgpt" });
    };
  }
  var chatgptDl = document.getElementById("chatgptDownloadBtn");
  if (chatgptDl) {
    chatgptDl.onclick = function () {
      lastDeskNote = "chatgptNote";
      var n = document.getElementById("chatgptNote");
      if (n) n.textContent = "ChatGPT Desktop indirme sayfası açılıyor…";
      send({ cmd: "open-chatgpt-download" });
    };
  }
  var chatgptLaunch = document.getElementById("chatgptLaunchBtn");
  if (chatgptLaunch) {
    chatgptLaunch.onclick = function () {
      if (!askDeskConsent(CONSENT_CHATGPT[0], CONSENT_CHATGPT[1], CONSENT_CHATGPT[2])) return;
      lastDeskNote = "chatgptNote";
      var n = document.getElementById("chatgptNote");
      if (n) n.textContent = "ChatGPT kapatılıyor, ayar yazılıyor, sonra açılıyor…";
      send({ cmd: "launch-chatgpt" });
    };
  }
  var geminiBtn = document.getElementById("connectGeminiBtn");
  if (geminiBtn) {
    geminiBtn.onclick = function () {
      if (!askDeskConsent(CONSENT_GEMINI[0], CONSENT_GEMINI[1], CONSENT_GEMINI[2])) return;
      lastDeskNote = "geminiNote";
      var n = document.getElementById("geminiNote");
      if (n) n.textContent = "Gemini kapatılıyor, ayar yazılıyor, ardından yeniden başlatılıyor…";
      send({ cmd: "mcp-install-gemini" });
    };
  }
  var geminiDl = document.getElementById("geminiDownloadBtn");
  if (geminiDl) {
    geminiDl.onclick = function () {
      lastDeskNote = "geminiNote";
      var n = document.getElementById("geminiNote");
      if (n) n.textContent = "Gemini Desktop indirme sayfası açılıyor…";
      send({ cmd: "open-gemini-download" });
    };
  }
  function bindDeskRemove(btnId, app, label, path, noteId) {
    var b = document.getElementById(btnId);
    if (!b) return;
    b.onclick = function () {
      if (!confirm(
        "BetterSaul, " + label + " ayarlarından silinsin mi?\n\n" +
        "Şu dosyadan yalnızca BetterSaul MCP kaydı kaldırılır:\n" + path + "\n\n" +
        label + " uygulamasının kendisine ve diğer ayarlarına dokunulmaz. " +
        "Değişikliğin geçerli olması için " + label + " uygulamasını kapatıp yeniden açın.\n\n" +
        "Silmeyi onaylıyor musunuz?")) return;
      lastDeskNote = noteId;
      var n = document.getElementById(noteId);
      if (n) n.textContent = "BetterSaul kaydı " + label + " ayarlarından siliniyor…";
      send({ cmd: "desk-remove", app: app });
    };
  }
  bindDeskRemove("claudeRemoveBtn", "claude", "Claude", CONSENT_CLAUDE[1], "claudeNote");
  bindDeskRemove("chatgptRemoveBtn", "chatgpt", "ChatGPT", CONSENT_CHATGPT[1], "chatgptNote");
  bindDeskRemove("geminiRemoveBtn", "gemini", "Gemini", CONSENT_GEMINI[1], "geminiNote");
  var geminiLaunch = document.getElementById("geminiLaunchBtn");
  if (geminiLaunch) {
    geminiLaunch.onclick = function () {
      if (!askDeskConsent(CONSENT_GEMINI[0], CONSENT_GEMINI[1], CONSENT_GEMINI[2])) return;
      lastDeskNote = "geminiNote";
      var n = document.getElementById("geminiNote");
      if (n) n.textContent = "Gemini kapatılıyor, ayar yazılıyor, sonra açılıyor…";
      send({ cmd: "launch-gemini" });
    };
  }
  var gptCopy = document.getElementById("connectChatgptCopy");
  if (gptCopy) {
    gptCopy.onclick = function () {
      copyText((lastConnect && lastConnect.chatgptJson) || "", "ChatGPT JSON kopyalandı.");
    };
  }
  var gemCopy = document.getElementById("connectGeminiCopy");
  if (gemCopy) {
    gemCopy.onclick = function () {
      copyText((lastConnect && lastConnect.geminiJson) || "", "Gemini JSON kopyalandı.");
    };
  }
  var cursorBtn = document.getElementById("connectCursorCopy");
  if (cursorBtn) {
    cursorBtn.onclick = function () {
      copyText((lastConnect && lastConnect.cursorJson) || "", "Cursor MCP JSON kopyalandı.");
    };
  }

  document.getElementById("setupBtn").onclick = function () {
    if (setupBusy) return;
    setupBusy = true;
    document.getElementById("setupBtn").disabled = true;
    document.getElementById("setupBtn").textContent = "Kuruluyor…";
    var setupLog = el("setupLog");
    if (setupLog) setupLog.textContent = "";
    lastSetupLog = "";
    markPhase(1);
    document.getElementById("setupStage").textContent = "Ortam ve BetterSaul MCP kuruluyor.";
    startSetupClock();
    send({ cmd: "setup" });
  };

  function resetLoginButtons() {
    if (loginTimer) { clearTimeout(loginTimer); loginTimer = null; }
    if (loginBridgeTimer) { clearTimeout(loginBridgeTimer); loginBridgeTimer = null; }
    var lbtn = document.getElementById("lbtn");
    var rbtn = document.getElementById("rbtn");
    lbtn.disabled = false;
    lbtn.textContent = "Giriş yap";
    rbtn.disabled = false;
    rbtn.textContent = "Hesap oluştur";
  }

  function onMsg(m) {
    if (typeof m === "string") {
      try { m = JSON.parse(m); } catch (e) { return; }
    }
    if (!m) return;
    if ((m.event === "login-ok" || m.ok) && m.user) {
      resetLoginButtons();
      applySession(m);
      return;
    }
    if (!m.event) return;
    if (m.event === "update-required" || m.updateRequired) {
      showUpdateWall(m);
      return;
    }
    if (m.event === "boot" || m.event === "session") {
      if (m.updateRequired) {
        showUpdateWall(m);
        return;
      }
      if (m.user) applySession(m);
      else show("login");
      return;
    }
    if (m.event === "login-ok") {
      resetLoginButtons();
      applySession(m);
      return;
    }
    if (m.event === "login-err") {
      failAuth(m.error || "İşlem başarısız");
      return;
    }
    if (m.event === "logout-ok") {
      show("login");
      if (petOut) petOut.textContent = "";
      return;
    }
    if (m.event === "chat-delta") {
      var piece = stripJunk(m.text || "");
      if (!piece) return;
      if (!chatAi) chatAi = addBubble("ai", "");
      chatAi.textContent += piece;
      chatAi.scrollIntoView({ block: "end" });
      armChatWatch();
      return;
    }
    if (m.event === "chat-status" || m.event === "chat-research") {
      document.getElementById("chatStatus").textContent = m.text || "";
      var tr = document.getElementById("chatTrace");
      if (tr && (m.text || "").trim()) {
        tr.hidden = false;
        tr.textContent += m.text + "\n";
        tr.scrollTop = tr.scrollHeight;
      }
      if (chatBusy) armChatWatch();
      return;
    }
    if (m.event === "chat-done" || m.event === "chat-err") {
      if (m.event === "chat-done") {
        var clean = stripJunk(m.text || "");
        if (clean && chatAi) chatAi.textContent = clean;
      }
      endChat(m.event === "chat-err" ? (m.error || m.text || "") : "Yanıt hazır.");
      if (m.event === "chat-done") send({ cmd: "archive-list", kind: "chat", q: "" });
      return;
    }
    if (chatBusy && (/-done$/.test(m.event) || /-err$/.test(m.event))) {
      endChat("Yanıt hazır.");
      return;
    }
    if (m.event === "petition-delta") {
      return;
    }
    if (m.event === "petition-research") {
      var box = document.getElementById("presearch");
      if (box) {
        box.hidden = false;
        box.textContent += (m.text || "") + "\n";
        box.scrollTop = box.scrollHeight;
      }
      document.getElementById("pstatus").textContent = m.text || "";
      return;
    }
    if (m.event === "petition-status") {
      document.getElementById("pstatus").textContent = m.text || "";
      if (petBusy && petOut && /HMK m\. 119|hazırlanıyor|derin içtihat/i.test(petOut.textContent || ""))
        petOut.textContent = (m.text || "Dilekçe hazırlanıyor…");
      var st = m.text || "";
      if (/^\d+\.\s/.test(st) || st.indexOf("→") >= 0 || st.indexOf("Tarama") >= 0 || st.indexOf("MCP") >= 0 || st.indexOf("Model") >= 0) {
        var box2 = document.getElementById("presearch");
        if (box2) {
          box2.hidden = false;
          box2.textContent += st + "\n";
          box2.scrollTop = box2.scrollHeight;
        }
      }
      return;
    }
    if (m.event === "petition-done" || m.event === "petition-err") {
      petBusy = false;
      var pbtn = document.getElementById("pbtn");
      if (pbtn) pbtn.disabled = false;
      if (m.event === "petition-done") send({ cmd: "archive-list", kind: "petition", q: "" });
      return;
    }
    if (m.event === "pdf-ok" || m.event === "export-ok") {
      var hmOk = document.getElementById("histMeta");
      if (hmOk) {
        hmOk.textContent = (m.format === "udf")
          ? ("UDF kaydedildi: " + (m.text || "") + " — UDF dosyası yalnızca editöre sürüklenerek açılır; çift tıklamayın. UYAP Kelime İşlemci’yi açıp dosyayı sürükleyin.")
          : ("Kaydedildi: " + (m.text || ""));
      }
      return;
    }
    if (m.event === "archive-list") {
      paintHistMeta(m.archive);
      paintHistList(m.items || []);
      return;
    }
    if (m.event === "archive-item") {
      paintHistItem(m.item);
      return;
    }
    if (m.event === "archive-deleted") {
      paintHistMeta(m.archive);
      document.getElementById("histDetail").innerHTML = '<p class="hist-empty">Kayıt silindi.</p>';
      histSel = 0;
      loadHistory();
      return;
    }
    if (m.event === "archive-err") {
      var hm = document.getElementById("histMeta");
      if (hm) hm.textContent = m.error || "Arşiv okunamadı.";
      return;
    }
    if (m.event === "pdf-err" || m.event === "export-err") {
      var hmErr = document.getElementById("histMeta");
      if (hmErr) hmErr.textContent = m.error || "Dosya kaydedilemedi.";
      return;
    }
    if (m.event === "setup-log") {
      var line = m.text || "";
      if (line && line === lastSetupLog) return;
      lastSetupLog = line;
      var pre = document.getElementById("setupLog");
      if (!pre) return;
      pre.textContent += line + "\n";
      pre.scrollTop = pre.scrollHeight;
      return;
    }
    if (m.event === "setup-progress") {
      var pct = Math.max(0, Math.min(100, m.pct || 0));
      var phase = phaseOf(pct, m.stage);
      markPhase(phase);
      var stageEl = el("setupStage");
      if (m.stage && phase === 2 && stageEl) {
        stageEl.textContent = "BetterSaul MCP ve Python paketleri kuruluyor.";
      } else if (m.stage && phase === 3 && stageEl) {
        stageEl.textContent = "Masaüstü ayarları yazılıyor. Yoksa Kurulum’dan indirin.";
      }
      if (m.got) {
        var now = Date.now();
        if (setupLastGot && m.got > setupLastGot && now > setupLastAt) {
          var bps = (m.got - setupLastGot) / ((now - setupLastAt) / 1000);
        }
        setupLastGot = m.got;
        setupLastAt = now;
      }
      return;
    }
    if (m.event === "setup-done") {
      setupBusy = false;
      stopSetupClock();
      renderHardware(m.hardware, m.mcpConnect);
      renderClaude(m);
      if (m.setupReady) {
        markPhase(4);
      }
      document.getElementById("setupBtn").textContent = "Kurulumu başlat";
      setReady(!!m.setupReady);
      renderMcp(m.mcp);
      send({ cmd: "mcp-status" });
      return;
    }
    if (m.event === "hw-status" || m.event === "mcp-connect") {
      renderHardware(m.hardware, m.mcpConnect);
      if (m.mcp) renderMcp(m.mcp);
      renderClaude(m);
      if (m.detail || m.error) {
        var n = document.getElementById("connectNote");
        if (n) n.textContent = m.error || m.detail || "";
        var cn = document.getElementById(lastDeskNote);
        if (cn) cn.textContent = m.error || m.detail || "";
      }
      if (typeof m.setupReady === "boolean") setReady(!!m.setupReady);
      return;
    }
    if (m.event === "mcp-status") {
      renderMcp(m.mcp || m);
      if (m.mcpConnect || typeof m.claudeInstalled === "boolean" || typeof m.chatgptInstalled === "boolean" || typeof m.geminiInstalled === "boolean") renderClaude(m);
      return;
    }
  }

  (function initClaims() {
    var tb = document.querySelector("#ziynetTable tbody");
    if (tb && !tb.children.length) {
      addZiynetRow();
      addZiynetRow();
    }
    var addBtn = document.getElementById("ziynetAdd");
    if (addBtn) addBtn.onclick = function () { addZiynetRow(); };
    ["pamt-maddi", "pamt-manevi", "pamt-kidem", "pamt-ihbar", "pamt-mesai", "pamt-ubgt", "pamt-izin", "pamt-alacak"].forEach(function (id) {
      var el = document.getElementById(id);
      if (el) el.addEventListener("input", syncHarc);
    });
    var harc = document.getElementById("pamt-harc");
    if (harc) {
      harc.addEventListener("input", function () {
        harc.dataset.manual = /\d/.test(harc.value) ? "1" : "";
      });
    }
    var pt = document.getElementById("ptype");
    if (pt) showClaimGroups(pt.value);
  })();

  window.__bsMsg = onMsg;
  var wv = webview();
  if (wv) {
    wv.addEventListener("message", function (ev) { onMsg(ev.data); });
    send({ cmd: "ready" });
  } else {
    show("login");
    document.getElementById("lerr").textContent = "Bu sayfa BetterSaul.exe içinde açılmalı.";
  }
})();
