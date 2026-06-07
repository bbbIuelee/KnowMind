const chatForm = document.querySelector("#chatForm");
const messageInput = document.querySelector("#messageInput");
const messageList = document.querySelector("#messageList");

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
}

/**
 * 根据用户输入生成 Day 03 本地假回复。
 */
function buildLocalReply(message) {
    return `已收到：${message}。Day 04 会把这里替换为后端 /chat 接口调用。`;
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
function handleSubmit(event) {
    event.preventDefault();

    const message = messageInput.value.trim();
    if (!message) {
        return;
    }

    appendMessage("user", message);
    messageInput.value = "";
    resizeInput();

    window.setTimeout(() => {
        appendMessage("ai", buildLocalReply(message));
    }, 200);
}

chatForm.addEventListener("submit", handleSubmit);
messageInput.addEventListener("input", resizeInput);
