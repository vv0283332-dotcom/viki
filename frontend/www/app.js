const API = "https://viki-api.onrender.com";

let token = localStorage.getItem("viki_token");
let currentUser = null;

let selectedMusic = null;
let musicAudio = null;

const $ = (id) => document.getElementById(id);

function authHeaders() {
  return {
    "Content-Type": "application/json",
    "Authorization": `Bearer ${token}`
  };
}

async function api(path, options = {}) {
  const response = await fetch(API + path, {
    ...options,
    headers: {
      ...(options.body ? {"Content-Type": "application/json"} : {}),
      ...(token ? {"Authorization": `Bearer ${token}`} : {}),
      ...(options.headers || {})
    }
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Request failed");
  }

  return data;
}

function showAuth() {
  $("authScreen").classList.remove("hidden");
  $("mainApp").classList.add("hidden");
  $("bottomNav").classList.add("hidden");
  $("logoutBtn").classList.add("hidden");
}

function showApp() {
  $("authScreen").classList.add("hidden");
  $("mainApp").classList.remove("hidden");
  $("bottomNav").classList.remove("hidden");
  $("logoutBtn").classList.remove("hidden");
}

function setMessage(message) {
  $("authMessage").textContent = message;
}

$("loginTab").onclick = () => {
  $("loginTab").classList.add("active");
  $("registerTab").classList.remove("active");
  $("loginForm").classList.remove("hidden");
  $("registerForm").classList.add("hidden");
  setMessage("");
};

$("registerTab").onclick = () => {
  $("registerTab").classList.add("active");
  $("loginTab").classList.remove("active");
  $("registerForm").classList.remove("hidden");
  $("loginForm").classList.add("hidden");
  setMessage("");
};

$("loginForm").onsubmit = async (event) => {
  event.preventDefault();

  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: $("loginEmail").value,
        password: $("loginPassword").value
      })
    });

    token = data.access_token;
    localStorage.setItem("viki_token", token);

    currentUser = data.user;
    showApp();
    await loadApp();
  } catch (error) {
    setMessage(error.message);
  }
};

$("registerForm").onsubmit = async (event) => {
  event.preventDefault();

  try {
    const data = await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        full_name: $("registerName").value,
        username: $("registerUsername").value,
        email: $("registerEmail").value,
        password: $("registerPassword").value
      })
    });

    token = data.access_token;
    localStorage.setItem("viki_token", token);

    currentUser = data.user;
    showApp();
    await loadApp();
  } catch (error) {
    setMessage(error.message);
  }
};

$("logoutBtn").onclick = () => {
  localStorage.removeItem("viki_token");
  token = null;
  currentUser = null;
  showAuth();
};

$("postContent").oninput = () => {
  $("charCount").textContent =
    `${$("postContent").value.length} / 5000`;
};


// =========================
// MEDIA PICKER
// =========================

$("postMedia").onchange = () => {
  const file = $("postMedia").files[0];

  const preview = $("mediaPreview");
  const name = $("mediaName");

  preview.innerHTML = "";

  if (!file) {
    name.textContent = "No media selected";
    preview.classList.add("hidden");
    return;
  }

  name.textContent = file.name;

  const url = URL.createObjectURL(file);

  if (file.type.startsWith("video/")) {
    preview.innerHTML = `
      <video
        src="${url}"
        controls
        playsinline
        preload="metadata">
      </video>
    `;
  } else if (file.type.startsWith("image/")) {
    preview.innerHTML = `
      <img
        src="${url}"
        alt="Post preview">
    `;
  }

  preview.classList.remove("hidden");
};


// =========================
// UPLOAD MEDIA
// =========================

async function uploadPostMedia(file) {
  const formData = new FormData();
  formData.append("file", file);

  $("uploadStatus").textContent = "Uploading media...";

  const response = await fetch(`${API}/upload-media`, {
    method: "POST",
    headers: token
      ? {"Authorization": `Bearer ${token}`}
      : {},
    body: formData
  });

  const data = await response.json().catch(() => ({}));

  if (!response.ok) {
    throw new Error(data.detail || "Media upload failed");
  }

  $("uploadStatus").textContent = "Media uploaded.";

  return data;
}


