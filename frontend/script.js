const TOKEN_KEY = "knowmind_access_token";
const USERNAME_KEY = "knowmind_username";
const SESSION_KEY = "knowmind_current_session_id";

const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const messageList = document.querySelector("#messageList");
const sendButton = document.querySelector("#sendButton");
const usernameInput = document.querySelector("#usernameInput");
const passwordInput = document.querySelector("#passwordInput");
const loginButton = document.querySelector("#loginButton");
const registerButton = document.querySelector("#registerButton");
const logoutButton = document.querySelector("#logoutButton");
const authStatus = document.querySelector("#authStatus");
const authMessage = document.querySelector("#authMessage");
const sessionSelect = document.querySelector("#sessionSelect");
const newSessionButton = document.querySelector("#newSessionButton");

let accessToken = localStorage.getItem(TOKEN_KEY) || "";
let currentUsername = localStorage.getItem(USERNAME_KEY) || "";
let currentSessionId = localStorage.getItem(SESSION_KEY) || "";

/**
 * 创建单条聊天消息节点。
 */
function createMessageElement(role, content) {
    const messageElement = document.createElement("article");
    messageElement.className = `message message-${role}`;

    const avatarElement = document.createElement("div");
    avatarElement.className = "avatar";
    avatarElement.textContent = role === "user" ? "我" : "K";

    const bubbleElement = document.createElement("div");
    bubbleElement.className = "bubble";
    bubbleElement.textContent = content;

    messageElement.append(avatarElement, bubbleElement);
    return messageElement;
}

/**
 * 清空当前消息列表。
 */
function clearMessages() {
    messageList.innerHTML = "";
}

/**
 * 追加消息并滚动到最新位置。
 */
function appendMessage(role, content) {
    const messageElement = createMessageElement(role, content);
    messageList.append(messageElement);
    messageList.scrollTop = messageList.scrollHeight;
    return messageElement;
}

/**
 * 显示当前登录状态对应的欢迎消息。
 */
function renderWelcomeMessage() {
    clearMessages();
    if (accessToken) {
        appendMessage("ai", "请选择一个历史会话，或直接发送消息开始新会话。");
        return;
    }
    appendMessage("ai", "你好，我是 KnowMind。请登录后开始新的知识问答会话。");
}

/**
 * 更新已有消息气泡内容。
 */
function updateMessageContent(messageElement, content) {
    const bubbleElement = messageElement.querySelector(".bubble");
    bubbleElement.textContent = content;
    messageList.scrollTop = messageList.scrollHeight;
}

/**
 * 更新登录提示文本。
 */
function setAuthMessage(message) {
    authMessage.textContent = message;
}

/**
 * 保存后端返回的登录凭据。
 */
function persistAuth(authData) {
    accessToken = authData.access_token;
    currentUsername = authData.username;
    localStorage.setItem(TOKEN_KEY, accessToken);
    localStorage.setItem(USERNAME_KEY, currentUsername);
}

/**
 * 清除本地登录和当前会话状态。
 */
function clearAuthState() {
    accessToken = "";
    currentUsername = "";
    currentSessionId = "";
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(USERNAME_KEY);
    localStorage.removeItem(SESSION_KEY);
}

/**
 * 根据登录状态刷新表单、按钮和输入框可用状态。
 */
function renderAuthState() {
    const loggedIn = Boolean(accessToken);
    authStatus.textContent = loggedIn ? `已登录：${currentUsername}` : "未登录";
    usernameInput.disabled = loggedIn;
    passwordInput.disabled = loggedIn;
    loginButton.hidden = loggedIn;
    registerButton.hidden = loggedIn;
    logoutButton.hidden = !loggedIn;
    messageInput.disabled = !loggedIn;
    sessionSelect.disabled = !loggedIn;
    newSessionButton.disabled = !loggedIn;
    sendButton.disabled = !loggedIn;
    messageInput.placeholder = loggedIn ? "输入一条消息" : "登录后才能发送消息";
}

