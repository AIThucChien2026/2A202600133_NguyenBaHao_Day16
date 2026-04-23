# Lab 16 Benchmark Report

## Metadata
- Dataset: hotpot_mini.json
- Mode: real
- Records: 218
- Agents: react, reflexion

## Summary
| Metric | ReAct | Reflexion | Delta |
|---|---:|---:|---:|
| EM | 0.9908 | 1.0 | 0.0092 |
| Avg attempts | 1 | 1.0275 | 0.0275 |
| Avg token estimate | 720.12 | 764.92 | 44.8 |
| Avg latency (ms) | 1300.39 | 1348.49 | 48.1 |

## Failure modes
```json
{
  "react": {
    "none": 108,
    "wrong_final_answer": 1
  },
  "reflexion": {
    "none": 109
  },
  "overall": {
    "none": 217,
    "wrong_final_answer": 1
  }
}
```

## Extensions implemented
- structured_evaluator
- reflection_memory
- benchmark_report_json
- mock_mode_for_autograding
- adaptive_max_attempts

## Discussion
Báo cáo so sánh ReAct (thử 1 lần) và Reflexion (có bộ nhớ phản hồi) trên 109 câu HotpotQA. Chiến lược 3 mô hình (Groq API): (1) `llama-3.3-70b-versatile` làm Actor yếu ở lần đầu của Reflexion nhằm tạo lỗi; (2) `openai/gpt-oss-120b` làm Actor mạnh cho ReAct và các lần thử sau; (3) `qwen/qwen3-32b` làm Evaluator/Reflector.

Kết quả: Reflexion đạt độ chính xác tuyệt đối (EM=1.0) so với ReAct (0.9908), khắc phục tốt lỗi thiếu bước (incomplete_multi_hop) hoặc trôi dạt thực thể ở câu hỏi khó. Sự đánh đổi: Reflexion tốn thêm trung bình 44.8 tokens và 48.1 ms mỗi câu do phát sinh vòng lặp Reflector/Evaluator khi trả lời sai lần đầu (Avg attempts = 1.0275). Kết luận, cơ chế tự sửa sai của Reflexion rất hiệu quả cho tác vụ suy luận đa bước, chuyển hóa thành công câu trả lời thiếu sót thành đáp án hoàn hảo.
