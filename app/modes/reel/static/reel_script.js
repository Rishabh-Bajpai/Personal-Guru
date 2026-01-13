let currentReels = [];
let currentIndex = 0;
let players = {}; // Store YT.Player instances
let isScrolling = false;
let apiReady = false;
let currentSessionId = null; // Track current search session

// Load YouTube Iframe API
const tag = document.createElement("script");
tag.src = "https://www.youtube.com/iframe_api";
const firstScriptTag = document.getElementsByTagName("script")[0];
firstScriptTag.parentNode.insertBefore(tag, firstScriptTag);

function onYouTubeIframeAPIReady() {
  apiReady = true;
  console.log("YouTube API Ready");

  // Auto-search if topic value is present
  const topicInput = document.getElementById("topicInput");
  if (topicInput && topicInput.value.trim()) {
    performSearch(topicInput.value.trim());
  }
}

// Send video event to backend
function logVideoEvent(videoId, eventType) {
  if (!currentSessionId || !videoId) return;

  // Updated path to match /reels/api/video-event
  fetch("/reels/api/video-event", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": document
        .querySelector('meta[name="csrf-token"]')
        .getAttribute("content"),
    },
    body: JSON.stringify({
      session_id: currentSessionId,
      video_id: videoId,
      event_type: eventType,
    }),
  }).catch((err) => console.error("Failed to log event:", err));
}

async function performSearch(topic) {
  const errorMessage = document.getElementById("errorMessage");
  const loadingSpinner = document.getElementById("loadingSpinner");
  const reelsContainer = document.getElementById("reelsContainer");
  const noResults = document.getElementById("noResults");

  // Clear previous state
  errorMessage.textContent = "";
  errorMessage.classList.remove("show");
  reelsContainer.innerHTML = "";
  noResults.style.display = "none";
  currentIndex = 0;
  players = {};

  if (!topic) {
    errorMessage.textContent = "Please enter a topic to search.";
    errorMessage.classList.add("show");
    return;
  }

  // Show loading
  loadingSpinner.style.display = "flex";

  try {
    const response = await fetch("/reels/api/search", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": document
          .querySelector('meta[name="csrf-token"]')
          .getAttribute("content"),
      },
      body: JSON.stringify({ topic }),
    });

    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.error || "Failed to search");
    }

    if (data.reels.length === 0) {
      noResults.style.display = "flex";
    } else {
      currentReels = data.reels;
      currentSessionId = data.session_id; // Store session ID
      displayReels();
    }
  } catch (error) {
    errorMessage.textContent = error.message;
    errorMessage.classList.add("show");
  } finally {
    loadingSpinner.style.display = "none";
  }
}

document.getElementById("searchForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const topic = document.getElementById("topicInput").value.trim();
  performSearch(topic);
});

function displayReels() {
  const reelsContainer = document.getElementById("reelsContainer");
  reelsContainer.innerHTML = "";

  currentReels.forEach((reel, index) => {
    const reelItem = createReelElement(reel, index);
    reelsContainer.appendChild(reelItem);
    // Initialize player for this reel if API is ready
    // If API not ready, it does nothing? No, we need to handle that.
    // But displayReels is usually called after search, which is triggered after API ready or user action.
    if (apiReady) {
      initializePlayer(index, reel.id);
    }
  });

  // Initialize Intersection Observer
  setupIntersectionObserver();
}

let observer;

function setupIntersectionObserver() {
  if (observer) {
    observer.disconnect();
  }

  const options = {
    root: document.getElementById("reelsContainer"),
    rootMargin: "0px",
    threshold: 0.7, // Video must be 70% visible to play
  };

  observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const index = parseInt(entry.target.dataset.index);
        if (!isNaN(index) && index !== currentIndex) {
          currentIndex = index;
          playReelVideo(index);
        } else if (!isNaN(index) && index === currentIndex) {
          playReelVideo(index);
        }
      }
    });
  }, options);

  const reels = document.querySelectorAll(".reel-item");
  reels.forEach((reel) => observer.observe(reel));
}

function createReelElement(reel, index) {
  const reelItem = document.createElement("div");
  reelItem.className = "reel-item";
  reelItem.dataset.index = index;

  const playerDivId = `player-${index}`;

  reelItem.innerHTML = `
        <div class="reel-video-wrapper" data-video-id="${reel.id}">
            <div id="${playerDivId}" class="youtube-player-placeholder"></div>
            <div class="reel-info-overlay">
                <h3 class="reel-title">${escapeHtml(reel.title)}</h3>
                <p class="reel-channel">📺 ${escapeHtml(reel.channel)}</p>
                <div class="reel-actions">
                    <button class="action-btn watch-on-yt" onclick="window.open('${
                      reel.url
                    }', '_blank')">
                        ▶ Watch on YouTube
                    </button>
                </div>
            </div>
        </div>
    `;

  return reelItem;
}