/**
 * 设置认证表单按钮的加载状态。
 */
function setAuthBusy(isBusy) {
    loginButton.disabled = isBusy;
    registerButton.disabled = isBusy;
    logoutButton.disabled = isBusy;
}

/**
 * 设置聊天发送按钮的加载状态。
 */
function setChatBusy(isBusy) {
    sendButton.disabled = isBusy || !accessToken;
}

/**
 * 创建携带认证信息的请求头。
 */
function buildHeaders(hasJsonBody) {
    const headers = {};
    if (hasJsonBody) {
        headers["Content-Type"] = "application/json";
    }
    if (accessToken) {
        headers.Authorization = `Bearer ${accessToken}`;
    }
    return headers;
}

/**
 * 发起 JSON 请求并统一处理错误信息。
 */
async function requestJson(path, options = {}) {
    const hasJsonBody = Object.prototype.hasOwnProperty.call(options, "body");
    const response = await fetch(path, {
        ...options,
        headers: buildHeaders(hasJsonBody),
        body: hasJsonBody ? JSON.stringify(options.body) : undefined,
    });

    let data = null;
    try {
        data = await response.json();
    } catch (error) {
        data = null;
    }

    if (!response.ok) {
        if (response.status === 401) {
            clearAuthState();
            renderAuthState();
            renderWelcomeMessage();
        }
        const detail = data && typeof data.detail === "string" ? data.detail : `请求失败：${response.status}`;
        throw new Error(detail);
    }

    return data;
}

/**
 * 按登录或注册模式提交账号信息。
 */
async function submitAuth(mode) {
    const username = usernameInput.value.trim();
    const password = passwordInput.value.trim();
    if (!username || !password) {
        setAuthMessage("用户名和密码不能为空。");
        return;
    }

    setAuthBusy(true);
    try {
        const endpoint = mode === "register" ? "/auth/register" : "/auth/login";
        const authData = await requestJson(endpoint, {
            method: "POST",
            body: { username, password },
        });
        persistAuth(authData);
        currentSessionId = "";
        localStorage.removeItem(SESSION_KEY);
        passwordInput.value = "";
        setAuthMessage(mode === "register" ? "注册并登录成功。" : "登录成功。");
        renderAuthState();
        renderWelcomeMessage();
        await refreshSessionList();
        messageInput.focus();
    } catch (error) {
        setAuthMessage(error.message);
    } finally {
        setAuthBusy(false);
        renderAuthState();
    }
}

/**
 * 退出当前账号。
 */
function logout() {
    clearAuthState();
    renderAuthState();
    renderWelcomeMessage();
    renderSessionOptions([]);
    setAuthMessage("已退出登录。");
}

/**
 * 渲染会话下拉列表。
 */
function renderSessionOptions(sessions) {
    sessionSelect.innerHTML = "";
    const newOption = document.createElement("option");
    newOption.value = "";
    newOption.textContent = "新会话";
    sessionSelect.append(newOption);

    sessions.forEach((session) => {
        const option = document.createElement("option");
        option.value = session.session_id;
        option.textContent = session.title || session.session_id;
        sessionSelect.append(option);
    });

    sessionSelect.value = currentSessionId || "";
}

/**
 * 从后端刷新当前用户的会话列表。
 */
async function refreshSessionList() {
    if (!accessToken) {
        renderSessionOptions([]);
        return [];
    }
    const sessions = await requestJson("/sessions");
    renderSessionOptions(sessions);
    return sessions;
}

/**
 * 渲染指定会话详情中的历史消息。
 */
async function loadSessionDetail(sessionId) {
    if (!sessionId) {
        startNewSession();
        return;
    }

    const detail = await requestJson(`/sessions/${encodeURIComponent(sessionId)}`);
    currentSessionId = detail.session_id;
    localStorage.setItem(SESSION_KEY, currentSessionId);
    sessionSelect.value = currentSessionId;
    clearMessages();

    if (!detail.messages.length) {
        appendMessage("ai", "这个会话还没有消息。");
        return;
    }

    detail.messages.forEach((message) => {
        appendMessage(message.message_type === "user" ? "user" : "ai", message.content);
    });
}

