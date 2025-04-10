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
            socket.send(JSON.stringify({ input: message }));
            addMessage(message, "user-message");
            userInput.value = "";
        }
    });

    // 监听WebSocket消息
    socket.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === "output") {
            addMessage(data.data.content, "bot-message");
        } else if (data.type === "status") {
            // 处理状态更新
            updateStatus(data.data);
        } else if (data.type === "error") {
            // 处理错误消息
            showError(data.data);
        } else if (data.type === "think") {
            // 处理思考状态
            updateThinkStatus(data.data);
        }
    };
    
    // 更新状态显示
    function updateStatus(statusData) {
        const statusElement = document.getElementById("status-area") || 
            createStatusElement();
        statusElement.textContent = statusData.message;
    }
    
    // 显示错误消息
    function showError(errorData) {
        const errorElement = document.createElement("div");
        errorElement.className = "error-message";
        errorElement.textContent = `错误: ${errorData.message}`;
        document.getElementById("display-area").appendChild(errorElement);
    }
    
    // 更新思考状态
    function updateThinkStatus(thinkData) {
        let thinkElement = document.getElementById("think-indicator");
        if (!thinkElement) {
            thinkElement = document.createElement("div");
            thinkElement.id = "think-indicator";
            thinkElement.className = "think-message";
            document.getElementById("display-area").appendChild(thinkElement);
        }
        thinkElement.textContent = thinkData.message;
    }
    
    // 创建状态显示区域
    function createStatusElement() {
        const statusElement = document.createElement("div");
        statusElement.id = "status-area";
        statusElement.className = "status-message";
        document.body.insertBefore(statusElement, document.querySelector("footer"));
        return statusElement;
    }
});

// 添加消息到显示区域
function addMessage(content, className) {
    const messageElement = document.createElement("div");
    messageElement.className = `message ${className}`;
    messageElement.textContent = content;
    document.getElementById("display-area").appendChild(messageElement);
}