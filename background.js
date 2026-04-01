import { checkTrustWithGemini } from './scripts/api.js';

// 1. Tạo menu chuột phải khi extension được cài đặt
chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "check-trust-ai",
    title: "Kiểm tra độ tin cậy với AI",
    contexts: ["selection"] // Chỉ hiện khi bôi đen văn bản
  });
});

// 2. Lắng nghe sự kiện khi người dùng bấm vào menu
chrome.contextMenus.onClicked.addListener(async (info, tab) => {
  if (info.menuItemId === "check-trust-ai") {
    const selectedText = info.selectionText;
    console.log("Nội dung người dùng chọn:", selectedText);

    // Gửi thông báo "Đang xử lý..." (Giai đoạn 1 tạm dùng log)
    console.log("Đang gửi dữ liệu đến Gemini API...");

    try {
      const result = await checkTrustWithGemini(selectedText);
      console.log("Kết quả từ AI:", result);
      
      // Ở Giai đoạn 1, bạn có thể dùng alert để xem kết quả nhanh (chỉ chạy trong content script)
      // Hoặc đơn giản là nhìn kết quả trong Service Worker Console.
    } catch (error) {
      console.error("Lỗi khi kết nối API:", error);
    }
  }
});