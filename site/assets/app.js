/* DealRadar front end.
   Loads one static JSON file and does everything else in the browser:
   filtering, sorting, saved deals, deal detail with price history.
   No framework, no build step: a GitHub Pages site is just files. */

(function () {
  "use strict";

  var DATA_URL = "data/deals.json";
  var PAGE = 48;
  var DAY = 864e5;

  var CATEGORY_LABELS = {
    "computers": "Computers", "tv-audio": "TV & Audio",
    "phones-tablets": "Phones & Tablets", "gaming": "Gaming",
    "home": "Home & Kitchen", "apparel": "Fashion", "beauty": "Beauty",
    "toys": "Toys",
    "tools": "Tools", "other": "More"
  };

  var $ = function (id) { return document.getElementById(id); };
  var el = {
    q: $("q"), cats: $("cats"), stores: $("stores"), storeFilter: $("storeFilter"),
    deals: $("deals"), sentinel: $("sentinel"), empty: $("empty"),
    emptyTitle: $("emptyTitle"), emptyBody: $("emptyBody"),
    count: $("count"), heroStats: $("heroStats"), active: $("activeFilters"),
    sort: $("sort"), pmin: $("pmin"), pmax: $("pmax"),
    onlyNew: $("onlyNew"), onlyLowest: $("onlyLowest"),
    discountChips: $("discountChips"), priceChips: $("priceChips"),
    viewGrid: $("viewGrid"), viewList: $("viewList"),
    sidebar: $("sidebar"), filterCount: $("filterCount"),
    savedBtn: $("savedBtn"), savedCount: $("savedCount"),
    modal: $("modal"), modalBody: $("modalBody"),
    toast: $("toast"), toTop: $("toTop"),
    event: $("event"), eventName: $("eventName"), eventClock: $("eventClock"), eventNote: $("eventNote"),
    notice: $("sampleNotice"), attribution: $("attribution")
  };

  var state = {
    all: [], byId: {}, filtered: [], shown: 0, now: Date.now(),
    q: "", cat: "", stores: [], minPct: 0, pmin: null, pmax: null,
    onlyNew: false, onlyLowest: false, savedOnly: false,
    sort: "hot", view: localStorage.getItem("dr-view") || "grid", hotCut: Infinity
  };

  var saved = loadSaved();

  /* ---------- Helpers ---------- */

  function esc(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }
  function safeUrl(u) { return /^https?:\/\//i.test(u || "") ? u : "#"; }
  function money(n) {
    if (n === null || n === undefined) return "";
    return "$" + n.toLocaleString("en-US", {
      minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2
    });
  }
  function ago(ms) {
    var m = Math.round(ms / 6e4);
    if (m < 1) return "just now";
    if (m < 60) return m + " min ago";
    var h = Math.round(m / 60);
    if (h < 24) return h + (h === 1 ? " hour ago" : " hours ago");
    var d = Math.round(h / 24);
    return d + (d === 1 ? " day ago" : " days ago");
  }
  function debounce(fn, ms) {
    var t; return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }
  function icon(path, extra) {
    return '<svg viewBox="0 0 24 24" aria-hidden="true"' + (extra || "") + ">" + path + "</svg>";
  }
  var I = {
    heart: '<path d="M12 20.5s-7.5-4.6-7.5-10.2A4.3 4.3 0 0 1 12 7.6a4.3 4.3 0 0 1 7.5 2.7c0 5.6-7.5 10.2-7.5 10.2z"/>',
    out: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
    x: '<path d="M6 6l12 12M18 6 6 18"/>',
    share: '<circle cx="18" cy="5" r="2.5"/><circle cx="6" cy="12" r="2.5"/><circle cx="18" cy="19" r="2.5"/><path d="m8.2 10.8 7.6-4.4M8.2 13.2l7.6 4.4"/>'
  };

  function loadSaved() {
    try { return JSON.parse(localStorage.getItem("dr-saved") || "[]"); }
    catch (e) { return []; }
  }
  function isSaved(id) { return saved.indexOf(id) !== -1; }
  function toggleSaved(id) {
    var i = saved.indexOf(id);
    if (i === -1) saved.push(id); else saved.splice(i, 1);
    localStorage.setItem("dr-saved", JSON.stringify(saved));
    updateSavedCount();
    toast(i === -1 ? "Saved. Find it under the heart icon." : "Removed from saved");
    return i === -1;
  }
  function updateSavedCount() {
    var n = saved.filter(function (id) { return state.byId[id]; }).length;
    el.savedCount.textContent = n;
    el.savedCount.hidden = n === 0;
  }

  var toastTimer;
  function toast(msg) {
    el.toast.textContent = msg;
    el.toast.classList.add("is-on");
    clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.toast.classList.remove("is-on"); }, 2200);
  }

  /* ---------- Derived fields ---------- */

  function prepare(d) {
    var first = d.first_seen ? Date.parse(d.first_seen) : null;
    d._new = first !== null && state.now - first < DAY;
    d._firstMs = first || 0;
    d._text = (d.title + " " + d.store + " " + (CATEGORY_LABELS[d.category] || "")).toLowerCase();
    // "Hot": percentage off leads, real dollars and freshness lift it.
    d._hot = (d.discount_pct || 0) +
      12 * Math.log10(1 + (d.savings || 0)) +
      (d._new ? 10 : 0) + (d.is_lowest ? 8 : 0);
    return d;
  }

  /* ---------- Filtering & sorting ---------- */

  var SORTS = {
    hot: function (a, b) { return b._hot - a._hot; },
    pct: function (a, b) { return (b.discount_pct || 0) - (a.discount_pct || 0) || (b.savings || 0) - (a.savings || 0); },
    save: function (a, b) { return (b.savings || 0) - (a.savings || 0); },
    "new": function (a, b) { return b._firstMs - a._firstMs || b._hot - a._hot; },
    low: function (a, b) { return (a.price || 0) - (b.price || 0); },
    high: function (a, b) { return (b.price || 0) - (a.price || 0); }
  };

  function matches(d, skip) {
    if (state.savedOnly && !isSaved(d.id)) return false;
    if (skip !== "cat" && state.cat && d.category !== state.cat) return false;
    if (skip !== "store" && state.stores.length && state.stores.indexOf(d.store) === -1) return false;
    if (state.minPct && (d.discount_pct || 0) < state.minPct) return false;
    if (state.pmin !== null && (d.price || 0) < state.pmin) return false;
    if (state.pmax !== null && (d.price || 0) > state.pmax) return false;
    if (state.onlyNew && !d._new) return false;
    if (state.onlyLowest && !d.is_lowest) return false;
    if (state.q) {
      var words = state.q.split(/\s+/);
      for (var i = 0; i < words.length; i++) if (d._text.indexOf(words[i]) === -1) return false;
    }
    return true;
  }

  function apply(opts) {
    state.filtered = state.all.filter(function (d) { return matches(d); })
      .sort(SORTS[state.sort] || SORTS.hot);
    state.shown = 0;
    el.deals.innerHTML = "";
    renderMore();
    renderCats();
    renderStores();
    renderActive();
    renderCount();
    syncUrl();
    if (!opts || !opts.keepScroll) {
      var top = el.deals.getBoundingClientRect().top + scrollY - 190;
      if (scrollY > top) scrollTo({ top: top });
    }
  }

  /* ---------- Rendering ---------- */

  function card(d) {
    var pct = d.discount_pct;
    var tags = [];
    if (d.is_lowest) tags.push('<span class="tag tag-low">Lowest price</span>');
    if (d._new) tags.push('<span class="tag tag-new">New</span>');
    if (d._hot >= state.hotCut) tags.push('<span class="tag tag-hot">Hot</span>');

    var img = d.image
      ? '<img class="dr-img" src="' + esc(safeUrl(d.image)) + '" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">'
      : '<span class="thumb-fallback">' + esc((d.store || "?").charAt(0)) + "</span>";

    var savedNow = isSaved(d.id);
    return '<li><article class="card" data-id="' + esc(d.id) + '">' +
      '<button class="save-btn" type="button" aria-pressed="' + savedNow + '" aria-label="' +
        (savedNow ? "Remove from saved" : "Save deal") + '">' + icon(I.heart) + "</button>" +
      '<button class="card-open" type="button" aria-label="Details: ' + esc(d.title) + '">' +
        '<div class="thumb">' +
          (pct ? '<span class="off' + (pct >= 50 ? " is-deep" : "") + '">&minus;' + pct + "%</span>" : "") +
          img +
        "</div>" +
        '<div class="card-body">' +
          (tags.length ? '<div class="tags">' + tags.join("") + "</div>" : "") +
          '<span class="card-store">' + esc(d.store) + "</span>" +
          '<h3 class="card-title">' + esc(d.title) + "</h3>" +
          '<div class="card-prices">' +
            '<span class="price">' + money(d.price) + "</span>" +
            (d.list_price > d.price ? '<span class="was">' + money(d.list_price) + "</span>" : "") +
            (d.savings ? '<span class="saved">You save ' + money(d.savings) + "</span>" : "") +
          "</div>" +
        "</div>" +
      "</button>" +
      '<div class="card-foot"><a class="get" href="' + esc(safeUrl(d.url)) +
        '" target="_blank" rel="nofollow sponsored noopener">Get deal ' + icon(I.out) + "</a></div>" +
    "</article></li>";
  }

  function renderMore() {
    var next = state.filtered.slice(state.shown, state.shown + PAGE);
    el.deals.insertAdjacentHTML("beforeend", next.map(card).join(""));
    state.shown += next.length;
    el.deals.setAttribute("aria-busy", "false");
    var none = state.filtered.length === 0;
    el.empty.hidden = !none;
    if (none) {
      if (state.savedOnly && !saved.length) {
        el.emptyTitle.textContent = "No saved deals yet.";
        el.emptyBody.textContent = "Tap the heart on any deal to keep it here.";
      } else {
        el.emptyTitle.textContent = "No deals match those filters.";
        el.emptyBody.textContent = "Try a broader search or lower the minimum discount.";
      }
    }
  }

  function renderCount() {
    var n = state.filtered.length;
    el.count.innerHTML = "<b>" + n.toLocaleString() + "</b> " + (n === 1 ? "deal" : "deals") +
      (state.savedOnly ? " saved" : "");
    var active = activeList().length;
    el.filterCount.textContent = active;
    el.filterCount.hidden = !active;
  }

  function counts(key, skip) {
    var c = {};
    state.all.forEach(function (d) { if (matches(d, skip)) c[d[key]] = (c[d[key]] || 0) + 1; });
    return c;
  }

  function renderCats() {
    var c = counts("category", "cat");
    var total = Object.keys(c).reduce(function (s, k) { return s + c[k]; }, 0);
    var cats = Object.keys(CATEGORY_LABELS).filter(function (k) { return c[k] || state.cat === k; });
    el.cats.innerHTML =
      '<button type="button" class="cat' + (state.cat ? "" : " is-on") + '" data-cat="">All deals <small>' + total + "</small></button>" +
      cats.map(function (k) {
        return '<button type="button" class="cat' + (state.cat === k ? " is-on" : "") + '" data-cat="' + k + '">' +
          esc(CATEGORY_LABELS[k]) + " <small>" + (c[k] || 0) + "</small></button>";
      }).join("");
  }

  function renderStores() {
    var c = counts("store", "store");
    var f = el.storeFilter.value.trim().toLowerCase();
    var names = Object.keys(state.storeTotals || {}).sort(function (a, b) {
      return (c[b] || 0) - (c[a] || 0) || a.localeCompare(b);
    });
    el.storeFilter.hidden = names.length <= 10;
    el.stores.innerHTML = names.filter(function (s) {
        return (c[s] || state.stores.indexOf(s) !== -1) && (!f || s.toLowerCase().indexOf(f) !== -1);
      })
      .map(function (s) {
        var on = state.stores.indexOf(s) !== -1;
        return '<label class="store-opt"><input type="checkbox" value="' + esc(s) + '"' + (on ? " checked" : "") +
          "><span>" + esc(s) + "</span><small>" + (c[s] || 0) + "</small></label>";
      }).join("");
  }

  function activeList() {
    var a = [];
    if (state.q) a.push({ k: "q", label: '"' + state.q + '"' });
    if (state.cat) a.push({ k: "cat", label: CATEGORY_LABELS[state.cat] || state.cat });
    state.stores.forEach(function (s) { a.push({ k: "store", v: s, label: s }); });
    if (state.minPct) a.push({ k: "minPct", label: state.minPct + "%+ off" });
    if (state.pmin !== null) a.push({ k: "pmin", label: "From " + money(state.pmin) });
    if (state.pmax !== null) a.push({ k: "pmax", label: "Up to " + money(state.pmax) });
    if (state.onlyNew) a.push({ k: "onlyNew", label: "New today" });
    if (state.onlyLowest) a.push({ k: "onlyLowest", label: "Lowest price" });
    if (state.savedOnly) a.push({ k: "savedOnly", label: "Saved" });
    return a;
  }

  function renderActive() {
    var a = activeList();
    el.active.innerHTML = a.map(function (f) {
      return '<span class="pill">' + esc(f.label) +
        '<button type="button" data-k="' + f.k + '"' + (f.v ? ' data-v="' + esc(f.v) + '"' : "") +
        ' aria-label="Remove filter ' + esc(f.label) + '">' + icon(I.x) + "</button></span>";
    }).join("") + (a.length > 1 ? '<button type="button" class="link-btn" data-k="all">Clear all</button>' : "");
  }

  function syncControls() {
    el.q.value = state.q;
    el.sort.value = state.sort;
    el.pmin.value = state.pmin === null ? "" : state.pmin;
    el.pmax.value = state.pmax === null ? "" : state.pmax;
    el.onlyNew.checked = state.onlyNew;
    el.onlyLowest.checked = state.onlyLowest;
    [].forEach.call(el.discountChips.children, function (b) {
      b.classList.toggle("is-on", +b.dataset.min === state.minPct);
    });
    [].forEach.call(el.priceChips.children, function (b) {
      var on = b.dataset.max ? (+b.dataset.max === state.pmax && state.pmin === null)
                             : (+b.dataset.min === state.pmin && state.pmax === null);
      b.classList.toggle("is-on", on);
    });
    el.savedBtn.setAttribute("aria-pressed", state.savedOnly);
    setView(state.view);
  }

  function clearFilter(k, v) {
    if (k === "all") {
      state.q = ""; state.cat = ""; state.stores = []; state.minPct = 0;
      state.pmin = null; state.pmax = null; state.onlyNew = false;
      state.onlyLowest = false; state.savedOnly = false;
    } else if (k === "store") {
      state.stores = state.stores.filter(function (s) { return s !== v; });
    } else if (k === "q" || k === "cat") { state[k] = ""; }
    else if (k === "minPct") { state.minPct = 0; }
    else if (k === "pmin" || k === "pmax") { state[k] = null; }
    else { state[k] = false; }
    syncControls();
    apply();
  }

  function setView(v) {
    state.view = v;
    el.deals.classList.toggle("is-grid", v === "grid");
    el.deals.classList.toggle("is-list", v === "list");
    el.viewGrid.classList.toggle("is-on", v === "grid");
    el.viewList.classList.toggle("is-on", v === "list");
    el.viewGrid.setAttribute("aria-pressed", v === "grid");
    el.viewList.setAttribute("aria-pressed", v === "list");
  }

  /* ---------- URL state: every filtered view is a shareable link ---------- */

  function syncUrl(dealId) {
    var p = new URLSearchParams();
    if (state.q) p.set("q", state.q);
    if (state.cat) p.set("cat", state.cat);
    if (state.stores.length) p.set("store", state.stores.join("|"));
    if (state.minPct) p.set("off", state.minPct);
    if (state.pmin !== null) p.set("min", state.pmin);
    if (state.pmax !== null) p.set("max", state.pmax);
    if (state.onlyNew) p.set("new", "1");
    if (state.onlyLowest) p.set("lowest", "1");
    if (state.savedOnly) p.set("saved", "1");
    if (state.sort !== "hot") p.set("sort", state.sort);
    if (dealId) p.set("deal", dealId);
    var qs = p.toString();
    history.replaceState(null, "", location.pathname + (qs ? "?" + qs : ""));
  }

  function readUrl() {
    var p = new URLSearchParams(location.search);
    state.q = (p.get("q") || "").toLowerCase();
    state.cat = p.get("cat") || "";
    state.stores = p.get("store") ? p.get("store").split("|") : [];
    state.minPct = +p.get("off") || 0;
    state.pmin = p.has("min") ? +p.get("min") : null;
    state.pmax = p.has("max") ? +p.get("max") : null;
    state.onlyNew = p.get("new") === "1";
    state.onlyLowest = p.get("lowest") === "1";
    state.savedOnly = p.get("saved") === "1";
    state.sort = SORTS[p.get("sort")] ? p.get("sort") : "hot";
    return p.get("deal");
  }

  /* ---------- Deal detail ---------- */

  function sparkline(points) {
    var prices = points.map(function (p) { return p[1]; });
    var lo = Math.min.apply(null, prices), hi = Math.max.apply(null, prices);
    var span = hi - lo || 1, n = points.length;
    var xy = points.map(function (p, i) {
      return [(i / (n - 1)) * 100, 36 - ((p[1] - lo) / span) * 30];
    });
    var line = xy.map(function (q, i) { return (i ? "L" : "M") + q[0].toFixed(2) + " " + q[1].toFixed(2); }).join(" ");
    var last = xy[xy.length - 1];
    return '<svg class="spark" viewBox="0 0 100 40" preserveAspectRatio="none" role="img" aria-label="Price history">' +
      '<path class="area" d="' + line + " L100 40 L0 40 Z" + '"/>' +
      '<path class="line" d="' + line + '"/>' +
      '<circle class="dot" cx="' + last[0] + '" cy="' + last[1] + '" r="1.6"/></svg>';
  }

  function fmtDate(s) {
    return new Date(s).toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  function openDeal(id, opener) {
    var d = state.byId[id];
    if (!d) return;
    var pct = d.discount_pct;
    var hist = d.history || [];
    var historyBlock;
    if (hist.length > 1) {
      historyBlock = '<div class="m-history"><div class="m-history-head"><span>Price, last ' + hist.length +
        " days</span><span>Lowest tracked <b>" + money(d.low_price) + "</b></span></div>" + sparkline(hist) + "</div>";
    } else {
      historyBlock = '<div class="m-history"><div class="m-history-head"><span>Price history</span></div>' +
        '<p class="m-note">Tracking started ' + (d.first_seen ? fmtDate(d.first_seen) : "today") +
        ". The chart fills in as prices are re-checked every few hours.</p></div>";
    }
    var savedNow = isSaved(d.id);
    el.modalBody.innerHTML =
      '<div class="m-media">' +
        (d.image ? '<img class="dr-img" src="' + esc(safeUrl(d.image.replace(/width=\d+/, "width=900"))) +
          '" alt="' + esc(d.title) + '" referrerpolicy="no-referrer">'
                 : '<span class="thumb-fallback">' + esc(d.store.charAt(0)) + "</span>") +
      "</div>" +
      '<div class="m-info">' +
        '<button class="icon-btn m-close" type="button" data-close aria-label="Close">' + icon(I.x) + "</button>" +
        '<span class="card-store">' + esc(d.store) + "</span>" +
        '<h2 id="mTitle">' + esc(d.title) + "</h2>" +
        '<div class="m-price-row"><span class="price">' + money(d.price) + "</span>" +
          (d.list_price > d.price ? '<span class="was">' + money(d.list_price) + "</span>" : "") +
          (pct ? '<span class="off">&minus;' + pct + "%</span>" : "") +
        "</div>" +
        (d.savings ? '<div class="m-saved">You save ' + money(d.savings) + "</div>" : "") +
        historyBlock +
        '<dl class="m-facts">' +
          "<dt>Category</dt><dd>" + esc(CATEGORY_LABELS[d.category] || "More") + "</dd>" +
          (d.first_seen ? "<dt>First spotted</dt><dd>" + ago(state.now - Date.parse(d.first_seen)) + "</dd>" : "") +
          (d.coupon ? "<dt>Code</dt><dd>" + esc(d.coupon) + "</dd>" : "") +
        "</dl>" +
        '<div class="m-actions">' +
          '<a class="btn btn-primary" href="' + esc(safeUrl(d.url)) + '" target="_blank" rel="nofollow sponsored noopener">Get deal at ' +
            esc(d.store) + " " + icon(I.out) + "</a>" +
          '<button class="btn btn-ghost" type="button" data-save aria-pressed="' + savedNow + '">' + icon(I.heart) +
            (savedNow ? "Saved" : "Save") + "</button>" +
          '<button class="btn btn-ghost" type="button" data-share>' + icon(I.share) + "Share</button>" +
        "</div>" +
        '<p class="m-note">Price checked ' + ago(state.now - Date.parse(state.generatedAt)) +
          ". Confirm the final price at " + esc(d.store) + ". We may earn a commission.</p>" +
      "</div>";
    el.modal.dataset.id = id;
    el.modal._opener = opener || null;
    if (!el.modal.open) el.modal.showModal();
    syncUrl(id);
  }

  function closeDeal() { if (el.modal.open) el.modal.close(); }

  el.modal.addEventListener("close", function () {
    syncUrl();
    if (el.modal._opener) el.modal._opener.focus();
  });
  el.modal.addEventListener("click", function (e) {
    if (e.target === el.modal || e.target.closest("[data-close]")) return closeDeal();
    var id = el.modal.dataset.id;
    var sb = e.target.closest("[data-save]");
    if (sb) {
      var on = toggleSaved(id);
      sb.setAttribute("aria-pressed", on);
      sb.lastChild.textContent = on ? "Saved" : "Save";
      var cardBtn = el.deals.querySelector('[data-id="' + id + '"] .save-btn');
      if (cardBtn) cardBtn.setAttribute("aria-pressed", on);
      return;
    }
    if (e.target.closest("[data-share]")) share(state.byId[id]);
  });

  function share(d) {
    var url = location.origin + location.pathname + "?deal=" + encodeURIComponent(d.id);
    var text = (d.discount_pct ? d.discount_pct + "% off: " : "") + d.title + " — " + money(d.price) + " at " + d.store;
    if (navigator.share) {
      navigator.share({ title: d.title, text: text, url: url }).catch(function () {});
    } else if (navigator.clipboard) {
      navigator.clipboard.writeText(text + " " + url).then(function () { toast("Link copied"); });
    }
  }

  /* ---------- Events ---------- */

  el.deals.addEventListener("click", function (e) {
    var art = e.target.closest(".card");
    if (!art) return;
    var save = e.target.closest(".save-btn");
    if (save) {
      var on = toggleSaved(art.dataset.id);
      save.setAttribute("aria-pressed", on);
      save.setAttribute("aria-label", on ? "Remove from saved" : "Save deal");
      if (state.savedOnly && !on) apply({ keepScroll: true });
      return;
    }
    var open = e.target.closest(".card-open");
    if (open) openDeal(art.dataset.id, open);
  });

  // Retailer photos come two ways: lifestyle shots on their own tinted
  // backdrop (fill the frame, or they look like a box in a box) and product
  // cutouts on white (float them with breathing room). Shape tells them apart.
  document.addEventListener("load", function (e) {
    var img = e.target;
    if (!img.classList || !img.classList.contains("dr-img") || !img.closest(".thumb")) return;
    var r = img.naturalWidth / (img.naturalHeight || 1);
    img.classList.add(r <= 1.08 ? "is-cover" : "is-cutout");
  }, true);

  // Broken retailer images fall back to the store's initial, not a broken icon.
  document.addEventListener("error", function (e) {
    var img = e.target;
    if (!img.classList || !img.classList.contains("dr-img")) return;
    var span = document.createElement("span");
    span.className = "thumb-fallback";
    var card = img.closest("[data-id]") || el.modal;
    var d = state.byId[card.dataset.id];
    span.textContent = d ? d.store.charAt(0) : "?";
    img.replaceWith(span);
  }, true);

  el.q.addEventListener("input", debounce(function () {
    state.q = el.q.value.trim().toLowerCase();
    apply();
  }, 160));

  el.cats.addEventListener("click", function (e) {
    var b = e.target.closest("[data-cat]");
    if (!b) return;
    state.cat = b.dataset.cat;
    apply();
  });

  el.stores.addEventListener("change", function (e) {
    var v = e.target.value;
    if (e.target.checked) state.stores.push(v);
    else state.stores = state.stores.filter(function (s) { return s !== v; });
    apply({ keepScroll: innerWidth <= 960 });
  });
  el.storeFilter.addEventListener("input", renderStores);

  el.discountChips.addEventListener("click", function (e) {
    var b = e.target.closest("[data-min]");
    if (!b) return;
    state.minPct = +b.dataset.min;
    syncControls(); apply({ keepScroll: innerWidth <= 960 });
  });

  el.priceChips.addEventListener("click", function (e) {
    var b = e.target.closest(".chip");
    if (!b) return;
    var already = b.classList.contains("is-on");
    state.pmin = null; state.pmax = null;
    if (!already) {
      if (b.dataset.max) state.pmax = +b.dataset.max;
      if (b.dataset.min) state.pmin = +b.dataset.min;
    }
    syncControls(); apply({ keepScroll: innerWidth <= 960 });
  });

  var onPrice = debounce(function () {
    state.pmin = el.pmin.value === "" ? null : Math.max(0, +el.pmin.value);
    state.pmax = el.pmax.value === "" ? null : Math.max(0, +el.pmax.value);
    syncControls(); apply({ keepScroll: true });
  }, 400);
  el.pmin.addEventListener("input", onPrice);
  el.pmax.addEventListener("input", onPrice);

  el.onlyNew.addEventListener("change", function () { state.onlyNew = el.onlyNew.checked; apply({ keepScroll: innerWidth <= 960 }); });
  el.onlyLowest.addEventListener("change", function () { state.onlyLowest = el.onlyLowest.checked; apply({ keepScroll: innerWidth <= 960 }); });

  el.sort.addEventListener("change", function () { state.sort = el.sort.value; apply(); });

  el.viewGrid.addEventListener("click", function () { setView("grid"); localStorage.setItem("dr-view", "grid"); });
  el.viewList.addEventListener("click", function () { setView("list"); localStorage.setItem("dr-view", "list"); });

  el.active.addEventListener("click", function (e) {
    var b = e.target.closest("[data-k]");
    if (b) clearFilter(b.dataset.k, b.dataset.v);
  });
  $("clearAll").addEventListener("click", function () { clearFilter("all"); });
  $("emptyReset").addEventListener("click", function () { clearFilter("all"); });

  el.savedBtn.addEventListener("click", function () {
    state.savedOnly = !state.savedOnly;
    syncControls(); apply();
  });

  $("themeBtn").addEventListener("click", function () {
    var t = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = t;
    localStorage.setItem("dr-theme", t);
  });

  function drawer(open) {
    el.sidebar.classList.toggle("is-open", open);
    document.body.classList.toggle("drawer-open", open);
  }
  $("openFilters").addEventListener("click", function () { drawer(true); });
  $("closeFilters").addEventListener("click", function () { drawer(false); });
  $("applyFilters").addEventListener("click", function () { drawer(false); });
  document.addEventListener("click", function (e) {
    if (document.body.classList.contains("drawer-open") && !el.sidebar.contains(e.target) &&
        !e.target.closest("#openFilters")) drawer(false);
  });

  document.addEventListener("keydown", function (e) {
    var typing = /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName);
    if (e.key === "/" && !typing && !el.modal.open) { e.preventDefault(); el.q.focus(); }
    if (e.key === "Escape" && document.body.classList.contains("drawer-open")) drawer(false);
  });

  el.toTop.addEventListener("click", function () { scrollTo({ top: 0, behavior: "smooth" }); });
  addEventListener("scroll", debounce(function () { el.toTop.hidden = scrollY < 1200; }, 100), { passive: true });

  new IntersectionObserver(function (entries) {
    if (entries[0].isIntersecting && state.shown < state.filtered.length) renderMore();
  }, { rootMargin: "900px" }).observe(el.sentinel);

  /* ---------- Event countdown ---------- */

  function startCountdown(h) {
    if (!h || !h.next) return;
    var peak = new Date(h.next.peak + "T00:00:00");
    var running = h.live && h.live.slug === h.next.slug;
    el.eventName.textContent = h.next.name;
    el.eventNote.textContent = running ? "Early deals are already live" :
      peak.toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric" });
    el.event.hidden = false;
    (function tick() {
      var ms = peak - new Date();
      if (ms <= 0) { el.eventClock.textContent = "Live now"; return; }
      var s = Math.floor(ms / 1000), d = Math.floor(s / 86400),
          hr = Math.floor((s % 86400) / 3600), m = Math.floor((s % 3600) / 60);
      el.eventClock.textContent = d >= 1 ? d + "d " + hr + "h" : hr + "h " + m + "m";
      setTimeout(tick, 30000);
    })();
  }

  /* ---------- Boot ---------- */

  // Sticky bars stack under the top bar, whose height changes when the
  // search box wraps on phones. Measure instead of guessing.
  var topbar = document.querySelector(".topbar");
  function measureTop() {
    document.documentElement.style.setProperty("--top-h", topbar.offsetHeight + "px");
  }
  measureTop();
  addEventListener("resize", debounce(measureTop, 100));

  el.deals.innerHTML = Array(12).join('<li class="skel"><div class="s-img"></div><div class="s-l1"></div><div class="s-l2"></div><div class="s-l3"></div></li>');
  setView(state.view);

  fetch(DATA_URL, { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(function (data) {
      state.generatedAt = data.generated_at || new Date().toISOString();
      state.now = Date.parse(state.generatedAt) || Date.now();
      state.all = (data.deals || []).map(prepare);
      state.all.forEach(function (d) { state.byId[d.id] = d; });
      // Right after tracking starts everything is "new", which means nothing.
      var freshShare = state.all.filter(function (d) { return d._new; }).length / (state.all.length || 1);
      if (freshShare > 0.5) {
        state.all.forEach(function (d) {
          d._new = false;
          d._hot -= 10;
        });
        el.onlyNew.closest(".toggle").hidden = true;
      }
      // "Hot" means the top 3%, not everything over some fixed bar.
      var scores = state.all.map(function (d) { return d._hot; }).sort(function (a, b) { return b - a; });
      state.hotCut = scores.length ? scores[Math.floor(scores.length * 0.03)] : Infinity;
      state.storeTotals = data.store_counts || {};
      if (!data.store_counts) state.all.forEach(function (d) { state.storeTotals[d.store] = (state.storeTotals[d.store] || 0) + 1; });

      if (data.is_sample_data) el.notice.hidden = false;

      var stores = Object.keys(state.storeTotals).length;
      var best = state.all.reduce(function (m, d) { return Math.max(m, d.discount_pct || 0); }, 0);
      el.heroStats.innerHTML = "<b>" + state.all.length.toLocaleString() + "</b> live deals from <b>" + stores +
        "</b> stores, up to <b>" + best + "% off</b>. Updated " + ago(Date.now() - state.now) + ".";

      var live = Object.keys(data.counts || {}).filter(function (k) { return k !== "seed" && data.counts[k] > 0; });
      el.attribution.textContent = live.length ? "Sources: " + live.join(", ") + "." : "";

      startCountdown(data.holiday);
      updateSavedCount();
      var dealId = readUrl();
      syncControls();
      apply({ keepScroll: true });
      if (dealId && state.byId[dealId]) openDeal(dealId);
    })
    .catch(function (err) {
      el.deals.innerHTML = "";
      el.empty.hidden = false;
      el.emptyTitle.textContent = "Deals could not load.";
      el.emptyBody.textContent = "The deal feed did not respond (" + err.message + "). It rebuilds every few hours, so try again shortly.";
    });
})();