function clearSelectedMusic() {
  selectedMusic = null;

  if (musicAudio) {
    musicAudio.pause();
    musicAudio = null;
  }

  const box = $("selectedMusic");
  if (box) {
    box.innerHTML = "";
    box.classList.add("hidden");
  }
}

function selectMusic(track) {
  selectedMusic = track;

  if (musicAudio) {
    musicAudio.pause();
    musicAudio = null;
  }

  const box = $("selectedMusic");

  box.innerHTML = `
    <div class="selected-music-info">
      <img
        src="${escapeHtml(track.artwork_url || "")}"
        alt=""
        class="music-art"
      >
      <div>
        <strong>${escapeHtml(track.title)}</strong>
        <span>${escapeHtml(track.artist)}</span>
      </div>
      <button type="button" id="removeMusicBtn">✕</button>
    </div>
  `;

  box.classList.remove("hidden");

  $("removeMusicBtn").onclick = clearSelectedMusic;

  $("musicPanel").classList.add("hidden");
}

function renderMusicResults(tracks) {
  const results = $("musicResults");

  if (!tracks.length) {
    results.innerHTML = `
      <div class="music-empty">No songs found.</div>
    `;
    return;
  }

  results.innerHTML = tracks.map((track, index) => `
    <div class="music-result">
      <img
        src="${escapeHtml(track.artwork_url || "")}"
        alt=""
        class="music-art"
      >

      <div class="music-info">
        <strong>${escapeHtml(track.title)}</strong>
        <span>${escapeHtml(track.artist)}</span>
        <small>${escapeHtml(track.album || "")}</small>
      </div>

      <button
        type="button"
        class="music-preview"
        data-index="${index}"
      >
        ▶
      </button>

      <button
        type="button"
        class="music-select"
        data-index="${index}"
      >
        +
      </button>
    </div>
  `).join("");

  results.querySelectorAll(".music-preview").forEach(button => {
    button.onclick = () => {
      const track = tracks[Number(button.dataset.index)];

      if (musicAudio) {
        musicAudio.pause();
      }

      musicAudio = new Audio(track.preview_url);
      musicAudio.play().catch(() => {
        alert("Unable to play this preview.");
      });
    };
  });

  results.querySelectorAll(".music-select").forEach(button => {
    button.onclick = () => {
      const track = tracks[Number(button.dataset.index)];
      selectMusic(track);
    };
  });
}

async function searchMusic() {
  const query = $("musicSearch").value.trim();

  if (!query) return;

  const results = $("musicResults");
  results.innerHTML = `<div class="music-empty">Searching...</div>`;

  try {
    const data = await api(
      `/music/search?q=${encodeURIComponent(query)}`
    );

    renderMusicResults(data.tracks || []);
  } catch (error) {
    results.innerHTML = `
      <div class="music-empty">
        ${escapeHtml(error.message)}
      </div>
    `;
  }
}

if ($("musicBtn")) {
  $("musicBtn").onclick = () => {
    $("musicPanel").classList.toggle("hidden");

    if (!$("musicPanel").classList.contains("hidden")) {
      $("musicSearch").focus();
    }
  };
}

if ($("musicSearchBtn")) {
  $("musicSearchBtn").onclick = searchMusic;
}

if ($("musicSearch")) {
  $("musicSearch").onkeydown = (event) => {
    if (event.key === "Enter") {
      event.preventDefault();
      searchMusic();
    }
  };
}

$("postForm").onsubmit = async (event) => {
  event.preventDefault();

  const content = $("postContent").value.trim();

  if (!content) return;

  try {
    let mediaUrl = "";
    let mediaType = "none";

    const musicUrl = selectedMusic?.preview_url || "";
    const musicTitle = selectedMusic?.title || "";
    const musicArtist = selectedMusic?.artist || "";

    const mediaFile = $("postMedia").files[0];

    if (mediaFile) {
      if (mediaFile.size > 300 * 1024 * 1024) {
        throw new Error("Media must be 300 MB or smaller.");
      }

      const uploaded = await uploadPostMedia(mediaFile);

      mediaUrl = uploaded.url;
      mediaType = uploaded.media_type;
    }

    await api("/posts", {
      method: "POST",
      body: JSON.stringify({
        content,
        media_url: mediaUrl,
        media_type: mediaType,
        music_url: musicUrl,
        music_title: musicTitle,
        music_artist: musicArtist
      })
    });

    $("postContent").value = "";
    $("charCount").textContent = "0 / 5000";

    $("postMedia").value = "";
    $("mediaName").textContent = "No media selected";
    $("mediaPreview").innerHTML = "";
    $("mediaPreview").classList.add("hidden");
    $("uploadStatus").textContent = "";

    clearSelectedMusic();

    await loadFeed();

  } catch (error) {
    $("uploadStatus").textContent = "";
    alert(error.message);
  }
};

