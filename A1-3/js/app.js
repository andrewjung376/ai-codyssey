/* AI여행추천 (AI TripPick) - 프론트엔드 로직
 * 네비게이션, 다크 모드, 폼 검증, POST /api(action: recommend|report) 호출,
 * 결과 렌더링, localStorage 캐시/최근 기록, 리포트 다운로드를 담당한다.
 */

(function () {
  "use strict";

  // ---------------------------------------------------------------------
  // 상수
  // ---------------------------------------------------------------------
  var MAX_PREFERENCE_LEN = 200;
  var SLOW_WARNING_MS = 8000; // 8초 경과 시 "조금 더 걸리고 있어요" 안내
  // 서버는 1순위 Cody 프록시(최대 28초) 실패 시 2순위 OpenAI 폴백(최대 20초)까지
  // 시도하므로, 정상적인 폴백 흐름도 끊기지 않도록 Vercel 함수 제한(60초)에 맞춰 넉넉히 잡는다.
  var REQUEST_TIMEOUT_MS = 55000; // 55초 경과 시 요청 중단
  var THEME_KEY = "trippick:theme";
  var RECOMMEND_CACHE_PREFIX = "trippick:recommend:";
  var RECENT_KEY = "trippick:recent";
  var MAX_RECENT = 5;

  // ---------------------------------------------------------------------
  // DOM 참조
  // ---------------------------------------------------------------------
  var navToggle = document.getElementById("navToggle");
  var navMenu = document.getElementById("navMenu");
  var themeToggle = document.getElementById("themeToggle");
  var themeIcon = document.getElementById("themeIcon");

  var form = document.getElementById("plannerForm");
  var dateInput = document.getElementById("dateInput");
  var dateError = document.getElementById("dateError");
  var preferenceInput = document.getElementById("preferenceInput");
  var preferenceError = document.getElementById("preferenceError");
  var prefCount = document.getElementById("prefCount");
  var submitBtn = document.getElementById("submitBtn");
  var freshBtn = document.getElementById("freshBtn");

  var recentWrap = document.getElementById("recentWrap");
  var recentList = document.getElementById("recentList");

  var statusArea = document.getElementById("statusArea");
  var skeletonArea = document.getElementById("skeletonArea");
  var resultArea = document.getElementById("resultArea");
  var resultDateLabel = document.getElementById("resultDateLabel");
  var aiKeySourceLabel = document.getElementById("aiKeySourceLabel");
  var cityCards = document.getElementById("cityCards");
  var errorSummary = document.getElementById("errorSummary");
  var downloadBtn = document.getElementById("downloadBtn");

  var lastMarkdown = "";
  var lastDate = "";
  var isSubmitting = false;

  // ---------------------------------------------------------------------
  // 네비게이션 (모바일 햄버거 메뉴)
  // ---------------------------------------------------------------------
  navToggle.addEventListener("click", function () {
    var isOpen = navMenu.classList.toggle("open");
    navToggle.setAttribute("aria-expanded", String(isOpen));
  });

  navMenu.querySelectorAll(".nav-link").forEach(function (link) {
    link.addEventListener("click", function () {
      navMenu.classList.remove("open");
      navToggle.setAttribute("aria-expanded", "false");
    });
  });

  // ---------------------------------------------------------------------
  // 다크 모드 (보너스: UX 고도화)
  // ---------------------------------------------------------------------
  function applyTheme(theme) {
    if (theme === "dark" || theme === "light") {
      document.documentElement.setAttribute("data-theme", theme);
    } else {
      document.documentElement.removeAttribute("data-theme");
    }
    var prefersDark =
      theme === "dark" ||
      (theme !== "light" && window.matchMedia("(prefers-color-scheme: dark)").matches);
    themeIcon.textContent = prefersDark ? "☀️" : "🌙";
  }

  function initTheme() {
    var saved = null;
    try {
      saved = localStorage.getItem(THEME_KEY);
    } catch (e) {
      // 프라이빗 모드 등에서 localStorage 접근이 막힐 수 있음. 기본값으로 진행.
    }
    applyTheme(saved);
  }

  themeToggle.addEventListener("click", function () {
    var current = document.documentElement.getAttribute("data-theme");
    var prefersDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    var currentlyDark = current === "dark" || (!current && prefersDark);
    var next = currentlyDark ? "light" : "dark";
    applyTheme(next);
    try {
      localStorage.setItem(THEME_KEY, next);
    } catch (e) {
      /* 저장 실패는 무시하고 화면 전환만 반영한다 */
    }
  });

  initTheme();

  // ---------------------------------------------------------------------
  // 여행 취향 글자수 카운터
  // ---------------------------------------------------------------------
  preferenceInput.addEventListener("input", function () {
    var len = preferenceInput.value.length;
    prefCount.textContent = String(len);
    prefCount.parentElement.style.color = len > MAX_PREFERENCE_LEN ? "var(--color-danger)" : "";
  });

  // ---------------------------------------------------------------------
  // localStorage 유틸 (캐시/최근 기록) - 접근 실패는 조용히 무시한다
  // ---------------------------------------------------------------------
  function safeGetItem(key) {
    try {
      return localStorage.getItem(key);
    } catch (e) {
      return null;
    }
  }

  function safeSetItem(key, value) {
    try {
      localStorage.setItem(key, value);
    } catch (e) {
      /* 용량 초과, 프라이빗 모드 등은 캐시 없이 계속 진행 */
    }
  }

  function cacheKey(date, preference) {
    return RECOMMEND_CACHE_PREFIX + date + "|" + (preference || "");
  }

  function loadRecommendCache(date, preference) {
    var raw = safeGetItem(cacheKey(date, preference));
    if (!raw) return null;
    try {
      return JSON.parse(raw);
    } catch (e) {
      return null;
    }
  }

  function saveRecommendCache(date, preference, data) {
    safeSetItem(cacheKey(date, preference), JSON.stringify(data));
  }

  function loadRecent() {
    var raw = safeGetItem(RECENT_KEY);
    if (!raw) return [];
    try {
      var list = JSON.parse(raw);
      return Array.isArray(list) ? list : [];
    } catch (e) {
      return [];
    }
  }

  function saveRecent(date, preference, cities) {
    var list = loadRecent().filter(function (item) {
      return !(item.date === date && item.preference === (preference || ""));
    });
    list.unshift({
      date: date,
      preference: preference || "",
      cities: cities,
      savedAt: new Date().toISOString(),
    });
    list = list.slice(0, MAX_RECENT);
    safeSetItem(RECENT_KEY, JSON.stringify(list));
    renderRecent();
  }

  function renderRecent() {
    var list = loadRecent();
    recentList.innerHTML = "";
    if (list.length === 0) {
      recentWrap.hidden = true;
      return;
    }
    recentWrap.hidden = false;
    list.forEach(function (item) {
      var chip = document.createElement("button");
      chip.type = "button";
      chip.className = "recent-chip";
      chip.textContent = item.date + " · " + item.cities.join(", ");
      chip.addEventListener("click", function () {
        dateInput.value = item.date;
        preferenceInput.value = item.preference || "";
        prefCount.textContent = String((item.preference || "").length);
        form.requestSubmit();
      });
      recentList.appendChild(chip);
    });
  }

  renderRecent();

  // ---------------------------------------------------------------------
  // 상태 메시지 렌더링
  // ---------------------------------------------------------------------
  function clearStatus() {
    statusArea.innerHTML = "";
  }

  function showStatus(message, type, options) {
    clearStatus();
    var box = document.createElement("div");
    box.className = "status-message " + (type || "info");
    var text = document.createElement("p");
    text.textContent = message;
    text.style.margin = "0";
    box.appendChild(text);

    if (options && options.retry) {
      var retryBtn = document.createElement("button");
      retryBtn.type = "button";
      retryBtn.className = "btn btn-primary btn-sm";
      retryBtn.textContent = "다시 시도";
      retryBtn.addEventListener("click", options.retry);
      box.appendChild(retryBtn);
    }

    statusArea.appendChild(box);
  }

  // ---------------------------------------------------------------------
  // 입력 검증
  // ---------------------------------------------------------------------
  function validateForm() {
    var valid = true;
    dateError.textContent = "";
    preferenceError.textContent = "";

    if (!dateInput.value) {
      dateError.textContent = "여행 날짜를 선택해 주세요.";
      valid = false;
    } else {
      var today = new Date();
      today.setHours(0, 0, 0, 0);
      var picked = new Date(dateInput.value + "T00:00:00");
      if (picked < today) {
        dateError.textContent = "여행 날짜는 오늘 이후로 선택해 주세요.";
        valid = false;
      }
    }

    if (preferenceInput.value.length > MAX_PREFERENCE_LEN) {
      preferenceError.textContent = "여행 취향은 " + MAX_PREFERENCE_LEN + "자 이내로 입력해 주세요.";
      valid = false;
    }

    return valid;
  }

  // ---------------------------------------------------------------------
  // fetch 유틸: 타임아웃(30초) + 지연 안내(8초)
  // ---------------------------------------------------------------------
  function postJson(url, payload, onSlow) {
    var controller = new AbortController();
    var timeoutId = setTimeout(function () {
      controller.abort();
    }, REQUEST_TIMEOUT_MS);
    var slowId = setTimeout(function () {
      if (onSlow) onSlow();
    }, SLOW_WARNING_MS);

    return fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    })
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return {};
          })
          .then(function (data) {
            return { ok: response.ok, status: response.status, data: data };
          });
      })
      .finally(function () {
        clearTimeout(timeoutId);
        clearTimeout(slowId);
      });
  }

  // ---------------------------------------------------------------------
  // 결과 렌더링
  // ---------------------------------------------------------------------
  var AI_KEY_SOURCE_LABELS = {
    cody: "Codyssey 프록시 (gpt-5-mini)",
    openai: "OpenAI 직접 호출 (gpt-4o-mini, 폴백)",
  };

  function renderAiKeySource(recommendKeySource, reportKeySource) {
    var recLabel = AI_KEY_SOURCE_LABELS[recommendKeySource];
    var repLabel = AI_KEY_SOURCE_LABELS[reportKeySource];

    if (!recLabel && !repLabel) {
      aiKeySourceLabel.hidden = true;
      return;
    }

    var text = "🔑 AI 응답 출처 — 추천: " + (recLabel || "알 수 없음");
    if (repLabel) {
      text += " · 리포트: " + repLabel;
    }
    aiKeySourceLabel.textContent = text;
    aiKeySourceLabel.hidden = false;
  }

  function renderResults(date, cities, reportCities, markdown, errors, recommendKeySource, reportKeySource) {
    resultDateLabel.textContent = date + " 추천 결과";
    renderAiKeySource(recommendKeySource, reportKeySource);
    cityCards.innerHTML = "";

    var reportByCity = {};
    (reportCities || []).forEach(function (r) {
      reportByCity[r.city] = r;
    });

    cities.forEach(function (city, index) {
      var report = reportByCity[city.city] || {};
      var card = document.createElement("article");
      card.className = "city-card";
      card.style.animationDelay = index * 0.08 + "s";

      var title = document.createElement("h4");
      title.textContent = city.city;
      card.appendChild(title);

      var weather = document.createElement("p");
      weather.className = "city-weather";
      weather.textContent = city.weather || "";
      card.appendChild(weather);

      card.appendChild(
        buildSection(
          "추천 이유",
          report.summary || city.reason || ""
        )
      );

      if (city.events && city.events.length > 0) {
        var eventsSection = document.createElement("div");
        eventsSection.className = "card-section";
        var eventsTitle = document.createElement("p");
        eventsTitle.className = "card-section-title";
        eventsTitle.textContent = "행사/축제";
        eventsSection.appendChild(eventsTitle);
        var ul = document.createElement("ul");
        ul.className = "tag-list";
        city.events.forEach(function (ev) {
          var li = document.createElement("li");
          li.textContent = ev;
          ul.appendChild(li);
        });
        eventsSection.appendChild(ul);
        card.appendChild(eventsSection);
      }

      card.appendChild(buildRestaurantSection(city.restaurants || []));

      if (report.schedule) {
        card.appendChild(buildScheduleSection(report.schedule));
      }

      cityCards.appendChild(card);
    });

    if (errors && errors.length > 0) {
      errorSummary.hidden = false;
      errorSummary.textContent =
        "일부 데이터를 불러오지 못했어요 (" +
        errors.length +
        "건). 해당 지역은 \"데이터 없음\"으로 표시됩니다.";
    } else {
      errorSummary.hidden = true;
      errorSummary.textContent = "";
    }

    lastMarkdown = markdown || "";
    lastDate = date;
    resultArea.hidden = false;
    freshBtn.hidden = false;
  }

  function buildSection(title, text) {
    var section = document.createElement("div");
    section.className = "card-section";
    var t = document.createElement("p");
    t.className = "card-section-title";
    t.textContent = title;
    section.appendChild(t);
    var body = document.createElement("p");
    body.style.margin = "0";
    body.style.fontSize = "0.9rem";
    body.textContent = text;
    section.appendChild(body);
    return section;
  }

  function buildRestaurantSection(restaurants) {
    var section = document.createElement("div");
    section.className = "card-section";
    var title = document.createElement("p");
    title.className = "card-section-title";
    title.textContent = "맛집 추천";
    section.appendChild(title);

    if (!restaurants || restaurants.length === 0) {
      var empty = document.createElement("p");
      empty.className = "no-data";
      empty.textContent = "데이터 없음";
      section.appendChild(empty);
      return section;
    }

    var ul = document.createElement("ul");
    ul.className = "restaurant-list";
    restaurants.forEach(function (r) {
      var li = document.createElement("li");
      var a = document.createElement("a");
      a.href = r.url || "#";
      a.target = "_blank";
      a.rel = "noopener noreferrer";
      a.textContent = r.name || "이름 없음";
      li.appendChild(a);
      var addr = document.createElement("span");
      addr.textContent = r.address || "";
      li.appendChild(addr);
      ul.appendChild(li);
    });
    section.appendChild(ul);
    return section;
  }

  function buildScheduleSection(schedule) {
    var section = document.createElement("div");
    section.className = "card-section";
    var title = document.createElement("p");
    title.className = "card-section-title";
    title.textContent = "1일 일정";
    section.appendChild(title);

    var grid = document.createElement("div");
    grid.className = "schedule-grid";
    [
      ["오전", schedule.morning],
      ["오후", schedule.afternoon],
      ["저녁", schedule.evening],
    ].forEach(function (pair) {
      var item = document.createElement("div");
      item.className = "schedule-item";
      var b = document.createElement("b");
      b.textContent = pair[0];
      item.appendChild(b);
      item.appendChild(document.createTextNode(pair[1] || ""));
      grid.appendChild(item);
    });
    section.appendChild(grid);
    return section;
  }

  // ---------------------------------------------------------------------
  // 리포트 다운로드
  // ---------------------------------------------------------------------
  downloadBtn.addEventListener("click", function () {
    if (!lastMarkdown) return;
    var blob = new Blob([lastMarkdown], { type: "text/markdown;charset=utf-8" });
    var url = URL.createObjectURL(blob);
    var a = document.createElement("a");
    a.href = url;
    a.download = lastDate + "_travel_plan.md";
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  });

  // ---------------------------------------------------------------------
  // 폼 제출 (핵심 흐름): recommend(캐시 우선) -> report
  // ---------------------------------------------------------------------
  function runPlanner(forceRefresh) {
    if (isSubmitting) return; // 중복 요청 방지
    if (!validateForm()) return;

    var date = dateInput.value;
    var preference = preferenceInput.value.trim();

    isSubmitting = true;
    submitBtn.disabled = true;
    submitBtn.textContent = "추천 생성 중...";
    clearStatus();
    resultArea.hidden = true;
    skeletonArea.hidden = false;

    var cached = forceRefresh ? null : loadRecommendCache(date, preference);
    var recommendPromise;

    if (cached) {
      showStatus("이전에 저장된 추천 결과를 재사용합니다. (같은 날짜·취향 재검색)", "info");
      recommendPromise = Promise.resolve({ ok: true, status: 200, data: cached });
    } else {
      recommendPromise = postJson(
        "/api",
        { action: "recommend", date: date, preference: preference || undefined },
        function () {
          showStatus("조금 더 걸리고 있어요… AI가 여행지를 고르고 있습니다.", "info");
        }
      );
    }

    recommendPromise
      .then(function (result) {
        if (!result.ok) {
          throw { stage: "recommend", result: result };
        }
        if (!cached) {
          saveRecommendCache(date, preference, result.data);
        }
        var cities = result.data.recommended_cities;
        var recommendErrors = result.data.errors || [];

        return postJson(
          "/api",
          { action: "report", date: date, recommended_cities: cities, errors: recommendErrors },
          function () {
            showStatus("리포트를 정리하고 있어요…", "info");
          }
        ).then(function (reportResult) {
          if (!reportResult.ok) {
            throw { stage: "report", result: reportResult };
          }
          clearStatus();
          renderResults(
            date,
            cities,
            reportResult.data.cities,
            reportResult.data.markdown,
            recommendErrors,
            result.data.ai_key_source,
            reportResult.data.ai_key_source
          );
          saveRecent(
            date,
            preference,
            cities.map(function (c) {
              return c.city;
            })
          );
        });
      })
      .catch(function (err) {
        handleFailure(err, forceRefresh);
      })
      .finally(function () {
        isSubmitting = false;
        submitBtn.disabled = false;
        submitBtn.textContent = "여행지 추천받기";
        skeletonArea.hidden = true;
      });
  }

  function handleFailure(err, forceRefresh) {
    if (err && err.name === "AbortError") {
      showStatus("응답이 너무 늦어요. 다시 시도해 주세요.", "error", {
        retry: function () {
          runPlanner(forceRefresh);
        },
      });
      return;
    }

    if (err && err.result) {
      var status = err.result.status;
      var message =
        (err.result.data && err.result.data.error) ||
        "AI 응답을 받지 못했어요. 잠시 후 다시 시도해 주세요.";

      if (status === 400) {
        showStatus(message, "error");
      } else if (status === 500) {
        showStatus("서비스 설정 오류입니다. 잠시 후 다시 시도해 주세요.", "error");
      } else {
        showStatus(message, "error", {
          retry: function () {
            runPlanner(forceRefresh);
          },
        });
      }
      return;
    }

    // fetch 자체 실패(네트워크 오류) 등 예상치 못한 오류
    showStatus("네트워크 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.", "error", {
      retry: function () {
        runPlanner(forceRefresh);
      },
    });
  }

  form.addEventListener("submit", function (e) {
    e.preventDefault();
    runPlanner(false);
  });

  freshBtn.addEventListener("click", function () {
    runPlanner(true);
  });

  // ---------------------------------------------------------------------
  // 날짜 입력 기본값: 오늘 이후 날짜만 선택 가능하도록 min 지정
  // ---------------------------------------------------------------------
  (function initDateInput() {
    var today = new Date();
    var yyyy = today.getFullYear();
    var mm = String(today.getMonth() + 1).padStart(2, "0");
    var dd = String(today.getDate()).padStart(2, "0");
    dateInput.min = yyyy + "-" + mm + "-" + dd;
  })();
})();
