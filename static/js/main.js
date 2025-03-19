// WebSocket连接
const socket = new WebSocket(`ws://${window.location.host}/ws`);

// 页面加载完成后初始化
document.addEventListener("DOMContentLoaded", () => {
    const userInput = document.getElementById("user-input");
    const sendButton = document.getElementById("send-button");
    const displayArea = document.getElementById("display-area");

    // 发送按钮点击事件
    sendButton.addEventListener("click", () => {
        const message = userInput.value.trim();
        if (message) {
            socket.send(JSON.stringify({ text: message }));
            addMessage(message, "user-message");
            userInput.value = "";
        }
    });

    // 监听WebSocket消息
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        if (data.type === "output") {
            addMessage(data.data.content, "bot-message");
        }
    };
});

// 添加消息到显示区域
function addMessage(content, className) {
    const messageElement = document.createElement("div");
    messageElement.className = `message ${className}`;
    messageElement.textContent = content;
    document.getElementById("display-area").appendChild(messageElement);
}