async function loadFeed() {
  try {
    const data = await api("/feed");

    const feed = $("feed");

    if (!data.posts.length) {
      feed.innerHTML = `
        <div class="empty">
          <h3>Your feed is empty</h3>
          <p>Create your first post or follow people to build your feed.</p>
        </div>
      `;
      return;
    }

    feed.innerHTML = data.posts.map(post => `
      <article class="post">
        <div class="post-header">
          <div class="avatar">
            ${(post.author.full_name || "V").charAt(0).toUpperCase()}
          </div>
          <div>
            <div class="post-author">${escapeHtml(post.author.full_name)}</div>
            <div class="post-time">@${escapeHtml(post.author.username)}</div>
          </div>
        </div>

        <div class="post-content">${escapeHtml(post.content)}</div>

        ${
          post.music_url
            ? `
              <div class="post-music">
                <div class="post-music-title">
                  🎵 ${escapeHtml(post.music_title || "Music")}
                </div>
                <div class="post-music-artist">
                  ${escapeHtml(post.music_artist || "")}
                </div>
                <audio
                  src="${escapeHtml(post.music_url)}"
                  controls
                  preload="none">
                </audio>
              </div>
            `
            : ""
        }

        ${
          post.media_url && post.media_type === "video"
            ? `
              <div class="post-media">
                <video
                  src="${escapeHtml(post.media_url)}"
                  controls
                  playsinline
                  preload="metadata">
                </video>
              </div>
            `
            : ""
        }

        ${
          post.media_url && post.media_type === "image"
            ? `
              <div class="post-media">
                <img
                  src="${escapeHtml(post.media_url)}"
                  alt="VIKI post image"
                  loading="lazy">
              </div>
            `
            : ""
        }

        <div class="post-actions">
          <button onclick="toggleLike(${post.id}, ${post.liked_by_me})">
            ${post.liked_by_me ? "❤️" : "♡"} ${post.likes}
          </button>

          <button onclick="showComments(${post.id})">
            💬 ${post.comments}
          </button>

          ${
            post.author.id === currentUser.id
              ? `<button onclick="deletePost(${post.id})">🗑️</button>`
              : ""
          }
        </div>

        <div id="comments-${post.id}"></div>
      </article>
    `).join("");

  } catch (error) {
    $("feed").innerHTML = `
      <div class="empty">
        <h3>Unable to load feed</h3>
        <p>${escapeHtml(error.message)}</p>
      </div>
    `;
  }
}

async function toggleLike(postId, liked) {
  try {
    await api(`/posts/${postId}/like`, {
      method: liked ? "DELETE" : "POST"
    });

    await loadFeed();
  } catch (error) {
    alert(error.message);
  }
}

async function deletePost(postId) {
  if (!confirm("Delete this post?")) return;

  try {
    await api(`/posts/${postId}`, {
      method: "DELETE"
    });

    await loadFeed();
  } catch (error) {
    alert(error.message);
  }
}

async function showComments(postId) {
  const container = $(`comments-${postId}`);

  if (container.dataset.open === "true") {
    container.innerHTML = "";
    container.dataset.open = "false";
    return;
  }

  try {
    const data = await api(`/posts/${postId}/comments`);

    container.dataset.open = "true";

    container.innerHTML = `
      <div style="margin-top:12px">
        ${data.comments.map(comment => `
          <div style="padding:8px 0;border-top:1px solid #eee">
            <strong>@${escapeHtml(comment.author.username)}</strong>
            ${escapeHtml(comment.content)}
          </div>
        `).join("")}

        <form onsubmit="addComment(event, ${postId})"
              style="margin-top:10px">
          <input name="comment"
                 placeholder="Write a comment..."
                 required>
        </form>
      </div>
    `;
  } catch (error) {
    alert(error.message);
  }
}

