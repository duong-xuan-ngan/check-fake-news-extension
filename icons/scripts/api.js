const GEMINI_API_KEY = "AIzaSyDW2JoMdI8TmfEPq6T-owvktCbYynOLcFk";
const API_URL = `https://generativelanguage.googleapis.com/v1beta/models/gemini-flash-latest:generateContent?key=${GEMINI_API_KEY}`;

export async function checkTrustWithGemini(text) {
  const response = await fetch(API_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      contents: [{ parts: [{ text: `Phân tích độ tin cậy: "${text}"` }] }]
    })
  });

  const data = await response.json();
  
  // Dòng quan trọng nhất để debug:
  console.log("Dữ liệu thô từ Google:", data);

  if (data.error) {
    throw new Error(`Lỗi API: ${data.error.message}`);
  }

  if (data.candidates && data.candidates[0].content) {
    return data.candidates[0].content.parts[0].text;
  } else {
    // Nếu không có nội dung, in ra lý do (thường là safety ratings)
    console.warn("Lý do không có phản hồi:", data.promptFeedback);
    throw new Error("AI từ chối trả lời hoặc phản hồi trống");
  }
}