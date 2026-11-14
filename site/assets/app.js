/* DealRadar front end.
   Loads one static JSON file and filters it in memory. No framework, no build
   step — the whole point of a GitHub Pages site is that it is just files. */

(function () {
  "use strict";

  var DATA_URL = "data/deals.json";
  var state = { deals: [], filtered: [] };

  var el = {
    deals: document.getElementById("deals"),
    empty: document.getElementById("empty"),
    count: document.getElementById("count"),
    updated: document.getElementById("updated"),
    q: document.getElementById("q"),
    store: document.getElementById("store"),
    cat: document.getElementById("cat"),
    min: document.getElementById("min"),
    countdown: document.getElementById("countdown"),
    clock: document.getElementById("clock"),
    event: document.getElementById("event"),
    eventDate: document.getElementById("eventDate"),
    notice: document.getElementById("sampleNotice"),
    attribution: document.getElementById("attribution")
  };

  var CATEGORY_LABELS = {
    "computers": "Computers", "tv-audio": "TV & Audio",
    "phones-tablets": "Phones & Tablets", "gaming": "Gaming",
    "home": "Home", "apparel": "Apparel", "toys": "Toys",
    "tools": "Tools", "other": "Other"
  };

  function money(n) {
    if (n === null || n === undefined) return "";
    return "$" + n.toLocaleString("en-US", {
      minimumFractionDigits: n % 1 ? 2 : 0, maximumFractionDigits: 2
    });
  }

  function esc(s) {
    var d = document.createElement("div");
    d.textContent = s == null ? "" : s;
    return d.innerHTML;
  }

  /* ---------- Countdown ---------- */

  function startCountdown(holiday) {
    if (!holiday || !holiday.next) return;
    var peak = new Date(holiday.next.peak + "T00:00:00");
    var live = holiday.live;

    el.event.textContent = holiday.next.name;
    el.eventDate.textContent = peak.toLocaleDateString("en-US", {
      weekday: "long", month: "long", day: "numeric"
    }) + (live && live.slug === holiday.next.slug
          ? " — deals are already running" : "");
    el.countdown.hidden = false;

    function tick() {
      var ms = peak - new Date();
      if (ms <= 0) {
        el.countdown.classList.add("is-live");
        el.clock.textContent = "Today";
        return;
      }
      var s = Math.floor(ms / 1000);
      var d = Math.floor(s / 86400);
      var h = Math.floor((s % 86400) / 3600);
      var m = Math.floor((s % 3600) / 60);

      if (d >= 1) {
        el.clock.innerHTML = d + '<span class="clock-unit">' +
          (d === 1 ? "day" : "days") + "</span> " +
          h + '<span class="clock-unit">hr</span>';
      } else {
        el.clock.innerHTML = h + '<span class="clock-unit">hr</span> ' +
          m + '<span class="clock-unit">min</span>';
      }
      setTimeout(tick, 60000);
    }
    tick();
  }

  /* ---------- Rendering ---------- */

  function row(d) {
    var pct = d.discount_pct;
    var deep = pct !== null && pct >= 40 ? " is-deep" : "";
    var meta = ['<span class="store">' + esc(d.store) + "</span>"];
    if (d.category && CATEGORY_LABELS[d.category]) {
      meta.push(esc(CATEGORY_LABELS[d.category]));
    }
    if (d.coupon) meta.push("Code " + esc(d.coupon));

    var prices = "";
    if (d.price !== null && d.price !== undefined) {
      prices += '<span class="price">' + money(d.price) + "</span>";
      if (d.list_price && d.list_price > d.price) {
        prices += '<span class="was">' + money(d.list_price) + "</span> ";
        prices += '<span class="saved">save ' + money(d.savings) + "</span>";
      }
    } else {
      prices = '<span class="was">see listing</span>';
    }

    return '<li><a class="row" href="' + esc(d.url) +
      '" target="_blank" rel="nofollow sponsored noopener"' +
      (pct === null ? ' data-nodiscount="1"' : "") + ">" +
      '<div class="row-main">' +
        '<p class="row-title">' + esc(d.title) + "</p>" +
        '<div class="row-meta">' + meta.join("<span>·</span>") + "</div>" +
      "</div>" +
      '<div class="delta' + deep + '">' +
        (pct !== null ? "&minus;" + pct + "%" : "deal") + "</div>" +
      '<div class="row-prices">' + prices + "</div>" +
      "</a></li>";
  }

  function render() {
    var list = state.filtered;
    el.count.textContent = list.length + " of " + state.deals.length;
    el.empty.hidden = list.length > 0;
    el.deals.innerHTML = list.slice(0, 300).map(row).join("");
  }

  /* ---------- Filtering ---------- */

  function applyFilters() {
    var q = el.q.value.trim().toLowerCase();
    var store = el.store.value;
    var cat = el.cat.value;
    var min = parseInt(el.min.value, 10) || 0;

    state.filtered = state.deals.filter(function (d) {
      if (store && d.store !== store) return false;
      if (cat && d.category !== cat) return false;
      if (min && (d.discount_pct === null || d.discount_pct < min)) return false;
      if (q && (d.title + " " + d.store).toLowerCase().indexOf(q) === -1) return false;
      return true;
    });
    render();
  }

  function fillSelect(sel, values, labels) {
    values.forEach(function (v) {
      var o = document.createElement("option");
      o.value = v;
      o.textContent = labels ? (labels[v] || v) : v;
      sel.appendChild(o);
    });
  }

  function debounce(fn, ms) {
    var t;
    return function () { clearTimeout(t); t = setTimeout(fn, ms); };
  }

  /* ---------- Boot ---------- */

  fetch(DATA_URL, { cache: "no-cache" })
    .then(function (r) {
      if (!r.ok) throw new Error("HTTP " + r.status);
      return r.json();
    })
    .then(function (data) {
      state.deals = data.deals || [];
      state.filtered = state.deals;

      if (data.is_sample_data) el.notice.hidden = false;

      if (data.generated_at) {
        var t = new Date(data.generated_at);
        el.updated.textContent = "Updated " + t.toLocaleString("en-US", {
          month: "short", day: "numeric", hour: "numeric", minute: "2-digit"
        });
      }

      fillSelect(el.store, data.stores || []);
      fillSelect(el.cat, data.categories || [], CATEGORY_LABELS);
      startCountdown(data.holiday);

      var live = Object.keys(data.counts || {}).filter(function (k) {
        return k !== "seed" && data.counts[k] > 0;
      });
      el.attribution.textContent = live.length
        ? "Sources: " + live.join(", ") + ". Some links earn a commission."
        : "Some links earn a commission.";

      render();
    })
    .catch(function (err) {
      el.empty.hidden = false;
      el.empty.innerHTML = "<strong>Deals could not load.</strong>" +
        "The feed at " + DATA_URL + " did not respond (" + esc(err.message) +
        "). It is rebuilt on a schedule — try again shortly.";
    });

  el.q.addEventListener("input", debounce(applyFilters, 150));
  [el.store, el.cat, el.min].forEach(function (s) {
    s.addEventListener("change", applyFilters);
  });
})();