async function addComment(event, postId) {
  event.preventDefault();

  const form = event.target;
  const content = form.comment.value.trim();

  if (!content) return;

  try {
    await api(`/posts/${postId}/comments`, {
      method: "POST",
      body: JSON.stringify({content})
    });

    await loadFeed();
  } catch (error) {
    alert(error.message);
  }
}

async function loadProfile() {
  if (!currentUser) return;

  try {
    const data = await api(`/users/${currentUser.username}`);

    $("profileName").textContent = data.full_name;
    $("profileUsername").textContent = `@${data.username}`;
    $("profileBio").textContent = data.bio || "No bio yet.";
    $("postCount").textContent = data.posts;
    $("followersCount").textContent = data.followers;
    $("followingCount").textContent = data.following;
    const avatarImg = $("profileAvatarImg");
    const avatarFallback = $("profileAvatar");

    if (data.avatar_url) {
      avatarImg.src = data.avatar_url;
      avatarImg.classList.remove("hidden");
      avatarFallback.classList.add("hidden");
    } else {
      avatarImg.removeAttribute("src");
      avatarImg.classList.add("hidden");
      avatarFallback.classList.remove("hidden");
      avatarFallback.textContent =
        (data.full_name || "V").charAt(0).toUpperCase();
    }

  } catch (error) {
    console.error(error);
  }
}


async function loadPaymentProviders() {
  const select = $("fundProvider");
  if (!select) return;

  try {
    const currency =
      ($("walletCurrency")?.textContent || "USD").trim();

    const country =
      ($("fundCountry")?.value || "").trim().toUpperCase();

    const data = await api(
      `/wallets/payment-providers?currency=${encodeURIComponent(currency)}&country=${encodeURIComponent(country)}`
    );

    select.innerHTML = "";

    if (!data.providers.length) {
      select.innerHTML =
        `<option value="">No configured provider</option>`;

      return;
    }

    data.providers.forEach(provider => {
      const option = document.createElement("option");
      option.value = provider;
      option.textContent =
        provider.charAt(0).toUpperCase() + provider.slice(1);

      select.appendChild(option);
    });

  } catch (error) {
    console.error("Payment providers:", error);

    select.innerHTML =
      `<option value="">Unable to load providers</option>`;
  }
}


async function startWalletFunding(event) {
  event.preventDefault();

  const amount = Number($("fundAmount").value);
  const currency =
    ($("walletCurrency")?.textContent || "USD").trim();

  const country =
    ($("fundCountry")?.value || "").trim().toUpperCase();

  const provider =
    ($("fundProvider")?.value || "").trim();

  const message = $("fundWalletMessage");
  const button = $("fundWalletBtn");

  if (!Number.isFinite(amount) || amount <= 0) {
    message.textContent = "Enter a valid amount.";
    return;
  }

  if (!provider) {
    message.textContent =
      "No payment provider is currently configured for this currency.";
    return;
  }

  button.disabled = true;
  message.textContent = "Creating secure payment checkout...";

  try {
    const data = await api("/wallets/deposit", {
      method: "POST",
      body: JSON.stringify({
        amount,
        currency,
        country,
        provider
      })
    });

    if (!data.checkout_url) {
      throw new Error("Payment checkout URL was not returned.");
    }

    localStorage.setItem(
      "viki_pending_deposit",
      data.provider_reference
    );

    message.textContent =
      "Opening secure payment page...";

    window.location.href = data.checkout_url;

  } catch (error) {
    message.textContent = error.message;
    button.disabled = false;
  }
}


async function verifyReturnedPayment() {
  const params = new URLSearchParams(window.location.search);

  const reference =
    params.get("reference") ||
    localStorage.getItem("viki_pending_deposit");

  if (!reference) return;

  try {
    const result =
      await api(
        `/wallets/deposit/verify/${encodeURIComponent(reference)}`,
        {method: "POST"}
      );

    if (result.success && result.status === "completed") {
      localStorage.removeItem("viki_pending_deposit");

      alert(
        `Wallet funded successfully: ${Number(result.balance).toFixed(2)} ${result.currency}`
      );

      await loadWallet();
    }

  } catch (error) {
    console.error("Payment verification:", error);
  }

  if (window.location.search) {
    window.history.replaceState(
      {},
      document.title,
      window.location.pathname
    );
  }
}