/**
 * 根据本地保存的会话 ID 恢复最近一次会话。
 */
async function restoreSessionAfterLogin() {
    const sessions = await refreshSessionList();
    const hasSavedSession = sessions.some((session) => session.session_id === currentSessionId);
    if (currentSessionId && hasSavedSession) {
        await loadSessionDetail(currentSessionId);
        return;
    }

    currentSessionId = "";
    localStorage.removeItem(SESSION_KEY);
    renderWelcomeMessage();
    sessionSelect.value = "";
}

/**
 * 调用后端非流式聊天接口。
 */
async function requestChatReply(message) {
    if (!accessToken) {
        throw new Error("请先登录后再发送消息。");
    }

    const data = await requestJson("/chat", {
        method: "POST",
        body: {
            message,
            session_id: currentSessionId || null,
        },
    });

    currentSessionId = data.session_id;
    localStorage.setItem(SESSION_KEY, currentSessionId);
    return data;
}

/**
 * 自动调整输入框高度，避免长文本遮挡。
 */
function resizeInput() {
    messageInput.style.height = "auto";
    messageInput.style.height = `${Math.min(messageInput.scrollHeight, 120)}px`;
}

/**
 * 处理聊天表单提交。
 */
async function handleSubmit(event) {
    event.preventDefault();

    const message = messageInput.value.trim();
    if (!message || !accessToken) {
        if (!accessToken) {
            setAuthMessage("请先登录后再发送消息。");
        }
        return;
    }

    appendMessage("user", message);
    messageInput.value = "";
    resizeInput();
    setChatBusy(true);

    const aiMessageElement = appendMessage("ai", "正在请求 KnowMind 后端...");

    try {
        const data = await requestChatReply(message);
        updateMessageContent(aiMessageElement, data.response || "后端没有返回回答内容。");
        await refreshSessionList();
        sessionSelect.value = currentSessionId;
    } catch (error) {
        updateMessageContent(aiMessageElement, error.message);
    } finally {
        setChatBusy(false);
        messageInput.focus();
    }
}

/**
 * 开启一个新的本地会话上下文。
 */
function startNewSession() {
    currentSessionId = "";
    localStorage.removeItem(SESSION_KEY);
    sessionSelect.value = "";
    renderWelcomeMessage();
    messageInput.focus();
}

/**
 * 处理会话下拉选择变化。
 */
async function handleSessionChange() {
    try {
        await loadSessionDetail(sessionSelect.value);
    } catch (error) {
        setAuthMessage(error.message);
    }
}

/**
 * 处理登录按钮点击。
 */
function handleLoginClick() {
    submitAuth("login");
}

/**
 * 处理注册按钮点击。
 */
function handleRegisterClick() {
    submitAuth("register");
}

/**
 * 校验本地 token 并初始化页面状态。
 */
async function initializeApp() {
    renderAuthState();
    renderWelcomeMessage();
    if (!accessToken) {
        renderSessionOptions([]);
        return;
    }

    try {
        const user = await requestJson("/auth/me");
        currentUsername = user.username;
        localStorage.setItem(USERNAME_KEY, currentUsername);
        renderAuthState();
        setAuthMessage("已恢复登录状态。");
        await restoreSessionAfterLogin();
    } catch (error) {
        setAuthMessage(error.message);
        logout();
    }
}

loginButton.addEventListener("click", handleLoginClick);
registerButton.addEventListener("click", handleRegisterClick);
logoutButton.addEventListener("click", logout);
newSessionButton.addEventListener("click", startNewSession);
sessionSelect.addEventListener("change", handleSessionChange);
chatForm.addEventListener("submit", handleSubmit);
messageInput.addEventListener("input", resizeInput);

initializeApp();
