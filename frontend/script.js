const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const messageList = document.querySelector("#messageList");
const sendButton = document.querySelector("#sendButton");

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
 * 追加消息并滚动到最新位置。
 */
function appendMessage(role, content) {
    const messageElement = createMessageElement(role, content);
    messageList.append(messageElement);
    messageList.scrollTop = messageList.scrollHeight;
    return messageElement;
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
 * 调用后端非流式聊天接口。
 */
async function requestChatReply(message) {
    const response = await fetch("/chat", {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({
            message,
            session_id: null,
        }),
    });

    if (!response.ok) {
        throw new Error(`聊天接口请求失败：${response.status}`);
    }

    return response.json();
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
    if (!message) {
        return;
    }

    appendMessage("user", message);
    messageInput.value = "";
    resizeInput();
    sendButton.disabled = true;

    const aiMessageElement = appendMessage("ai", "正在请求 KnowMind 后端...");

    try {
        const data = await requestChatReply(message);
        updateMessageContent(aiMessageElement, data.response || "后端没有返回回答内容。");
    } catch (error) {
        updateMessageContent(aiMessageElement, error.message);
    } finally {
        sendButton.disabled = false;
        messageInput.focus();
    }
}

chatForm.addEventListener("submit", handleSubmit);
messageInput.addEventListener("input", resizeInput);