async function loadWallet() {
  try {
    const data = await api("/wallet");

    $("walletBalance").textContent =
      Number(data.available).toFixed(2);

    $("walletPending").textContent =
      Number(data.pending).toFixed(2);

    $("walletCurrency").textContent =
      data.currency;

    await loadPaymentProviders();

    const ledger = await api("/wallet/ledger");

    $("ledger").innerHTML = ledger.length
      ? ledger.map(item => `
          <div class="ledger-item">
            <span>${escapeHtml(item.description)}</span>
            <strong>
              ${Number(item.amount).toFixed(2)}
              ${escapeHtml(item.currency)}
            </strong>
          </div>
        `).join("")
      : `<div class="empty">
           <p>No transactions yet.</p>
         </div>`;
  } catch (error) {
    console.error(error);
  }
}

async function loadApp() {
  await Promise.all([
    loadFeed(),
    loadProfile(),
    loadWallet()
  ]);
}

function switchView(viewId) {
  document.querySelectorAll(".view").forEach(view => {
    view.classList.remove("active-view");
  });

  $(viewId).classList.add("active-view");
}

document.querySelectorAll(".bottom-nav button").forEach(button => {
  button.onclick = () => {
    switchView(button.dataset.view);
  };
});

function escapeHtml(value) {
  const div = document.createElement("div");
  div.textContent = value ?? "";
  return div.innerHTML;
}

async function boot() {
  if (!token) {
    showAuth();
    return;
  }

  try {
    currentUser = await api("/me");
    showApp();
    await loadApp();
  } catch {
    localStorage.removeItem("viki_token");
    token = null;
    showAuth();
  }
}

boot();


async function loadCreatorCenter() {
  try {
    const me = await api("/me");

    $("creatorStatus").textContent =
      me.is_creator ? "Creator" : "Not a creator";

    const data = await api("/monetization/creator/earnings");

    if (!data.earnings.length) {
      $("creatorEarnings").textContent = "0.00";
      $("creatorCurrency").textContent = "USD";
      return;
    }

    const first = data.earnings[0];

    $("creatorEarnings").textContent =
      Number(first.amount).toFixed(2);

    $("creatorCurrency").textContent =
      first.currency;

  } catch (error) {
    console.error("Creator center:", error);
  }
}