function initializePlayer(index, videoId) {
  const playerDivId = `player-${index}`;
  if (!document.getElementById(playerDivId)) return;

  players[index] = new YT.Player(playerDivId, {
    height: "100%",
    width: "100%",
    videoId: videoId,
    playerVars: {
      autoplay: 0,
      controls: 1,
      modestbranding: 1,
      rel: 0,
      fs: 1,
      playsinline: 1,
      origin: window.location.origin,
      enablejsapi: 1,
    },
    events: {
      onReady: (event) => {
        // If it's the first video and visible, play it (observer usually handles this though)
        // But observer might fire before player is ready?
        // We'll let observer handle playback trigger.
      },
      onStateChange: (event) => onPlayerStateChange(event, index),
      onError: (event) => {
        console.error(
          `Error playing video ${videoId} (index ${index}):`,
          event.data,
        );
        const reel = currentReels[index];

        if (event.data === 150 || event.data === 101) {
          console.log(
            `Video ${index} has embedding restrictions. Auto-skipping...`,
          );
          logVideoEvent(reel.id, "auto_skipped");

          const reelItem = document.querySelector(
            `.reel-item[data-index="${index}"]`,
          );
          if (reelItem) {
            reelItem.classList.add("restricted-video");
            reelItem.style.display = "none";
          }

          setTimeout(() => {
            const nextIndex = index + 1;
            if (nextIndex < currentReels.length) {
              scrollToReel(nextIndex);
            }
          }, 500);
        } else {
          onPlayerError(event, index);
        }
      },
    },
  });
}

function onPlayerStateChange(event, index) {
  if (event.data === YT.PlayerState.ENDED) {
    console.log(`Video ${index} ended. Scrolling to next.`);
    if (index < currentReels.length - 1) {
      scrollToReel(index + 1);
    }
  }
}

function onPlayerError(event, index) {
  console.warn(`Error in player ${index}: ${event.data}`);
  const reelItem = document.querySelector(`.reel-item[data-index="${index}"]`);
  if (reelItem) {
    const youtubeUrl = currentReels[index]?.url;
    showVideoError(reelItem, youtubeUrl);
  }
}

function showVideoError(reelItem, youtubeUrl) {
  const wrapper = reelItem?.querySelector(".reel-video-wrapper");
  if (!wrapper) return;

  const errorOverlay = document.createElement("div");
  errorOverlay.className = "error-overlay";
  errorOverlay.style.cssText = `
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: rgba(0, 0, 0, 0.9);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        color: white;
        text-align: center;
        z-index: 10;
    `;
  errorOverlay.innerHTML = `
        <p style="margin-bottom: 20px; font-size: 18px; font-weight: bold;">
            Video functionality limited
        </p>
        <button style="
            padding: 12px 24px;
            background: #ff0000;
            color: white;
            border: none;
            border-radius: 4px;
            font-size: 16px;
            cursor: pointer;
            font-weight: bold;
        " onclick="window.open('${youtubeUrl}', '_blank')">
            ▶ Watch on YouTube
        </button>
    `;
  wrapper.appendChild(errorOverlay);
}

function scrollToReel(index) {
  if (index < 0 || index >= currentReels.length) return;
  const reelsContainer = document.getElementById("reelsContainer");
  const reelItem = reelsContainer.querySelector(
    `.reel-item[data-index="${index}"]`,
  );

  if (reelItem) {
    reelItem.scrollIntoView({ behavior: "smooth", block: "center" });
  }
}

function playReelVideo(index) {
  // Pause all other videos
  Object.keys(players).forEach((key) => {
    const player = players[key];
    const playerIndex = parseInt(key);
    if (
      player &&
      typeof player.pauseVideo === "function" &&
      playerIndex !== index
    ) {
      player.pauseVideo();
    }
  });

  // Play current video
  const player = players[index];
  if (player && typeof player.playVideo === "function") {
    player.seekTo(0);
    player.playVideo();

    const reel = currentReels[index];
    if (reel) {
      logVideoEvent(reel.id, "played");
    }
  }
}

document.addEventListener("keydown", (e) => {
  if (e.key === "ArrowDown") {
    e.preventDefault();
    scrollToReel(currentIndex + 1);
  } else if (e.key === "ArrowUp") {
    e.preventDefault();
    scrollToReel(currentIndex - 1);
  }
});

function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}