async function loadOwnerCenter() {
  const container = $("ownerContent");

  try {
    const data = await api("/monetization/owner/revenue");

    if (!data.revenue.length) {
      container.innerHTML = `
        <div class="empty">
          <h3>VIKI revenue</h3>
          <p>No completed platform revenue yet.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = data.revenue.map(item => `
      <div class="wallet-card">
        <p>Platform revenue</p>
        <strong>
          ${Number(item.amount).toFixed(2)}
        </strong>
        <span>${escapeHtml(item.currency)}</span>
      </div>
    `).join("");

  } catch (error) {
    container.innerHTML = `
      <div class="empty">
        <h3>Owner access required</h3>
        <p>This area is restricted to VIKI administrators.</p>
      </div>
    `;
  }
}


$("giftForm").onsubmit = async (event) => {
  event.preventDefault();

  const creator = $("giftCreator").value
    .trim()
    .replace(/^@/, "");

  const amount = Number($("giftAmount").value);

  if (!creator || !Number.isFinite(amount) || amount <= 0) {
    $("giftMessage").textContent =
      "Enter a valid creator and amount.";
    return;
  }

  try {
    const data = await api("/monetization/gift", {
      method: "POST",
      body: JSON.stringify({
        creator_username: creator,
        amount,
        currency: "USD"
      })
    });

    $("giftMessage").textContent =
      `Gift sent. Creator received ${data.creator_amount.toFixed(2)} ${data.currency}.`;

    $("giftForm").reset();

    await loadCreatorCenter();
    await loadWallet();

  } catch (error) {
    $("giftMessage").textContent =
      error.message;
  }
};


const originalLoadApp = loadApp;

loadApp = async function() {
  await originalLoadApp();

  await loadCreatorCenter();

  if (currentUser?.is_admin) {
    const nav = document.querySelector(".bottom-nav");

    if (!document.querySelector('[data-view="ownerView"]')) {
      const button = document.createElement("button");

      button.dataset.view = "ownerView";
      button.innerHTML = "👑<span>Owner</span>";

      button.onclick = () => switchView("ownerView");

      nav.appendChild(button);
    }

    await loadOwnerCenter();
  }
};


async function loadDiscoverUsers(search = "") {
  const container = $("discoverResults");

  try {
    const data = await api(
      "/discover/users?q=" + encodeURIComponent(search)
    );

    if (!data.users.length) {
      container.innerHTML = `
        <div class="empty">
          <h3>No people found</h3>
          <p>Try another search.</p>
        </div>
      `;
      return;
    }

    container.innerHTML = data.users.map(user => `
      <div class="discover-user">
        <div class="discover-avatar">
          ${escapeHtml(
            (user.username || "?").charAt(0).toUpperCase()
          )}
        </div>

        <div class="discover-info">
          <strong>
            ${escapeHtml(user.full_name || user.username)}
            ${user.is_creator ? " 💎" : ""}
          </strong>

          <span>
            @${escapeHtml(user.username)}
          </span>
        </div>

        <button
          class="follow-btn ${user.is_following ? "following" : ""}"
          data-follow-user="${user.id}"
          data-following="${user.is_following}"
        >
          ${user.is_following ? "Following" : "Follow"}
        </button>
      </div>
    `).join("");

    container.querySelectorAll("[data-follow-user]")
      .forEach(button => {
        button.addEventListener("click", async () => {
          const id = button.dataset.followUser;
          const following = button.dataset.following === "true";

          try {
            if (following) {
              await api(`/discover/follow/${id}`, {
                method: "DELETE"
              });
            } else {
              await api(`/discover/follow/${id}`, {
                method: "POST"
              });
            }

            await loadDiscoverUsers(
              $("discoverSearch").value.trim()
            );

            if (typeof loadFeed === "function") {
              await loadFeed();
            }

          } catch (error) {
            alert(error.message);
          }
        });
      });

  } catch (error) {
    container.innerHTML = `
      <div class="empty">
        <h3>Unable to load Discover</h3>
        <p>${escapeHtml(error.message)}</p>
      </div>
    `;
  }
}


let discoverTimer;

$("discoverSearch")?.addEventListener("input", () => {
  clearTimeout(discoverTimer);

  discoverTimer = setTimeout(() => {
    loadDiscoverUsers(
      $("discoverSearch").value.trim()
    );
  }, 250);
});


loadDiscoverUsers();

/* =========================
   PROFILE AVATAR UPLOAD
   ========================= */

const avatarInput = $("avatarInput");

if (avatarInput) {
  avatarInput.addEventListener("change", async () => {
    const file = avatarInput.files?.[0];

    if (!file) return;

    if (!file.type.startsWith("image/")) {
      alert("Please select an image.");
      avatarInput.value = "";
      return;
    }

    if (file.size > 5 * 1024 * 1024) {
      alert("Profile picture must be 5 MB or smaller.");
      avatarInput.value = "";
      return;
    }

    try {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`${API}/profiles/me/avatar`, {
        method: "POST",
        headers: token
          ? { Authorization: `Bearer ${token}` }
          : {},
        body: formData
      });

      const data = await response.json().catch(() => ({}));

      if (!response.ok) {
        throw new Error(data.detail || "Profile picture upload failed.");
      }

      const avatarImg = $("profileAvatarImg");
      const avatarFallback = $("profileAvatar");

      if (avatarImg && data.avatar_url) {
        const separator = data.avatar_url.includes("?") ? "&" : "?";

        avatarImg.src = `${API}${data.avatar_url}${separator}t=${Date.now()}`;
        avatarImg.classList.remove("hidden");

        if (avatarFallback) {
          avatarFallback.classList.add("hidden");
        }
      }

      if (currentUser) {
        currentUser.avatar_url = data.avatar_url;
      }

      avatarInput.value = "";

    } catch (error) {
      console.error("Avatar upload:", error);
      alert(error.message);
      avatarInput.value = "";
    }
  });
}


document.addEventListener("DOMContentLoaded", () => {
  const form = $("fundWalletForm");

  if (form) {
    form.onsubmit = startWalletFunding;
  }

  const country = $("fundCountry");

  if (country) {
    country.addEventListener("input", () => {
      loadPaymentProviders();
    });
  }
});

verifyReturnedPayment();
